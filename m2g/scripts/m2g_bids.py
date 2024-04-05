#!/usr/bin/env python

"""
m2g.scripts.m2g_bids
~~~~~~~~~~~~~~~~~~~~~~

The top level m2g entrypoint module.
In this module, m2g:
1. Pulls data into the input directory from s3 if we need it.
2. Parses the input directory.
3. for each subject/session pair, runs m2g_dwi_pipeline.m2g_dwi_worker (the actual pipeline)
"""


# standard library imports
import sys
import shutil
import glob
import os
from argparse import ArgumentParser
import numpy as np
from numpy import genfromtxt
import re

# m2g imports
from m2g.utils import cloud_utils
from m2g.utils import gen_utils
from m2g.utils.gen_utils import DirectorySweeper
from m2g.utils.gen_utils import check_dependencies
from m2g.utils.gen_utils import is_bids
from m2g.utils.gen_utils import as_directory
from m2g.scripts.m2g_dwi_pipeline import m2g_dwi_worker
from m2g.functional.m2g_func import m2g_func_worker, func_dir_reorg


def get_atlas(atlas_dir, vox_size):
    """Given the desired location of atlases and the type of processing, ensure we have all the atlases and parcellations.

    Parameters
    ----------
    atlas_dir : str
        Path to directory containing atlases.
    vox_size : str
        t1w input image voxel dimensions, either 2mm or 1mm

    Returns
    -------
    tuple
        filepaths corresponding to the human parcellations, the atlas, and the atlas's mask. atals_brain and lv_mask is None if not fmri.

    Raises
    ------
    ValueError
        raised if dimensionality is wrong.
    NotImplementedError
        currently raised in lieu of atlas pulling capabilities.
    """
    if vox_size == "2mm":
        dims = "2x2x2"
    elif vox_size == "1mm":
        dims = "1x1x1"
    elif vox_size == "4mm":
        dims = "4x4x4"
    else:
        raise ValueError(
            "Voxel dimensions of input t1w image not currently supported by m2g."
        )

    # grab atlases if they don't exist
    if not os.path.exists(atlas_dir):
        # TODO : re-implement this pythonically with shutil and requests in python3.
        print("atlas directory not found. Cloning ...")
        clone = "https://github.com/neurodata/neuroparc.git"
        gen_utils.run(f"git clone {clone} {atlas_dir}")

    atlas = os.path.join(
        atlas_dir, "atlases/reference_brains/MNI152NLin6_res-" + dims + "_T1w.nii.gz"
    )
    atlas_mask = os.path.join(
        atlas_dir,
        "atlases/mask/MNI152NLin6_res-" + dims + "_T1w_descr-brainmask.nii.gz",
    )
    parcellations = [
        i for i in glob.glob(atlas_dir + "/atlases/label/Human/*.nii.gz") if dims in i
    ]
    parcellations = [os.path.join(atlas_dir, "label/Human/", l) for l in parcellations]

    assert all(map(os.path.exists, parcellations)), "Some parcellations do not exist."
    assert all(
        map(os.path.exists, [atlas, atlas_mask])
    ), "atlas or atlas_mask, does not exist."
    return parcellations, atlas, atlas_mask


def get_atlas_dir():
    """
    Gets the location of m2g's atlases.

    Returns
    -------
    str
        atlas directory location.
    """
    if os.path.isdir("/m2g_atlases"):
        return "/m2g_atlases"  # in docker

    return os.path.expanduser("~") + "/.m2g/m2g_atlases"  # local


def main():
    """Starting point of the m2g pipeline, assuming that you are using a BIDS organized dataset"""
    parser = ArgumentParser(
        description="This is an end-to-end connectome estimation pipeline from fMRI and diffusion weighted MRI data."
    )
    parser.add_argument(
        "input_dir",
        help="""The directory with the input dataset
        formatted according to the BIDS standard.
        To use data from s3, put the bucket and directory location as the input directory:
        `s3://<bucket>/<dataset>`
        downloaded file will be stored in ~/.m2g/input. If directory already exists it will be deleted.""",
    )
    parser.add_argument(
        "output_dir",
        help="""The local directory where the output
        files should be stored.""",
    )
    parser.add_argument(
        "--participant_label",
        help="""The label(s) of the
        participant(s) that should be analyzed. The label
        corresponds to sub-<participant_label> from the BIDS
        spec (so it does not include "sub-"). If this
        parameter is not provided all subjects should be
        analyzed. Multiple participants can be specified
        with a space separated list.""",
        nargs="+",
    )
    parser.add_argument(
        "--session_label",
        help="""The label(s) of the
        session that should be analyzed. The label
        corresponds to ses-<participant_label> from the BIDS
        spec (so it does not include "ses-"). If this
        parameter is not provided all sessions should be
        analyzed. Multiple sessions can be specified
        with a space separated list.""",
        nargs="+",
    )
    parser.add_argument(
        "--pipeline",
        action="store",
        help="""Pipline to use when analyzing the input data, 
        either func, dwi, or both. Default is dwi.""",
        default="dwi",
    )
    parser.add_argument(
        "--acquisition",
        action="store",
        help="""Acquisition method for functional data:
        altplus - Alternating in the +z direction
        alt+z - Alternating in the +z direction
        alt+z2 - Alternating, but beginning at slice #1
        altminus - Alternating in the -z direction
        alt-z - Alternating in the -z direction
        alt-z2 - Alternating, starting at slice #nz-2 instead of #nz-1
        seqplus - Sequential in the plus direction
        seqminus - Sequential in the minus direction,
        default is alt+z. For more information:https://fcp-indi.github.io/docs/user/func.html""",
        default="alt+z",
    )
    parser.add_argument(
        "--tr",
        action="store",
        help="functional scan TR (seconds), default is 2.0",
        default=2.0,
    )
    parser.add_argument(
        "--push_location",
        action="store",
        help="Name of folder on s3 to push output data to, if the folder does not exist, it will be created."
        "Format the location as `s3://<bucket>/<path>`",
        default=None,
    )
    parser.add_argument(
        "--parcellation",
        action="store",
        help="""The parcellation(s) being analyzed. Multiple parcellations can be provided with a space separated list.
        If not parcellations are defined, will use all parcellations from neuroparc.""",
        nargs="+",
        default=None,
    )
    parser.add_argument(
        "--skipeddy",
        action="store_true",
        help="Whether to skip eddy correction if it has already been run and the files can be found in output_dir.",
        default=False,
    )
    parser.add_argument(
        "--skipreg",
        action="store_true",
        default=False,
        help="Shether to skip registration of the parcellations if it has already been run and the files can be fround in output_dir",
    )
    parser.add_argument(
        "--voxelsize",
        action="store",
        default="2mm",
        help="Voxel size : 2mm, 1mm. Voxel size of both parcellation and reference structural image to use for template registrations.",
    )
    parser.add_argument(
        "--mod",
        action="store",
        help="Deterministic (det) or probabilistic (prob) tracking method for the dwi tractography. Default is det.",
        default="det",
    )
    parser.add_argument(
        "--track_type",
        action="store",
        help="Tracking approach: local, particle. Default is local.",
        default="local",
    )
    parser.add_argument(
        "--diffusion_model",
        action="store",
        help="Diffusion model: csd or csa. Default is csa.",
        default="csa",
    )
    parser.add_argument(
        "--space",
        action="store",
        help="Space for tractography: native, native_dsn. Default is native.",
        default="native",
    )
    parser.add_argument(
        "--seeds",
        action="store",
        help="Seeding density for tractography in the m2g-d pipeline. Default is 20.",
        default=20,
    )
    parser.add_argument(
        "--skull",
        action="store",
        help="""Special actions to take when skullstripping t1w image based on default skullstrip ('none') failure:
        Excess tissue below brain: below
        Chunks of cerebelum missing: cerebelum
        Frontal clipping near eyes: eye
        Excess clipping in general: general,""",
        default=None,
    )
    parser.add_argument(
        "--mem_gb",
        action="store",
        help="Memory, in GB, to allocate to functional pipeline",
        default=20,
    )
    parser.add_argument(
        "--n_cpus",
        action="store",
        help="Number of cpus to allocate to either the functional pipeline or the diffusion connectome generation",
        default=1,
    )
    result = parser.parse_args()

    # and ... begin!
    print("\nBeginning m2g ...")

    # ---------------- Parse CLI arguments ---------------- #
    input_dir = result.input_dir
    output_dir = result.output_dir
    subjects = result.participant_label
    sessions = result.session_label
    pipe = result.pipeline
    acquisition = result.acquisition  # functional pipeline settings
    mem_gb = result.mem_gb  # functional pipeline settings
    n_cpus = result.n_cpus
    tr = result.tr  # functional pipeline settings
    parcellation_name = result.parcellation
    push_location = result.push_location

    # arguments to be passed in every m2g run
    # TODO : change value naming convention to match key naming convention
    constant_kwargs = {
        "vox_size": result.voxelsize,
        "mod_type": result.mod,
        "track_type": result.track_type,
        "mod_func": result.diffusion_model,
        "seeds": result.seeds,
        "reg_style": result.space,
        "skipeddy": result.skipeddy,
        "skipreg": result.skipreg,
        "skull": result.skull,
        "n_cpus": result.n_cpus,
    }

    # ---------------- S3 stuff ---------------- #
    # grab s3 stuff
    s3 = input_dir.startswith("s3://")
    creds = bool(cloud_utils.get_credentials())
    if s3:
        buck, remo = cloud_utils.parse_path(input_dir)
        home = os.path.expanduser("~")
        input_dir = as_directory(home + "/.m2g/input", remove=True)
        if (not creds) and push_location:
            raise AttributeError(
                """No AWS credentials found, but "--push_location" flag called. 
                Pushing will most likely fail."""
            )

        # Get S3 input data if needed
        # TODO : `Flat is better than nested`. Make the logic for this cleaner
        if subjects is not None:
            for subject in subjects:
                if sessions is not None:
                    for session in sessions:
                        info = f"sub-{subject}/ses-{session}"
                        cloud_utils.s3_get_data(buck, remo, input_dir, info=info)
                else:
                    info = f"sub-{subject}"
                    cloud_utils.s3_get_data(buck, remo, input_dir, info=info)
        else:
            info = "sub-"
            cloud_utils.s3_get_data(buck, remo, input_dir, info=info)

    # ---------------- Pre-run checks ---------------- #
    # check operating system compatibility
    compatible = sys.platform == "darwin" or sys.platform == "linux"
    if not compatible:
        input(
            "\n\nWARNING: You appear to be running m2g on an operating system that is not macOS or Linux."
            "\nm2g has not been tested on this operating system and may not work. Press enter to continue.\n\n"
        )

    # make sure we have AFNI and FSL
    check_dependencies()
    # make sure input directory is BIDs-formatted
    assert is_bids(input_dir)

    print(
        f"""
        input directory location: {input_dir}. 
        Input directory contents: {os.listdir(input_dir)}.
        """
    )

    # ---------------- Grab parcellations, atlases, mask --------------- #
    # TODO: Test that you can locate parcellations elsewhere
    # get parcellations, atlas, and mask, then stick it into constant_kwargs
    atlas_dir = get_atlas_dir()
    (
        parcellations,
        atlas,
        mask,
    ) = get_atlas(atlas_dir, constant_kwargs["vox_size"])
    if parcellation_name is not None:  # filter parcellations
        parcellations = [
            file_
            for file_ in parcellations
            for parc in parcellation_name
            if parc in file_
        ]
    # Check if parcellations is empty
    if len(parcellations) == 0:
        raise ValueError("No valid parcellations found.")

    atlas_info = {"atlas": atlas, "mask": mask, "parcellations": parcellations}

    # ------- Check if they have selected the functional pipeline ------ #
    if pipe == "func" or pipe == "both":

        sweeper = DirectorySweeper(
            input_dir, subjects=subjects, sessions=sessions, pipeline="func"
        )
        scans = sweeper.get_dir_info(pipeline="func")

        home = os.path.expanduser("~")
        if not os.path.exists(home + "/.m2g"):
            os.makedirs(f"{home}/.m2g")

        for SubSesFile in scans:
            subject, session, files = SubSesFile
            # add subject and session folders to output
            outDir = f"{output_dir}/sub-{subject}/ses-{session}"

            m2g_func_worker(
                input_dir,
                outDir,
                subject,
                session,
                files["t1w"],
                files["func"],
                constant_kwargs["vox_size"],
                parcellations,
                acquisition,
                tr,
                mem_gb,
                n_cpus,
            )

            print(
                f"""
                Functional Pipeline completed!
                """
            )
            # Reorganize output files from CPAC to a more user-friendly version
            func_dir_reorg(outDir)

            if push_location:
                print(f"Pushing to s3 at {push_location}.")
                push_buck, push_remo = cloud_utils.parse_path(push_location)
                cloud_utils.s3_push_data(
                    push_buck,
                    push_remo,
                    output_dir,
                    subject=subject,
                    session=session,
                    creds=creds,
                )
        if pipe != "both":
            sys.exit(0)

    # ------------ Continue DWI pipeline ------------ #

    constant_kwargs.update(atlas_info)
    # parse input directory
    sweeper = DirectorySweeper(input_dir, subjects=subjects, sessions=sessions)
    scans = sweeper.get_dir_info()

    # ---------------- Run Pipeline --------------- #
    # run m2g on the entire BIDs directory.
    for SubSesFile in scans:
        subject, session, kwargs = SubSesFile
        kwargs["outdir"] = f"{output_dir}/sub-{subject}/ses-{session}"
        kwargs.update(constant_kwargs)
        m2g_dwi_worker(**kwargs)
        if push_location:
            print(f"Pushing to s3 at {push_location}.")
            push_buck, push_remo = cloud_utils.parse_path(push_location)
            cloud_utils.s3_push_data(
                push_buck,
                push_remo,
                output_dir,
                subject=subject,
                session=session,
                creds=creds,
            )


if __name__ == "__main__":
    main()
