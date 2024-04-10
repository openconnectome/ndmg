#!/usr/bin/env python

"""
m2g.scripts.m2g_dwi_pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Contains the primary, top-level pipeline.
For a full description, see here: https://neurodata.io/talks/ndmg.pdf
"""


# multithreading
import multiprocessing as mp
import os

# standard library imports
import shutil
import time
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from subprocess import Popen

# package imports
import nibabel as nib
import numpy as np
from dipy.io import read_bvals_bvecs
from dipy.tracking.streamline import Streamlines

# m2g imports
from m2g import graph, preproc, register, track
from m2g.stats.qa_tractography import qa_tractography
from m2g.utils import cloud_utils, gen_utils, reg_utils

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
    if vox_size not in ["1mm", "2mm", "4mm"]:
        raise ValueError("Voxel size not supported. Use 4mm, 2mm, or 1mm")

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

    # make output directory
    print("Adding directory tree...")
    parcellations = gen_utils.as_list(parcellations)
    init_dirs = gen_utils.make_initial_directories(
        outdir, dwi, parcellations=parcellations
    )

    warm_welcome = welcome_message(init_dirs["connectomes"])
    print(warm_welcome)

    # -------- Preprocessing Steps --------------------------------- #

    # set up directories
    # prep_dwi: Path = outdir / "dwi/preproc"
    eddy_corrected_data: Path = init_dirs["dwi_dirs"][1] / "eddy_corrected_data.nii.gz"

    # check that skipping eddy correct is possible
    if skipeddy:
        # do it anyway if eddy_corrected_data doesnt exist
        if not eddy_corrected_data.is_file():
            print("Cannot skip preprocessing if it has not already been run!")
            skipeddy = False

    # if we're not skipping eddy correct, perform it
    if not skipeddy:
        init_dirs["dwi_dirs"][1] = gen_utils.as_directory(
            init_dirs["dwi_dirs"][1], remove=True, return_as_path=True
        )
        preproc.eddy_correct(dwi, str(eddy_corrected_data), 0)

    # copy bval/bvec files to output directory
    bvec_scaled = str(init_dirs["dwi_dirs"][1] / "bvec_scaled.bvec")
    fbval = str(init_dirs["dwi_dirs"][1] / "bval.bval")
    fbvec = str(init_dirs["dwi_dirs"][1] / "bvec.bvec")
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
        eddy_corrected_data, bvec_scaled, init_dirs["dwi_dirs"][1]
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
        fbval, fbvec, eddy_corrected_data, init_dirs["dwi_dirs"][1]
    )

    # Get B0 header and affine
    eddy_corrected_data_img = nib.load(str(eddy_corrected_data))
    hdr = eddy_corrected_data_img.header

    # -------- Registration Steps ----------------------------------- #

    # define registration directory locations
    # TODO: possibly just pull these from a container generated by `gen_utils.make_initial_directories`
    # reg_dirs = ["anat/preproc", "anat/registered", "tmp/reg_a", "tmp/reg_m"]
    # reg_dirs = [outdir / loc for loc in reg_dirs]
    prep_anat = init_dirs["anat_dirs"][0]
    reg_anat = init_dirs["anat_dirs"][1]
    tmp_rega = init_dirs["tmp_dirs"][0]
    tmp_regm = init_dirs["tmp_dirs"][1]

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
    t1w = gen_utils.match_target_vox_res(t1w, vox_size, outdir, sens="anat_d")

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
    # prep_track: Path = outdir / "dwi/fiber"
    prep_track = init_dirs["dwi_dirs"][0]
    start_time = time.time()
    qa_tensor = str(init_dirs["qa_dirs"][6] / "/Tractography_Model_Peak_Directions.png")

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

    # TODO: Get rid of native_dsn once and for all?
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
        # rois = nib.load(labels_im_file_list[idx]).get_fdata().astype(int)
        g1 = graph.GraphTools(
            attr=parcellations[idx],
            rois=labels_im_file_list[idx],  # rois,
            tracks=tracks,
            affine=np.eye(4),
            outdir=outdir,
            connectome_path=init_dirs["connectomes"][idx],
            n_cpus=n_cpus,
        )
        g1.g = g1.make_graph()
        g1.summary()
        g1.save_graph_png(init_dirs["qa_dirs"][3], init_dirs["connectomes"][idx])
        g1.save_graph(init_dirs["connectomes"][idx])

    exe_time = datetime.now() - startTime

    # if "M2G_URL" in os.environ:
    #     print("Note: tractography QA does not work in a Docker environment.")
    # else:
    #     # TODO: Check that this still works
    #     qa_tractography_out = outdir / "qa/fibers"
    #     qa_tractography(streams, str(qa_tractography_out), str(eddy_corrected_data))
    #     print("QA tractography Completed.")
    #     pass

    print(f"Total execution time: {exe_time}")
    print("M2G Complete.")
    print(f"Connectome Locations: {init_dirs['connectomes']}")
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
