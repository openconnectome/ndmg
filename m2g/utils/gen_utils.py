# !/usr/bin/env python

"""
m2g.utils.gen_utils
~~~~~~~~~~~~~~~~~~~~

Contains general utility functions.
"""

import functools
import json
# system imports
import os
import re
import shutil
import subprocess
import sys
import time
from collections import namedtuple
from pathlib import Path

# package imports
import bids
import dipy
import nibabel as nib
import numpy as np
from dipy.align.reslice import reslice
from dipy.core.gradients import gradient_table
from dipy.io import read_bvals_bvecs
from fury import actor, window
from nilearn.image import mean_img
from scipy.sparse import lil_matrix


class DirectorySweeper:
    """
    Class for parsing through a BIDs-formatted directory tree.

    Parameters
    ----------
    bdir : str
        BIDs-formatted directory containing dwi data.
    subjects : list or str, optional
        The subjects to run m2g on.
        If None, parse through the whole directory.
    sessions : list or str, optional
        The sessions to run m2g with.
        If None, use every possible session.
    pipeline : str, optional
        The pipeline you are using, 'func' or 'dwi', default is 'dwi'
    """

    def __init__(self, bdir, subjects=None, sessions=None, pipeline="dwi"):
        self.bdir = bdir
        self.layout = bids.BIDSLayout(bdir)
        if subjects is None:
            subjects = self.layout.get_subjects()
        if sessions is None:
            sessions = self.layout.get_sessions()

        # get list of subject / session pairs
        self.pairs = self.get_pairs(
            subjects=subjects, sessions=sessions, pipeline=pipeline
        )

    def __repr__(self):
        return str(self.layout)

    def get_pairs(self, subjects, sessions, pipeline="dwi"):
        """
        Return subject/session pairs.

        Parameters
        ----------
        subjects : str or list
            Subjects to retrieve.
        sessions : str or list
            Sessions to retrieve.
        pipeline : str, optional
        The pipeline you are using, 'func' or 'dwi', default is 'dwi'

        Returns
        -------
        list
            List of subject, session pairs.
            Formatted like: [(subject, session), (subject, session), ...].
        """
        pairs = []
        # Change suffix to be 'bold' because prefixes aren't a thing
        if pipeline == "func":
            pipeline = "bold"

        kwargs = dict(
            suffix=pipeline,
            extension=["nii", "nii.gz"],
            subject=subjects,
            session=sessions,
        )

        for entity in self.layout.get(**kwargs):
            subject = entity.entities["subject"]
            session = entity.entities["session"]
            pairs.append((subject, session))
        if len(pairs) == 0:
            raise ValueError(f"No pairs found for {self}")
        return pairs

    def get_files(self, subject, session, pipeline="dwi"):
        """
        Retrieve all relevant files from a dataframe.

        Parameters
        ----------
        subject : str
            Subject to get files for.
        session : str
            Session to get files for.
        pipeline : str, optional
        The pipeline you are using, 'func' or 'dwi', default is 'dwi'

        Returns
        -------
        dict
            Dictionary of all files from a single session.
        """

        if pipeline == "func":
            func = self.layout.get(
                return_type="filename", session=session, subject=subject, suffix="bold"
            )
            if (
                len(func) == 1
            ):  # TODO:Account for one or multiple functional scans per anatomical image
                [func] = func
            [anat] = self.layout.get(
                return_type="filename",
                session=session,
                subject=subject,
                suffix=["T1w", "t1w"],
            )
            files = {"func": func, "t1w": anat}
        else:  # TODO: allow for more than one dwi scan to exist in the dwi directory for processing
            bval, bvec, dwi = self.layout.get(
                return_type="filename", session=session, subject=subject, suffix="dwi"
            )
            [anat] = self.layout.get(
                return_type="filename", session=session, subject=subject, suffix="T1w"
            )
            files = {"dwi": dwi, "bvals": bval, "bvecs": bvec, "t1w": anat}

        return files

    def get_dir_info(self, pipeline="dwi"):
        """
        Parse an entire BIDSLayout for scan parameters.

        Parameters
        ----------
        pipeline : str, optional
        The pipeline you are using, 'func' or 'dwi', default is 'dwi'

        Returns
        -------
        list
            List of SubSesFiles namedtuples.
            SubSesFile.files is a dictionary of files.
            SubSesFile.subject is the subject string.
            SubSesFile.session is the session string.
        """

        scans = []
        SubSesFiles = namedtuple("SubSesFiles", ["subject", "session", "files"])

        # remove duplicate subject/session pairs for either
        self.pairs = list(set(self.pairs))
        # append subject, session, and files for each relevant session to scans
        for subject, session in self.pairs:
            files = self.get_files(subject, session, pipeline=pipeline)
            scan = SubSesFiles(subject, session, files)
            scans.append(scan)

            if not scan.files:
                print(
                    f""""
                    There were no files for
                    subject {subject}, session {session}.
                    """
                )

        return scans


def make_initial_directories(outdir: Path, dwi: Path, parcellations=[]) -> None:
    """
    Make starting directory tree.

    Parameters
    ----------
    outdir : Path
        Output directory of the form Path(<dir>/sub-<n>/ses-<m>/)
    dwi : Path
        Path to dwi directory/files
    parcellations : list, optional
        Set of all parcellations we're using, by default []
    """

    # populate connectome_dir with folder for each parcellation
    connectome_dirs = []
    for parc in parcellations:
        name = get_filename(parc)
        p = str(f"connectomes_d/{name}")
        connectome_dirs.append(p)

    init_dirs = {
        "anat_dirs": ["anat_d/preproc", "anat_d/registered"],
        "dwi_dirs": ["dwi/fiber", "dwi/preproc", "dwi/tensor"],
        "qa_dirs": [
            "qa_d/adjacency",
            "qa_d/fibers",
            "qa_d/graphs",
            "qa_d/graphs_plotting",
            "qa_d/mri",
            "qa_d/reg",
            "qa_d/tensor",
        ],
        "tmp_dirs": ["tmp_d/reg_a", "tmp_d/reg_m"],
        "connectome_dirs": connectome_dirs,
        "connectomes": [],
    }

    # create directories
    for cat in init_dirs:
        replace = []
        for p in init_dirs[cat]:
            full_path = outdir / p
            full_path.mkdir(parents=True, exist_ok=True)
            replace.append(full_path)
        init_dirs[cat] = replace

    init_dirs["outdir"] = outdir

    # generate list of connectome file locations
    dwi_name = get_filename(dwi)
    connectomes = []
    for parc in parcellations:
        name = get_filename(parc)
        folder = outdir / f"connectomes_d/{name}"
        connectome = f"{dwi_name}_{name}_connectome.csv"
        connectomes.append(str(folder / connectome))

    init_dirs["connectomes"] = connectomes

    return init_dirs


def has_files(dirname: Path):
    dirname = Path(dirname)
    if dirname.exists() and dirname.is_dir():
        if os.listdir(dirname):
            return True
    return False


def as_directory(dir_, remove=False, return_as_path=False):
    """
    Convenience function to make a directory while returning it.

    Parameters
    ----------
    dir_ : str, Path
        File location to directory.
    remove : bool, optional
        Whether to remove a previously existing directory, by default False

    Returns
    -------
    str
        Directory string.
    """
    p = Path(dir_).absolute()

    if remove:
        print(f"Previous directory found at {dir_}. Removing.")
        shutil.rmtree(p, ignore_errors=True)
    p.mkdir(parents=True, exist_ok=True)

    if return_as_path:
        return p

    return str(p)


def as_list(x):
    """A function to convert an item to a list if it is not, or pass it through otherwise

    Parameters
    ----------
    x : any object
        anything that can be entered into a list that you want to be converted into a list

    Returns
    -------
    list
        a list containing x
    """

    if isinstance(x, list):
        return x

    return [x]


def merge_dicts(x, y):
    """A function to merge two dictionaries, making it easier for us to make modality specific queries
    for dwi images (since they have variable extensions due to having an nii.gz, bval, and bvec file)

    Parameters
    ----------
    x : dict
        dictionary you want merged with y
    y : dict
        dictionary you want merged with x

    Returns
    -------
    dict
        combined dictionary with {x content,y content}
    """

    z = x.copy()
    z.update(y)
    return z


def print_arguments(inputs=[], outputs=[]):
    # NOTE : any functions decorated with this go here first when you set a breakpoint in the debugger.
    #        To debug the function itself, step into the line that calls the decorated function (f(*args, **kwargs)).
    """
    Decorator. Standardizes print statements across functions by printing arguments to stdout. Checks input files for existence.

    Parameters
    ----------
    inputs : List[int]
        Set of integer locations of file inputs to functions.

    outputs : List[int]
        Set of integer locations of locations of file outputs generated by functions.

    Raises
    ------
    ValueError
        Raised if the input file at that location doesn't exist.

    Returns
    -------
    func
        decorated function.
    """

    def outer(f):
        @functools.wraps(f)
        def inner(*args, **kwargs):
            print("\n")
            all_args = list(args) + list(kwargs.values())

            if inputs:
                print(f"Checking inputs for {f.__name__} ...")
            for input_ in inputs:
                p = all_args[input_]
                if not os.path.exists(p):
                    raise FileNotFoundError(f"Input {p} does not exist.")
                print(f"Input {p} found.")

            for output_ in outputs:
                p = all_args[output_]
                print(f"Output will exist at {p}.")

            print(f"Calling {f.__name__}.")
            function_out = f(*args, **kwargs)
            print("\n")
            return function_out

        return inner

    return outer


def timer(f):
    # NOTE : any functions decorated with this go here first when you set a breakpoint in the debugger.
    #        To debug the function itself, step into the line that calls the decorated function (f(*args, **kwargs)).
    """Print the runtime of the decorated function"""

    @functools.wraps(f)
    def wrapper_timer(*args, **kwargs):
        start_time = time.perf_counter()
        func = f(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time
        print(f"Function {f.__name__!r} finished in {run_time:.4f} secs")
        return func

    return wrapper_timer


def is_bids(input_dir):
    """
    Make sure that the input data is BIDs-formatted.
    If it's BIDs-formatted, except for a `dataset_description.json` file, return True.

    Returns
    -------
    bool
        True if the input directory is BIDs-formatted

    Raises
    ------
    ValueError
        Occurs if the input directory is not formatted properly.
    """
    try:
        l = bids.BIDSLayout(input_dir)
        return l.validate
    except ValueError as e:
        p = "dataset_description.json"
        if p not in str(e):
            raise ValueError(e)
        create_datadescript(input_dir)
        return is_bids(input_dir)


def create_datadescript(input_dir):
    """
    Creates a simple `data_description.json` file in the root of the input directory. Necessary for proper BIDs formatting.

    Parameters
    ----------
    input_dir : str
        BIDs-formatted input director.
    """
    print(f"Creating a simple dataset_description.json in {input_dir}... ")
    name = Path(input_dir).stem
    vers = bids.__version__
    out = dict(Name=name, BIDSVersion=vers)
    with open(input_dir + "/dataset_description.json", "w") as f:
        json.dump(out, f)


def check_dependencies():
    """
    Check for the existence of FSL and AFNI.
    Stop the pipeline immediately if these dependencies are not installed.

    Raises
    ------
    AssertionError
        Raised if FSL is not installed.
    AssertionError
        Raised if AFNI is not installed.
    """

    # Check for python version
    print(f"Python location : {sys.executable}")
    print(f"Python version : {sys.version}")
    print(f"DiPy version : {dipy.__version__}")
    if sys.version_info[0] < 3:
        print(
            "WARNING : Using python 2. This Python version is no longer maintained. Use at your own risk."
        )

    # Check FSL installation
    try:
        print(f"Your fsl directory is located here: {os.environ['FSLDIR']}")
    except KeyError:
        raise AssertionError(
            "You do not have FSL installed! See installation instructions here: https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation"
        )

    # Check AFNI installation
    try:
        print(
            f"Your AFNI directory is located here: {subprocess.check_output('which afni', shell=True, universal_newlines=True)}"
        )
    except subprocess.CalledProcessError:
        raise AssertionError(
            "You do not have AFNI installed! See installation instructions here: https://afni.nimh.nih.gov/pub/dist/doc/htmldoc/background_install/main_toc.html"
        )


def run(cmd):
    # TODO: subprocess.run can take in lists, so could do a check with `isinstance` to allow running a command as a list
    """
    Wrapper on `subprocess.run`.
    Print the command.
    Execute a command string on the shell (on bash).
    Exists so that the shell prints out commands as m2g calls them.

    Parameters
    ----------
    cmd : str
        Command to be sent to the shell.
    """
    print(f"Running shell command: {cmd}")
    subprocess.run(cmd, shell=True, check=True)


def show_template_bundles(final_streamlines, template_path, fname):
    """Displayes the template bundles

    Parameters
    ----------
    final_streamlines : list
        Generated streamlines
    template_path : str
        Path to reference FA nii.gz file
    fname : str
        Path of the output file (saved as )
    """

    renderer = window.Renderer()
    template_img_data = nib.load(template_path).get_data().astype("bool")
    template_actor = actor.contour_from_roi(
        template_img_data, color=(50, 50, 50), opacity=0.05
    )
    renderer.add(template_actor)
    lines_actor = actor.streamtube(
        final_streamlines, window.colors.orange, linewidth=0.3
    )
    renderer.add(lines_actor)
    window.record(renderer, n_frames=1, out_path=fname, size=(900, 900))


def get_braindata(brain_file):
    """Opens a brain data series for a mask, mri image, or atlas.
    Returns a numpy.ndarray representation of a brain.

    Parameters
    ----------
    brain_file : str, nibabel.nifti1.nifti1image, numpy.ndarray
        an object to open the data for a brain. Can be a string (path to a brain file),
        nibabel.nifti1.nifti1image, or a numpy.ndarray

    Returns
    -------
    array
        array of image data

    Raises
    ------
    TypeError
        Brain file is not an accepted format
    """

    if type(brain_file) is np.ndarray:  # if brain passed as matrix
        braindata = brain_file
    else:
        if type(brain_file) is str or type(brain_file) is str:
            brain = nib.load(str(brain_file))
        elif type(brain_file) is nib.nifti1.Nifti1Image:
            brain = brain_file
        else:
            raise TypeError(
                f"Brain file is type: {type(brain_file)}"
                f"; accepted types are numpy.ndarray, "
                f"string, and nibabel.nifti1.Nifti1Image."
            )
        braindata = brain.get_data()
    return braindata


def get_filename(path):
    """Given a fully qualified path, return just the file name, without extension

    Parameters
    ----------
    path : str
        Path to file you want isolated

    Returns
    -------
    str
        File name
    """
    return os.path.basename(path).split(".")[0]


def get_slice(mri, volid, sli):
    """Takes a volume index and constructs a new nifti image from the specified volume

    Parameters
    ----------
    mri : str
        Path to the 4d mri volume you wish to extract a slice from
    volid : int
        The index of the volume desired
    sli : str
        Path for the resulting file containing the desired slice
    """

    mri_im = nib.load(mri)
    data = mri_im.get_data()
    # get the slice at the desired volume
    vol = np.squeeze(data[:, :, :, volid])

    # Wraps volume in new nifti image
    head = mri_im.get_header()
    head.set_data_shape(head.get_data_shape()[0:3])
    out = nib.Nifti1Image(vol, affine=mri_im.get_affine(), header=head)
    out.update_header()
    # and saved to a new file
    nib.save(out, sli)


@timer
@print_arguments(inputs=[0, 1, 2], outputs=[3])
def make_gtab_and_bmask(fbval: str, fbvec: str, dwi_file: str, preproc_dir: Path):
    """Takes bval and bvec files and produces a structure in dipy format while also using FSL commands

    Parameters
    ----------
    fbval : str
        Path to b-value file
    fbvec : str
        Path to b-vector file
    dwi_file : str
        Path to dwi file being analyzed
    preproc_dir : Path
        Path to <outdir>/dwi/preproc

    Returns
    -------
    GradientTable
        gradient table created from bval and bvec files
    str
        location of averaged b0 image file
    str
        location of b0 brain mask file
    """

    # Use B0's from the DWI to create a more stable DWI image for registration
    nodif_B0 = f"{preproc_dir}/nodif_B0.nii.gz"
    nodif_B0_bet = f"{preproc_dir}/nodif_B0_bet.nii.gz"
    nodif_B0_mask = f"{preproc_dir}/nodif_B0_bet_mask.nii.gz"

    # loading bvecs/bvals
    print(fbval)
    print(fbvec)
    bvals, bvecs = read_bvals_bvecs(fbval, fbvec)

    # Creating the gradient table
    gtab = gradient_table(bvals, bvecs, atol=1.0)

    # Correct b0 threshold
    gtab.b0_threshold = min(bvals)

    # Get B0 indices
    B0s = np.where(gtab.bvals == gtab.b0_threshold)[0]
    print(f"B0s found at: {B0s}")

    # Show info
    print(gtab.info)

    # Extract and Combine all B0s collected
    print("Extracting B0's...")
    cmds = []
    B0s_bbr = []
    for B0 in B0s:
        print(B0)
        B0_bbr = f"{preproc_dir}/{str(B0)}_B0.nii.gz"
        cmd = f"fslroi {dwi_file} {B0_bbr} {str(B0)} 1"
        cmds.append(cmd)
        B0s_bbr.append(B0_bbr)

    for cmd in cmds:
        print(cmd)
        run(cmd)

    # Get mean B0
    B0s_bbr_imgs = []
    for B0 in B0s_bbr:
        B0s_bbr_imgs.append(nib.load(B0))

    mean_B0 = mean_img(B0s_bbr_imgs)
    nib.save(mean_B0, nodif_B0)

    # Get mean B0 brain mask
    cmd = f"bet {nodif_B0} {nodif_B0_bet} -m -f 0.2"
    run(cmd)
    return gtab, nodif_B0_bet, nodif_B0_mask


def normalize_xform(img):
    """Set identical, valid qform and sform matrices in an image
    Selects the best available affine (sform > qform > shape-based), and
    coerces it to be qform-compatible (no shears).
    The resulting image represents this same affine as both qform and sform,
    and is marked as NIFTI_XFORM_ALIGNED_ANAT, indicating that it is valid,
    not aligned to template, and not necessarily preserving the original
    coordinates.
    If header would be unchanged, returns input image.

    Parameters
    ----------
    img : Nifti1Image
        Input image to be normalized

    Returns
    -------
    Nifti1Image
        normalized image
    """

    # Let nibabel convert from affine to quaternions, and recover xform
    tmp_header = img.header.copy()
    tmp_header.set_qform(img.affine)
    xform = tmp_header.get_qform()
    xform_code = 2

    # Check desired codes
    qform, qform_code = img.get_qform(coded=True)
    sform, sform_code = img.get_sform(coded=True)
    if all(
        (
            qform is not None and np.allclose(qform, xform),
            sform is not None and np.allclose(sform, xform),
            int(qform_code) == xform_code,
            int(sform_code) == xform_code,
        )
    ):
        return img

    new_img = img.__class__(img.get_data(), xform, img.header)
    # Unconditionally set sform/qform
    new_img.set_sform(xform, xform_code)
    new_img.set_qform(xform, xform_code)

    return new_img


@print_arguments(inputs=[0, 1])
def reorient_dwi(dwi_prep: Path, bvecs: str, preproc_dir: Path):
    # TODO : normalize whether inputs are `str` or `Path`
    """Orients dwi data to the proper orientation (RAS+) using nibabel

    Parameters
    ----------
    dwi_prep : str
        Path to eddy corrected dwi file
    bvecs : str
        Path to the resaled b-vector file

    Returns
    -------
    out_fname : str
        Path to potentially reoriented dwi file
    out_bvec_fname : str
        Path to b-vector file, potentially reoriented if dwi data was
    """

    # ensure proper types
    preproc_dir = Path(preproc_dir)
    dwi_prep = str(dwi_prep)
    out_bvec_fname = str(preproc_dir / "bvecs_reor.bvec")

    input_img = nib.load(dwi_prep)
    input_axcodes = nib.aff2axcodes(input_img.affine)
    reoriented = nib.as_closest_canonical(input_img)
    normalized = normalize_xform(reoriented)
    # Is the input image oriented how we want?
    new_axcodes = ("R", "A", "S")
    out_beginning = str(preproc_dir / f"{get_filename(dwi_prep)}")
    if normalized is not input_img:
        out_fname = out_beginning + "_reor_RAS.nii.gz"
        print(f"Reorienting {dwi_prep} to RAS+...")

        # Flip the bvecs
        input_orientation = nib.orientations.axcodes2ornt(input_axcodes)
        desired_orientation = nib.orientations.axcodes2ornt(new_axcodes)
        transform_orientation = nib.orientations.ornt_transform(
            input_orientation, desired_orientation
        )
        bvec_array = np.loadtxt(bvecs)
        if bvec_array.shape[0] != 3:
            bvec_array = bvec_array.T
        if not bvec_array.shape[0] == transform_orientation.shape[0]:
            raise ValueError("Unrecognized bvec format")
        output_array = np.zeros_like(bvec_array)
        for this_axnum, (axnum, flip) in enumerate(transform_orientation):
            output_array[this_axnum] = bvec_array[int(axnum)] * float(flip)
        np.savetxt(out_bvec_fname, output_array, fmt="%.8f ")
    else:
        out_fname = out_beginning + "_RAS.nii.gz"
        out_bvec_fname = bvecs

    normalized.to_filename(out_fname)

    return out_fname, out_bvec_fname


@print_arguments(inputs=[0])
def reorient_t1w(img: str, anat_preproc_dir: Path):
    """Reorients input image to RAS+. Essentially a wrapper on `nib.as_closest_canonical` and `normalize_xform`.

    Parameters
    ----------
    img : str
        Path to image being reoriented
    anat_preproc_dir : Path
        Location of preproc directory for anatomical files.


    Returns
    -------
    str
        Path to reoriented image
    """

    # Load image, orient as RAS
    orig_img = nib.load(img)
    reoriented = nib.as_closest_canonical(orig_img)
    normalized = normalize_xform(reoriented)

    # Image may be reoriented
    out_name = anat_preproc_dir / f"{get_filename(img)}"
    if normalized is not orig_img:
        print(f"Reorienting {img} to RAS+...")
        out_name = str(out_name) + "_reor_RAS.nii.gz"
    else:
        out_name = str(out_name) + "_RAS.nii.gz"

    normalized.to_filename(out_name)

    return out_name


@print_arguments(inputs=[0])
def match_target_vox_res(img_file: str, vox_size, outdir: Path, sens):
    """Reslices input MRI file if it does not match the targeted voxel resolution. Can take dwi or t1w scans.

    Parameters
    ----------
    img_file : str
        path to file to be resliced
    vox_size : str
        target voxel resolution ('4mm', '2mm', or '1mm')
    preproc_dir :
    sens : str
        type of data being analyzed ('dwi' or 'anat')

    Returns
    -------
    str
        location of potentially resliced image
    """

    # Check dimensions
    img = nib.load(img_file)
    data = img.get_fdata()
    affine = img.affine
    hdr = img.header
    zooms = hdr.get_zooms()[:3]
    if vox_size == "1mm":
        new_zooms = (1.0, 1.0, 1.0)
    elif vox_size == "2mm":
        new_zooms = (2.0, 2.0, 2.0)
    elif vox_size == "4mm":
        new_zooms = (4.0, 4.0, 4.0)

    # set up paths
    outdir = Path(outdir)
    preproc_location = str(outdir / f"{sens}/preproc/{get_filename(img_file)}")

    if (abs(zooms[0]), abs(zooms[1]), abs(zooms[2])) != new_zooms:
        print("Reslicing image " + img_file + " to " + vox_size + "...")

        img_file_res = preproc_location + "_res.nii.gz"
        data2, affine2 = reslice(data, affine, zooms, new_zooms)
        img2 = nib.Nifti1Image(data2, affine=affine2)
        nib.save(img2, img_file_res)
        img_file = img_file_res
    else:
        print("Reslicing image " + img_file + " to " + vox_size + "...")
        img_file_nores = preproc_location + "_nores.nii.gz"
        nib.save(img, img_file_nores)
        img_file = img_file_nores

    return img_file


def parcel_overlap(parcellation1, parcellation2, outpath):
    """A function to compute the percent composition of each parcel in
    parcellation 1 with the parcels in parcellation 2. Rows are indices
    in parcellation 1; cols are parcels in parcellation 2. Values are the
    percent of voxels in parcel (parcellation 1) that fall into parcel
    (parcellation 2). Implied is that each row sums to 1.

    Parameters
    ----------
    parcellation1 : str
        the path to the first parcellation.
    parcellation2 : str
        the path to the second parcellation.
    outpath : str
        the path to produce the output.
    """

    p1_dat = nib.load(parcellation1).get_data()
    p2_dat = nib.load(parcellation2).get_data()
    p1regs = np.unique(p1_dat)
    p1regs = p1regs[p1regs > 0]
    p2regs = np.unique(p2_dat)

    p1n = get_filename(parcellation1)
    p2n = get_filename(parcellation2)

    overlapdat = lil_matrix((p1regs.shape[0], p2regs.shape[0]), dtype=np.float32)
    for p1idx, p1reg in enumerate(p1regs):
        p1seq = p1_dat == p1reg
        N = p1seq.sum()
        poss_regs = np.unique(p2_dat[p1seq])
        for p2idx, p2reg in enumerate(p2regs):
            if p2reg in poss_regs:
                # percent overlap is p1seq and'd with the anatomical region voxelspace, summed and normalized
                pover = np.logical_and(p1seq, p2_dat == p2reg).sum() / float(N)
                overlapdat[p1idx, p2idx] = pover

    outf = os.path.join(outpath, f"{p1n}_{p2n}.csv")
    with open(outf, "w") as f:
        p2str = [f"{x}" for x in p2regs]
        f.write("p1reg," + ",".join(p2str) + "\n")
        for idx, p1reg in enumerate(p1regs):
            datstr = ["%.4f" % x for x in overlapdat[idx,].toarray()[0,]]
            f.write(str(p1reg) + "," + ",".join(datstr) + "\n")
        f.close()
