#!/usr/bin/env python

"""
m2g.scripts.m2g_dwi_pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Contains the primary, top-level pipeline.
For a full description, see here: https://neurodata.io/talks/ndmg.pdf
"""


# standard library imports
import shutil
import time
from datetime import datetime
import os
from pathlib import Path
from argparse import ArgumentParser

# package imports
import nibabel as nib
import numpy as np
from subprocess import Popen
from dipy.tracking.streamline import Streamlines
from dipy.io import read_bvals_bvecs

# m2g imports
from m2g import preproc
from m2g import register
from m2g import track
from m2g import graph
from m2g.utils import gen_utils
from m2g.utils import reg_utils
from m2g.utils import cloud_utils
from m2g.stats.qa_tractography import qa_tractography

# multithreading
import multiprocessing as mp

# TODO : not sure why this is here, potentially remove
os.environ["MPLCONFIGDIR"] = "/tmp/"


def m2g_dwi_worker(
    dwi,
    bvals,
    bvecs,
    t1w,
    atlas,
    mask,
    parcellations,
    outdir,
    vox_size="2mm",
    mod_type="det",
    track_type="local",
    mod_func="csa",
    seeds=20,
    reg_style="native",
    skipeddy=False,
    skipreg=False,
    skull=None,
    n_cpus=1,
):
    """Creates a brain graph from MRI data
    Parameters
    ----------
    dwi : str
        Path for the dwi file(s)
    bvals : str
        Path for the bval file(s)
    bvecs : str
        Path for the bvec file(s)
    t1w : str
        Location of anatomical input file(s)
    atlas : str
        Location of atlas file
    mask : str
        Location of T1w brain mask file, make sure the proper voxel size is used
    parcellations : list
        Filepaths to the parcellations we're using.
    outdir : str
        The directory where the output files should be stored. Prepopulate this folder with results of participants level analysis if running gorup analysis.
    vox_size : str
        Voxel size to use for template registrations. Default is '2mm'.
    mod_type : str
        Determinstic (det) or probabilistic (prob) tracking. Default is det.
    track_type : str
        Tracking approach: eudx or local. Default is eudx.
    mod_func : str
        Diffusion model: csd, csa. Default is csa.
    seeds : int
        Density of seeding for native-space tractography.
    reg_style : str
        Space for tractography. Default is native.
    skipeddy : bool
        Whether or not to skip the eddy correction if it has already been run. Default is False.
    skipreg : bool
        Whether or not to skip registration. Default is False.
    skull : str, optional
        skullstrip parameter pre-set. Default is "none".
    n_cpus : int, optional
        Number of CPUs to use for computing edges from streamlines
    Raises
    ------
    ValueError
        Raised if downsampling voxel size is not supported
    ValueError
        Raised if bval/bvecs are potentially corrupted
    """

    # -------- Initial Setup ------------------ #
    # print starting arguments for clarity in log
    args = locals().copy()
    for arg, value in args.items():
        print(f"{arg} = {value}")

    # initial assertions
    if vox_size not in ["1mm", "2mm"]:
        raise ValueError("Voxel size not supported. Use 2mm or 1mm")

    print("Checking inputs...")
    for file_ in [t1w, bvals, bvecs, dwi, atlas, mask, *parcellations]:
        if not os.path.isfile(file_):
            raise FileNotFoundError(f"Input {file_} not found. Exiting m2g.")
        else:
            print(f"Input {file_} found.")

    # time m2g execution
    startTime = datetime.now()

    # initial variables
    outdir = Path(outdir)
    dwi_name = gen_utils.get_filename(dwi)

    # make output directory
    print("Adding directory tree...")
    parcellations = gen_utils.as_list(parcellations)
    gen_utils.make_initial_directories(outdir, parcellations=parcellations)

    # generate list of connectome file locations
    connectomes = []
    for parc in parcellations:
        name = gen_utils.get_filename(parc)
        folder = outdir / f"connectomes/{name}"
        connectome = f"{dwi_name}_{name}_connectome.csv"
        connectomes.append(str(folder / connectome))

    warm_welcome = welcome_message(connectomes)
    print(warm_welcome)

    # -------- Preprocessing Steps --------------------------------- #

    # set up directories
    prep_dwi: Path = outdir / "dwi/preproc"
    eddy_corrected_data: Path = prep_dwi / "eddy_corrected_data.nii.gz"

    # check that skipping eddy correct is possible
    if skipeddy:
        # do it anyway if eddy_corrected_data doesnt exist
        if not eddy_corrected_data.is_file():
            print("Cannot skip preprocessing if it has not already been run!")
            skipeddy = False

    # if we're not skipping eddy correct, perform it
    if not skipeddy:
        prep_dwi = gen_utils.as_directory(prep_dwi, remove=True, return_as_path=True)
        preproc.eddy_correct(dwi, str(eddy_corrected_data), 0)

    # copy bval/bvec files to output directory
    bvec_scaled = str(outdir / "dwi/preproc/bvec_scaled.bvec")
    fbval = str(outdir / "dwi/preproc/bval.bval")
    fbvec = str(outdir / "dwi/preproc/bvec.bvec")
    shutil.copyfile(bvecs, fbvec)
    shutil.copyfile(bvals, fbval)

    # Correct any corrupted bvecs/bvals
    bvals, bvecs = read_bvals_bvecs(fbval, fbvec)
    bvecs[np.where(np.any(abs(bvecs) >= 10, axis=1) == True)] = [1, 0, 0]
    bvecs[np.where(bvals == 0)] = 0
    bvecs_0_loc = np.all(abs(bvecs) == np.array([0, 0, 0]), axis=1)
    if len(bvecs[np.where(np.logical_and(bvals > 50, bvecs_0_loc))]) > 0:
        raise ValueError(
            "WARNING: Encountered potentially corrupted bval/bvecs. Check to ensure volumes with a "
            "diffusion weighting are not being treated as B0's along the bvecs"
        )
    np.savetxt(fbval, bvals)
    np.savetxt(fbvec, bvecs)

    # Rescale bvecs
    print("Rescaling b-vectors...")
    preproc.rescale_bvec(fbvec, bvec_scaled)

    # Check orientation (eddy_corrected_data)
    eddy_corrected_data, bvecs = gen_utils.reorient_dwi(
        eddy_corrected_data, bvec_scaled, prep_dwi
    )

    # Check dimensions
    eddy_corrected_data = gen_utils.match_target_vox_res(
        eddy_corrected_data, vox_size, outdir, sens="dwi"
    )

    # Build gradient table
    print("fbval: ", fbval)
    print("bvecs: ", bvecs)
    print("fbvec: ", fbvec)
    print("eddy_corrected_data: ", eddy_corrected_data)
    gtab, nodif_B0, nodif_B0_mask = gen_utils.make_gtab_and_bmask(
        fbval, fbvec, eddy_corrected_data, prep_dwi
    )

    # Get B0 header and affine
    eddy_corrected_data_img = nib.load(str(eddy_corrected_data))
    hdr = eddy_corrected_data_img.header

    # -------- Registration Steps ----------------------------------- #

    # define registration directory locations
    # TODO: possibly just pull these from a container generated by `gen_utils.make_initial_directories`
    reg_dirs = ["anat/preproc", "anat/registered", "tmp/reg_a", "tmp/reg_m"]
    reg_dirs = [outdir / loc for loc in reg_dirs]
    prep_anat, reg_anat, tmp_rega, tmp_regm = reg_dirs

    if not skipreg:
        for dir_ in [prep_anat, reg_anat]:
            if gen_utils.has_files(dir_):
                gen_utils.as_directory(dir_, remove=True)
        if gen_utils.has_files(tmp_rega) or gen_utils.has_files(tmp_regm):
            for tmp in [tmp_regm, tmp_rega]:
                gen_utils.as_directory(tmp, remove=True)

    # Check orientation (t1w)
    start_time = time.time()
    t1w = gen_utils.reorient_t1w(t1w, prep_anat)
    t1w = gen_utils.match_target_vox_res(t1w, vox_size, outdir, sens="anat")

    print("Running registration in native space...")

    # Instantiate registration
    reg = register.DmriReg(
        outdir, nodif_B0, nodif_B0_mask, t1w, vox_size, skull, simple=False
    )

    # Perform anatomical segmentation
    if skipreg:
        reg.check_gen_tissue_files()
        gen_tissue_files = [reg.t1w_brain, reg.wm_mask, reg.gm_mask, reg.csf_mask]
        existing_files = all(map(os.path.isfile, gen_tissue_files))
        if existing_files:
            print("Found existing gentissue run!")
        else:  # Run if not all necessary files are not found
            reg.gen_tissue()
    else:
        reg.gen_tissue()

    # Align t1w to dwi
    t1w2dwi_align_files = [reg.t1w2dwi, reg.mni2t1w_warp, reg.t1_aligned_mni]
    existing_files = all(map(os.path.isfile, t1w2dwi_align_files))
    if skipreg and existing_files:
        print("Found existing t1w2dwi run!")
    else:
        reg.t1w2dwi_align()

    # Align tissue classifiers
    tissue_align_files = [
        reg.wm_gm_int_in_dwi,
        reg.vent_csf_in_dwi,
        reg.corpuscallosum_dwi,
    ]
    existing_files = all(map(os.path.isfile, tissue_align_files))
    if skipreg and existing_files:
        print("Found existing tissue2dwi run!")
    else:
        reg.tissue2dwi_align()

    # Align atlas to dwi-space and check that the atlas hasn't lost any of the rois
    _ = [reg, parcellations, outdir, prep_anat, vox_size, reg_style]
    labels_im_file_list = reg_utils.skullstrip_check(*_)

    # -------- Tensor Fitting and Fiber Tractography ---------------- #

    # initial path setup
    prep_track: Path = outdir / "dwi/fiber"
    start_time = time.time()
    qa_tensor = str(outdir / "qa/tensor/Tractography_Model_Peak_Directions.png")

    # build seeds
    seeds = track.build_seed_list(reg.wm_gm_int_in_dwi, np.eye(4), dens=int(seeds))
    print("Using " + str(len(seeds)) + " seeds...")

    # Compute direction model and track fiber streamlines
    print("Beginning tractography in native space...")
    # TODO: could add a --skiptrack flag here that checks if `streamlines.trk` already exists to skip to connectome estimation more quickly
    trct = track.RunTrack(
        eddy_corrected_data,
        nodif_B0_mask,
        reg.gm_in_dwi,
        reg.vent_csf_in_dwi,
        reg.csf_mask_dwi,
        reg.wm_in_dwi,
        gtab,
        mod_type,
        track_type,
        mod_func,
        qa_tensor,
        seeds,
        np.eye(4),
    )
    streamlines = trct.run()
    trk_hdr = trct.make_hdr(streamlines, hdr)
    tractogram = nib.streamlines.Tractogram(
        streamlines, affine_to_rasmm=trk_hdr["voxel_to_rasmm"]
    )
    trkfile = nib.streamlines.trk.TrkFile(tractogram, header=trk_hdr)
    streams = os.path.join(prep_track, "streamlines.trk")
    nib.streamlines.save(trkfile, streams)

    print("Streamlines complete")
    print(f"Tractography runtime: {np.round(time.time() - start_time, 1)}")

    if reg_style == "native_dsn":
        fa_path = track.tens_mod_fa_est(gtab, eddy_corrected_data, nodif_B0_mask)
        # Normalize streamlines
        print("Running DSN...")
        streamlines_mni, streams_mni = register.direct_streamline_norm(
            streams, fa_path, outdir
        )
        # Save streamlines to disk
        print("Saving DSN-registered streamlines: " + streams_mni)

    # ------- Connectome Estimation --------------------------------- #
    # Generate graphs from streamlines for each parcellation
    global tracks
    if reg_style == "native":
        tracks = streamlines
    elif reg_style == "native_dsn":
        tracks = streamlines_mni



    for idx, parc in enumerate(parcellations):
        print(f"Generating graph for {parc} parcellation...")
        print(f"Applying native-space alignment to {parcellations[idx]}")
        if reg_style == "native":
            tracks = streamlines
        elif reg_style == "native_dsn":
            tracks = streamlines_mni
        rois = nib.load(labels_im_file_list[idx]).get_fdata().astype(int)
        g1 = graph.GraphTools(
            attr=parcellations[idx],
            rois=rois,
            tracks=tracks,
            affine=np.eye(4),
            outdir=outdir,
            connectome_path=connectomes[idx],
            n_cpus=n_cpus,
        )
        g1.g = g1.make_graph()
        g1.summary()
        g1.save_graph_png(connectomes[idx])
        g1.save_graph(connectomes[idx])


    exe_time = datetime.now() - startTime

    if "M2G_URL" in os.environ:
        print("Note: tractography QA does not work in a Docker environment.")
    else:
        # qa_tractography_out = outdir / "qa/fibers"
        # qa_tractography(streams, str(qa_tractography_out), str(eddy_corrected_data))
        # print("QA tractography Completed.")
        pass

    print(f"Total execution time: {exe_time}")
    print("M2G Complete.")
    print(f"Output contents: {os.listdir(outdir / f'connectomes')}")
    print("~~~~~~~~~~~~~~\n\n")
    print(
        "NOTE :: m2g uses native-space registration to generate connectomes.\n Without post-hoc normalization, multiple connectomes generated with m2g cannot be compared directly."
    )



def welcome_message(connectomes):

    line = """\n~~~~~~~~~~~~~~~~\n 
    Welcome to m2g!\n 
    Your connectomes will be located here:
    \n\n"""

    for connectome in connectomes:
        line += connectome + "\n"

    line += "~~~~~~~~~~~~~~~~\n"

    return line


def main():
    parser = ArgumentParser(
        description="This is an end-to-end connectome estimation pipeline from sMRI and DTI images"
    )
    parser.add_argument("dwi", action="store", help="Nifti dMRI image stack")
    parser.add_argument("bval", action="store", help="DTI scanner b-values")
    parser.add_argument("bvec", action="store", help="DTI scanner b-vectors")
    parser.add_argument("t1w", action="store", help="Nifti T1w MRI image")
    parser.add_argument("atlas", action="store", help="Nifti T1 MRI atlas")
    parser.add_argument(
        "mask",
        action="store",
        help="Nifti binary mask of \
                        brain space in the atlas",
    )
    parser.add_argument(
        "outdir",
        action="store",
        help="Path to which \
                        derivatives will be stored",
    )
    parser.add_argument(
        "labels",
        action="store",
        nargs="*",
        help="Nifti \
                        labels of regions of interest in atlas space",
    )
    parser.add_argument(
        "--vox",
        action="store",
        nargs="*",
        default="1mm",
        help="Voxel size to use for template registrations \
                        (e.g. '1mm')",
    )
    parser.add_argument(
        "--mod",
        action="store",
        help="Determinstic (det) or probabilistic (prob) tracking. Default is det.",
        default="det",
    )
    parser.add_argument(
        "--tt",
        action="store",
        help="Tracking approach: eudx or local. Default is eudx.",
        default="eudx",
    )
    parser.add_argument(
        "--mf",
        action="store",
        help="Diffusion model: csd or csa. Default is csa.",
        default="csa",
    )
    parser.add_argument(
        "--sp",
        action="store",
        help="Space for tractography. Default is native.",
        default="native",
    )
    parser.add_argument(
        "-sked",
        "--sked",
        action="store_true",
        default=False,
        help="whether or not to skip eddy correction",
    )
    parser.add_argument(
        "-skreg",
        "--skreg",
        action="store_true",
        default=False,
        help="whether or not to skip registration",
    )
    result = parser.parse_args()

    # Create output directory
    print(f"Creating output directory: {result.outdir}")
    print(f"Creating output temp directory: {result.outdir}/tmp")
    outdir_tmp = Path(result.outdir) / "tmp"
    outdir_tmp.mkdir(parents=True, exist_ok=True)

    m2g_dwi_worker(
        result.dwi,
        result.bval,
        result.bvec,
        result.t1w,
        result.atlas,
        result.mask,
        result.labels,
        result.outdir,
        result.vox,
        result.mod,
        result.tt,
        result.mf,
        result.sp,
        result.seeds,
        result.skipeddy,
        result.skipreg,
    )


if __name__ == "__main__":
    main()
