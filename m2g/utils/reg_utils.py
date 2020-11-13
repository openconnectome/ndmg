"""
m2g.utils.reg_utils
~~~~~~~~~~~~~~~~~~~~

Contains small-scale registration utilities.
"""

# standard library imports
import os
import subprocess

# package imports
import nibabel as nib
import numpy as np
import nilearn.image as nl

from dipy.align.imaffine import MutualInformationMetric
from dipy.align.imaffine import AffineRegistration
from dipy.align.imaffine import transform_origins
from dipy.align.transforms import TranslationTransform3D
from dipy.align.transforms import RigidTransform3D
from dipy.align.transforms import AffineTransform3D
from dipy.align.imwarp import SymmetricDiffeomorphicRegistration
from dipy.align.metrics import CCMetric
from dipy.viz import regtools

# m2g imports
from m2g.utils import gen_utils
from m2g.utils.gen_utils import print_arguments, timer


def erode_mask(mask, v=0):
    """A function to erode a mask by a specified number of voxels. Here, we define
    erosion as the process of checking whether all the voxels within a number of voxels
    for a mask have valuess.

    Parameters
    ----------
    mask : array
        a numpy array of a mask to be eroded
    v : int, optional
        the number of voxels to erode by, by default 0

    Returns
    -------
    numpy array
        eroded mask

    Raises
    ------
    ValueError
        The mask you provided for erosion has an invalid shape (must be x.shape=y.shape=z.shape)
    """

    print("Eroding Mask...")
    for i in range(0, v):
        # masked_vox is a tuple 0f [x]. [y]. [z] cooords
        # wherever mask is nonzero
        erode_mask = np.zeros(mask.shape)
        x, y, z = np.where(mask != 0)
        if x.shape == y.shape and y.shape == z.shape:
            # iterated over all the nonzero voxels
            for j in range(0, x.shape[0]):
                # check that the 3d voxels within 1 voxel are 1
                # if so, add to the new mask
                md = mask.shape
                if (
                    mask[x[j], y[j], z[j]]
                    and mask[np.min((x[j] + 1, md[0] - 1)), y[j], z[j]]
                    and mask[x[j], np.min((y[j] + 1, md[1] - 1)), z[j]]
                    and mask[x[j], y[j], np.min((z[j] + 1, md[2] - 1))]
                    and mask[np.max((x[j] - 1, 0)), y[j], z[j]]
                    and mask[x[j], np.max((y[j] - 1, 0)), z[j]]
                    and mask[x[j], y[j], np.max((z[j] - 1, 0))]
                ):
                    erode_mask[x[j], y[j], z[j]] = 1
        else:
            raise ValueError("Your mask erosion has an invalid shape.")
        mask = erode_mask
    return mask


@print_arguments(inputs=[0], outputs=[1])
def probmap2mask(prob_map, mask_path, t, erode=0):
    """
    A function to extract a mask from a probability map.
    Also, performs mask erosion as a substep.

    **Positional Arguments:**

        prob_map:
            - the path to probability map for the given class
              of brain tissue.
        mask_path:
            - the path to the extracted mask.
        t:
            - the threshold to consider voxels part of the class.
        erode=0:
            - the number of voxels to erode by. Defaults to 0.
    """
    print(f"Extracting Mask from probability map {prob_map}...")
    prob = nib.load(prob_map)
    prob_dat = prob.get_data()
    mask = (prob_dat > t).astype(int)
    if erode > 0:
        mask = erode_mask(mask, v=erode)
    img = nib.Nifti1Image(mask, header=prob.header, affine=prob.get_affine())
    # save the corrected image
    nib.save(img, mask_path)
    return mask_path


@print_arguments(inputs=[0, 1], outputs=[2])
def apply_mask(inp, mask, out):
    """A function to generate a brain-only mask for an input image using 3dcalc

    Parameters
    ----------
    inp : str
        path for the input image. If 4d, the mask should be 4d. If 3d, the mask should be 3d.
    mask : str
        path to the mask to apply to the data. Should be nonzero in mask region.
    out : str
        the path for the output skull-extracted image.
    """

    cmd = f'3dcalc -a {inp} -b {mask} -expr "a*step(b)" -prefix {out}'
    gen_utils.run(cmd)


@print_arguments(inputs=[1], outputs=[2])
def extract_t1w_brain(t1w, out, tmpdir, skull="none"):
    """A function to extract the brain from an input T1w image
    using AFNI's brain extraction utilities.

    Parameters
    ----------
    t1w : str
        path for the input T1w image
    out : str
        path for the output brain image
    tmpdir : str
        Path for the temporary directory to store images
    skull : str, optional
        skullstrip parameter pre-set. Default is "none".
    """

    t1w_name = gen_utils.get_filename(t1w)
    # the t1w image with the skull removed.
    skull_t1w = f"{tmpdir}/{t1w_name}_noskull.nii.gz"
    # 3dskullstrip to extract the brain-only t1w
    t1w_skullstrip(t1w, skull_t1w, skull)
    # 3dcalc to apply the mask over the 4d image
    apply_mask(t1w, skull_t1w, out)


@print_arguments(inputs=[1], outputs=[0])
def normalize_t1w(inp, out):
    """
    A function that normalizes intensity values for anatomical
    T1w images. Makes brain extraction much more robust
    in the event that we have poor shading in our T1w image.

    **Positional Arguments:**

        - inp:
            - the input T1w image.
        - out:
            - the output intensity-normalized image.
    """
    cmd = f"3dUnifize -prefix {out} -input {inp}"
    gen_utils.run(cmd)


@print_arguments(inputs=[0], outputs=[1])
def resample_fsl(base, res, goal_res, interp="spline"):
    """
    A function to resample a base image in fsl to that of a template.

    **Positional Arguments:**

        base:
            - the path to the base image to resample.
        res:
            - the filename after resampling.
        goal_res:
            - the desired resolution.
        interp:
            - the interpolation strategy to use.
    """
    # resample using an isometric transform in fsl
    cmd = f"flirt -in {base} -ref {base} -out {res} -applyisoxfm {goal_res} -interp {interp}"
    gen_utils.run(cmd)


def skullstrip_check(dmrireg, parcellations, outdir, prep_anat, vox_size, reg_style):
    """Peforms the alignment of atlas to dwi space and checks if the alignment results in roi loss

    Parameters
    ----------
    dmrireg : object
        object created in the pipeline containing relevant paths and class methods for analysing tractography
    parcellations : str, list
        the path to the t1w image to be segmented
    outdir : str
        the basename for outputs. Often it will be most convenient for this to be the dataset, followed by the subject,
        followed by the step of processing. Note that this anticipates a path as well;
        ie, /path/to/dataset_sub_nuis, with no extension.
    preproc_dir : str
        Path to anatomical preprocessing directory location.
    vox_size : str
        additional options that can optionally be passed to fast. Desirable options might be -P, which will use
        prior probability maps if the input T1w MRI is in standard space, by default ""
    reg_style : str
        Tractography space, must be either native or native_dsn

    Returns
    -------
    list
        List containing the paths to the aligned label files

    Raises
    ------
    KeyError
        The atlas has lost an roi due to alignment
    """
    if reg_style == "native":
        dsn = False
    elif reg_style == "native_dsn":
        dsn = True
    else:
        raise ValueError("Unsupported tractography space, must be native or native_dsn")

    labels_im_file_list = []
    for idx, label in enumerate(parcellations):
        labels_im_file = gen_utils.reorient_t1w(parcellations[idx], prep_anat)
        labels_im_file = gen_utils.match_target_vox_res(
            labels_im_file, vox_size, outdir, sens="anat"
        )
        orig_lab = nib.load(labels_im_file)
        orig_lab = orig_lab.get_data().astype("int")
        n_ids = orig_lab[orig_lab > 0]
        num = len(np.unique(n_ids))

        labels_im_file_dwi = dmrireg.atlas2t1w2dwi_align(labels_im_file, dsn)
        labels_im = nib.load(labels_im_file_dwi)
        align_lab = labels_im.get_data().astype("int")
        n_ids_2 = align_lab[align_lab > 0]
        num2 = len(np.unique(n_ids_2))

        if num != num2:
            print('''WARNING: The atlas has lost an roi due to alignment! A file containing the lost ROI values will be generated in the
            same folder as the connectome output. Try rerunning m2g with the appropriate --skull flag.'''
            )

        labels_im_file_list.append(labels_im_file_dwi)
    return labels_im_file_list


@timer
@print_arguments(inputs=[0], outputs=[1])
def t1w_skullstrip(t1w, out, skull=None):
    """Skull-strips the t1w image using AFNIs 3dSkullStrip algorithm, which is a modification of FSLs BET specialized to t1w images.
    Offers robust skull-stripping with no hyperparameters
    Note: renormalizes the intensities, call extract_t1w_brain instead if you want the original intensity values

    Parameters
    ----------
    t1w : str
        path for the input t1w image file
    out : str
        path for the output skull-stripped image file
    skull : str, optional
        skullstrip parameter pre-set. Default is "none".
    """
    if skull == "below":
        cmd = f"3dSkullStrip -prefix {out} -input {t1w} -shrink_fac_bot_lim 0.6 -ld 45"
    elif skull == "cerebelum":
        cmd = f"3dSkullStrip -prefix {out} -input {t1w} -shrink_fac_bot_lim 0.3 -ld 45"
    elif skull == "eye":
        cmd = f"3dSkullStrip -prefix {out} -input {t1w} -no_avoid_eyes -ld 45"
    elif skull == "general":
        cmd = f"3dSkullStrip -prefix {out} -input {t1w} -push_to_edge -ld 45"
    else:
        cmd = f"3dSkullStrip -prefix {out} -input {t1w} -ld 30"
    gen_utils.run(cmd)


@print_arguments(inputs=[0], outputs=[1])
def segment_t1w(t1w, basename, opts=""):
    """Uses FSLs FAST to segment an anatomical image into GM, WM, and CSF probability maps.

    Parameters
    ----------
    t1w : str
        the path to the t1w image to be segmented
    basename : str
        the basename for outputs. Often it will be most convenient for this to be the dataset, followed by the subject,
        followed by the step of processing. Note that this anticipates a path as well;
        ie, /path/to/dataset_sub_nuis, with no extension.
    opts : str, optional
        additional options that can optionally be passed to fast. Desirable options might be -P, which will use
        prior probability maps if the input T1w MRI is in standard space, by default ""

    Returns
    -------
    dict
        dictionary of output files
    """

    # run FAST, with options -t for the image type and -n to
    # segment into CSF (pve_0), WM (pve_1), GM (pve_2)
    cmd = f"fast -t 1 {opts} -n 3 -o {basename} {t1w}"
    gen_utils.run(cmd)
    out = {}  # the outputs
    out["wm_prob"] = f"{basename}_pve_2.nii.gz"
    out["gm_prob"] = f"{basename}_pve_1.nii.gz"
    out["csf_prob"] = f"{basename}_pve_0.nii.gz"
    return out


@print_arguments(inputs=[0, 1], outputs=[3])
def align(
    inp,
    ref,
    xfm=None,
    out=None,
    dof=12,
    searchrad=True,
    bins=256,
    interp=None,
    cost="mutualinfo",
    sch=None,
    wmseg=None,
    init=None,
    finesearch=None,
):
    """Aligns two images using FSLs flirt function and stores the transform between them

    Parameters
    ----------
    inp : str
        path to input image being altered to align with the reference image as a nifti image file
    ref : str
        path to reference image being aligned to as a nifti image file
    xfm : str, optional
        where to save the 4x4 affine matrix containing the transform between two images, by default None
    out : str, optional
        determines whether the image will be automatically aligned and where the resulting image will be saved, by default None
    dof : int, optional
        the number of degrees of free dome of the alignment, by default 12
    searchrad : bool, optional
        whether to use the predefined searchradius parameter (180 degree sweep in x, y, and z), by default True
    bins : int, optional
        number of histogram bins, by default 256
    interp : str, optional
        interpolation method to be used (trilinear,nearestneighbour,sinc,spline), by default None
    cost : str, optional
        cost function to be used in alignment (mutualinfo, corratio, normcorr, normmi, leastsq, labeldiff, or bbr), by default "mutualinfo"
    sch : str, optional
        the optional FLIRT schedule, by default None
    wmseg : str, optional
        an optional white-matter segmentation for bbr, by default None
    init : str, optional
        an initial guess of an alignment in the form of the path to a matrix file, by default None
    finesearch : int, optional
        angle in degrees, by default None
    """

    cmd = f"flirt -in {inp} -ref {ref}"
    if xfm is not None:
        cmd += f" -omat {xfm}"
    if out is not None:
        cmd += f" -out {out}"
    if dof is not None:
        cmd += f" -dof {dof}"
    if bins is not None:
        cmd += f" -bins {bins}"
    if interp is not None:
        cmd += f" -interp {interp}"
    if cost is not None:
        cmd += f" -cost {cost}"
    if searchrad is not None:
        cmd += " -searchrx -180 180 -searchry -180 180 " + "-searchrz -180 180"
    if sch is not None:
        cmd += f" -schedule {sch}"
    if wmseg is not None:
        cmd += f" -wmseg {wmseg}"
    if init is not None:
        cmd += f" -init {init}"
    gen_utils.run(cmd)


@print_arguments(inputs=[0, 1, 2], outputs=[3])
def align_epi(epi, t1, brain, out):
    """
    Algins EPI images to T1w image
    """
    cmd = f"epi_reg --epi={epi} --t1={t1} --t1brain={brain} --out={out}"
    gen_utils.run(cmd)


@timer
@print_arguments(inputs=[0, 1], outputs=[3])
def align_nonlinear(inp, ref, xfm, out, warp, ref_mask=None, in_mask=None, config=None):
    """Aligns two images using nonlinear methods and stores the transform between them using fnirt

    Parameters
    ----------
    inp : str
        path to the input image
    ref : str
        path to the reference image that the input will be aligned to
    xfm : str
        path to the file containing the affine transform matrix created by reg_utils.align()
    out : str
        path for the desired output image
    warp : str
        the path to store the output file containing the nonlinear warp coefficients/fields
    ref_mask : str, optional
        path to the reference image brain_mask, by default None
    in_mask : str, optional
        path for the file with mask in input image space, by default None
    config : str, optional
        path to the config file specifying command line arguments, by default None
    """

    cmd = f"fnirt --in={inp} --ref={ref} --aff={xfm} --iout={out} --cout={warp} --warpres=8,8,8"
    if ref_mask is not None:
        cmd += f" --refmask={ref_mask} --applyrefmask=1"
    if in_mask is not None:
        cmd += f" --inmask={in_mask} --applyinmask=1"
    if config is not None:
        cmd += f" --config={config}"
    gen_utils.run(cmd)


@print_arguments(inputs=[0, 1, 2], outputs=[3])
def applyxfm(ref, inp, xfm, aligned, interp="trilinear", dof=6):
    """Aligns two images with a given transform using FSLs flirt command

    Parameters
    ----------
    ref : str
        path of reference image to be aligned to as a nifti image file
    inp : str
        path of input image to be aligned as a nifti image file
    xfm : str
        path to the transform matrix between the two images
    aligned : str
        path for the output aligned image
    interp : str, optional
        interpolation method, by default "trilinear"
    dof : int, optional
        degrees of freedom for the alignment, by default 6
    """

    cmd = f"flirt -in {inp} -ref {ref} -out {aligned} -init {xfm} -interp {interp} -dof {dof} -applyxfm"
    gen_utils.run(cmd)


@print_arguments(inputs=[0, 1], outputs=[2, 3])
def apply_warp(ref, inp, out, warp, xfm=None, mask=None, interp=None, sup=False):
    """Applies a warp from the structural to reference space in a single step using information about
    the structural -> ref mapping as well as the functional to structural mapping.

    Parameters
    ----------
    ref : str
        path of the reference image to be aligned to
    inp : str
        path of the input image to be aligned
    out : str
        path for the resulting warped output image
    warp : str
        path for the warp coefficent file to go from inp -> ref
    xfm : str, optional
        path of the affine transformation matrix file from inp -> ref, by default None
    mask : str, optional
        path of filename for mask image (in reference space), by default None
    interp : str, optional
        interpolation method {nn, trilinear, sinc, spline}, by default None
    sup : bool, optional
        whether to perform automatic intermediary supersampling, by default False
    """

    cmd = (
        "applywarp --ref=" + ref + " --in=" + inp + " --out=" + out + " --warp=" + warp
    )
    if xfm is not None:
        cmd += " --premat=" + xfm
    if mask is not None:
        cmd += " --mask=" + mask
    if interp is not None:
        cmd += " --interp=" + interp
    if sup is True:
        cmd += " --super --superlevel=a"
    gen_utils.run(cmd)


@print_arguments(inputs=[0, 2], outputs=[1])
def inverse_warp(ref, out, warp):
    """Takes a non-linear mapping and finds the inverse. Takes the file conaining warp-coefficients/fields specified in the
    variable warp (t1w -> mni) and creates its inverse (mni -> t1w) which is saved in the location determined by the variable out

    Parameters
    ----------
    ref : str
        path to a file in target space, which is a different target space than warp (a image that has not been mapped to mni)
    out : str
        path to the output file, containing warps that are now inverted
    warp : str
        path to the warp/shiftmap transform volume wanting to be inverted
    """

    cmd = "invwarp --warp=" + warp + " --out=" + out + " --ref=" + ref
    gen_utils.run(cmd)


@print_arguments(inputs=[0, 2], outputs=[1])
def resample(base, ingested, template):
    """
    Resamples the image such that images which have already been aligned
    in real coordinates also overlap in the image/voxel space.

    **Positional Arguments**
            base:
                - Image to be aligned
            ingested:
                - Name of image after alignment
            template:
                - Image that is the target of the alignment
    """
    # Loads images
    template_im = nib.load(template)
    base_im = nib.load(base)
    # Aligns images
    target_im = nl.resample_img(
        base_im,
        target_affine=template_im.get_affine(),
        target_shape=template_im.get_data().shape,
        interpolation="nearest",
    )
    # Saves new image
    nib.save(target_im, ingested)


@print_arguments(inputs=[0, 1], outputs=[2])
def combine_xfms(xfm1, xfm2, xfmout):
    """A function to combine two transformations and output the resulting transformation

    Parameters
    ----------
    xfm1 : str
        path to the first transformation
    xfm2 : str
        path to the second transformation
    xfmout : str
        path for the ouput transformation
    """
    cmd = f"convert_xfm -omat {xfmout} -concat {xfm1} {xfm2}"
    gen_utils.run(cmd)


@print_arguments(inputs=[0, 1], outputs=[2])
def wm_syn(template_path, fa_path, working_dir):
    """A function to perform ANTS SyN registration using dipy functions

    Parameters
    ----------
    template_path  : str
        File path to the template reference FA image.
    fa_path : str
        File path to the FA moving image (image to be fitted to reference)
    working_dir : str
        Path to the working directory to perform SyN and save outputs.

    Returns
    -------
    DiffeomorphicMap
        An object that can be used to register images back and forth between static (template) and moving (FA) domains
    AffineMap
        An object used to transform the moving (FA) image towards the static image (template)
    """

    fa_img = nib.load(fa_path)
    template_img = nib.load(template_path)

    static = template_img.get_data()
    static_affine = template_img.affine
    moving = fa_img.get_data().astype(np.float32)
    moving_affine = fa_img.affine

    affine_map = transform_origins(static, static_affine, moving, moving_affine)

    nbins = 32
    sampling_prop = None
    metric = MutualInformationMetric(nbins, sampling_prop)

    level_iters = [10, 10, 5]
    sigmas = [3.0, 1.0, 0.0]
    factors = [4, 2, 1]
    affine_reg = AffineRegistration(
        metric=metric, level_iters=level_iters, sigmas=sigmas, factors=factors
    )
    transform = TranslationTransform3D()

    params0 = None
    translation = affine_reg.optimize(
        static, moving, transform, params0, static_affine, moving_affine
    )
    transform = RigidTransform3D()

    rigid_map = affine_reg.optimize(
        static,
        moving,
        transform,
        params0,
        static_affine,
        moving_affine,
        starting_affine=translation.affine,
    )
    transform = AffineTransform3D()

    # We bump up the iterations to get a more exact fit:
    affine_reg.level_iters = [1000, 1000, 100]
    affine_opt = affine_reg.optimize(
        static,
        moving,
        transform,
        params0,
        static_affine,
        moving_affine,
        starting_affine=rigid_map.affine,
    )

    # We now perform the non-rigid deformation using the Symmetric Diffeomorphic Registration(SyN) Algorithm:
    metric = CCMetric(3)
    level_iters = [10, 10, 5]
    sdr = SymmetricDiffeomorphicRegistration(metric, level_iters)

    mapping = sdr.optimize(
        static, moving, static_affine, moving_affine, affine_opt.affine
    )
    warped_moving = mapping.transform(moving)

    # We show the registration result with:
    regtools.overlay_slices(
        static,
        warped_moving,
        None,
        0,
        "Static",
        "Moving",
        f"{working_dir}/transformed_sagittal.png",
    )
    regtools.overlay_slices(
        static,
        warped_moving,
        None,
        1,
        "Static",
        "Moving",
        f"{working_dir}/transformed_coronal.png",
    )
    regtools.overlay_slices(
        static,
        warped_moving,
        None,
        2,
        "Static",
        "Moving",
        f"{working_dir}/transformed_axial.png",
    )

    return mapping, affine_map
