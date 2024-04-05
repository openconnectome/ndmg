#!/usr/bin/env python

"""
m2g.register
~~~~~~~~~~~~~
Contains m2g's registration classes, organized as full registration workflows.
Used for the majority of the registration described here: https://neurodata.io/talks/ndmg.pdf#page=20
"""

# standard library imports
import os
from argparse import ArgumentParser
import subprocess
from pathlib import Path

# package imports
import nibabel as nib
import numpy as np
from nilearn.image import load_img
from nilearn.image import math_img
from dipy.tracking.streamline import deform_streamlines
from dipy.io.streamline import load_trk
from dipy.tracking import utils

# m2g imports
from m2g.utils import gen_utils
from m2g.utils import reg_utils
from m2g.scripts import m2g_bids
from m2g.stats.qa_skullstrip import gen_overlay_pngs
from m2g.stats.qa_reg import reg_mri_pngs
from m2g.stats.qa_fast import qa_fast_png


@gen_utils.timer
def direct_streamline_norm(streams, fa_path, outdir: Path):
    """Applys the Symmetric Diffeomorphic Registration (SyN) Algorithm onto the streamlines to the atlas space defined by .../atlases/reference_brains/FSL_HCP1065_FA_2mm.nii.gz
    Parameters
    ----------
    streams : str
        Path to streamlines.trk file to be transformed
    fa_path : str
        Path to subject's FA tensor image
    outdir : Path
        Output directory location.

    Returns
    -------
    ArraySequence
        Transformed streamlines
    str
        Path to tractogram streamline file: streamlines_dsn.trk
    """

    atlas_dir = m2g_bids.get_atlas_dir()
    template_path = atlas_dir + "/atlases/reference_brains/FSL_HCP1065_FA_2mm.nii.gz"

    # Run SyN and normalize streamlines
    fa_img = nib.load(fa_path)
    vox_size = fa_img.get_header().get_zooms()[0]
    template_img = nib.load(template_path)

    # SyN FA->Template
    mapping, affine_map = reg_utils.wm_syn(template_path, fa_path, str(outdir / "tmp"))
    streamlines = load_trk(streams, reference="same")

    # Warp streamlines
    adjusted_affine = affine_map.affine.copy()
    adjusted_affine[1][3] = -adjusted_affine[1][3] / vox_size**2
    mni_streamlines = deform_streamlines(
        streamlines.streamlines,
        deform_field=mapping.get_forward_field()[-1:],
        stream_to_current_grid=template_img.affine,
        current_grid_to_world=adjusted_affine,
        stream_to_ref_grid=template_img.affine,
        ref_grid_to_world=np.eye(4),
    )

    # Save streamlines
    hdr = fa_img.header
    trk_affine = np.eye(4)
    trk_hdr = nib.streamlines.trk.TrkFile.create_empty_header()
    trk_hdr["hdr_size"] = 1000
    trk_hdr["dimensions"] = hdr["dim"][1:4].astype("float32")
    trk_hdr["voxel_sizes"] = hdr["pixdim"][1:4]
    trk_hdr["voxel_to_rasmm"] = trk_affine
    trk_hdr["voxel_order"] = "RAS"
    trk_hdr["pad2"] = "RAS"
    trk_hdr["image_orientation_patient"] = np.array(
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    ).astype("float32")
    trk_hdr["endianness"] = "<"
    trk_hdr["_offset_data"] = 1000
    trk_hdr["nb_streamlines"] = len(mni_streamlines)
    tractogram = nib.streamlines.Tractogram(mni_streamlines, affine_to_rasmm=trk_affine)
    trkfile = nib.streamlines.trk.TrkFile(tractogram, header=trk_hdr)
    streams_mni = streams.split(".trk")[0] + "_dsn.trk"
    nib.streamlines.save(trkfile, streams_mni)
    return mni_streamlines, streams_mni


class DmriReg:
    """Class containing relevant paths and class methods for analysing tractography
    Parameters
    ----------
    outdir : Path
        Output directory location.
    nodif_B0 : str
        path to mean b0 image
    nodif_B0_mask : str
        path to mean b0 mask (nodif_B0....nii.gz)
    t1w_in : str
        path to t1w file
    vox_size : str
        voxel resolution ('2mm' or '1mm')
    skull : str, optional
        skullstrip parameter pre-set. Default is "none"
    simple : bool, optional
        Whether you want to attempt non-linear registration when transforming between mni, t1w, and dwi space. Default is False
    Raises
    ------
    ValueError
        FSL atlas for ventricle reference not found
    """

    def __init__(
        self,
        outdir: Path,
        nodif_B0,
        nodif_B0_mask,
        t1w_in,
        vox_size,
        skull=None,
        simple=False,
    ):

        atlas_dir = m2g_bids.get_atlas_dir()
        FSLDIR = os.environ["FSLDIR"]

        if vox_size == "2mm":
            vox_dims = "2x2x2"
        elif vox_size == "1mm":
            vox_dims = "1x1x1"
        elif vox_size == "4mm":
            vox_dims = "4x4x4"

        # TODO : clean up all these attributes
        self.outdir = outdir
        self.reg_a = str(outdir / "tmp_d/reg_a")
        self.reg_m = str(outdir / "tmp_d/reg_m")
        self.reg_anat = str(outdir / "anat_d/registered")
        self.prep_anat = str(outdir / "anat_d/preproc")
        self.qa = str(outdir / "qa_d")
        self.qa_reg = str(Path(self.qa) / "reg")

        self.simple = simple
        self.nodif_B0 = nodif_B0
        self.nodif_B0_mask = nodif_B0_mask
        self.t1w = t1w_in
        self.vox_size = vox_size
        self.t1w_name = "t1w"
        self.dwi_name = "dwi"
        self.skull = skull
        self.t12mni_xfm_init = f"{self.reg_m}" + "/xfm_t1w2mni_init.mat"
        self.mni2t1_xfm_init = f"{self.reg_m}" + "/xfm_mni2t1w_init.mat"
        self.t12mni_xfm = f"{self.reg_m}" + "/xfm_t1w2mni.mat"
        self.mni2t1_xfm = f"{self.reg_m}" + "/xfm_mni2t1.mat"
        self.mni2t1w_warp = f"{self.reg_a}/mni2t1w_warp.nii.gz"
        self.warp_t1w2mni = f"{self.reg_a}/warp_t12mni.nii.gz"
        self.t1w2dwi = f"{self.reg_anat}/{self.t1w_name}_in_dwi.nii.gz"
        self.t1_aligned_mni = f"{self.prep_anat}/{self.t1w_name}_aligned_mni.nii.gz"
        self.t1w_brain = f"{self.prep_anat}/{self.t1w_name}_brain.nii.gz"
        self.dwi2t1w_xfm = f"{self.reg_m}" + "/dwi2t1w_xfm.mat"
        self.t1w2dwi_xfm = f"{self.reg_m}" + "/t1w2dwi_xfm.mat"
        self.t1w2dwi_bbr_xfm = f"{self.reg_m}" + "/t1w2dwi_bbr_xfm.mat"
        self.dwi2t1w_bbr_xfm = f"{self.reg_m}" + "/dwi2t1w_bbr_xfm.mat"
        self.t1wtissue2dwi_xfm = f"{self.reg_m}" + "/t1wtissue2dwi_xfm.mat"
        self.xfm_atlas2t1w_init = (
            f"{self.reg_m}" + f"/{self.t1w_name}_xfm_atlas2t1w_init.mat"
        )
        self.xfm_atlas2t1w = f"{self.reg_m}/{self.t1w_name}_xfm_atlas2t1w.mat"
        self.temp2dwi_xfm = f"{self.reg_m}/{self.dwi_name}_xfm_temp2dwi.mat"

        self.input_mni = f"{FSLDIR}/data/standard/MNI152_T1_{vox_size}_brain.nii.gz"
        self.input_mni_mask = (
            f"{FSLDIR}/data/standard/MNI152_T1_{vox_size}_brain_mask.nii.gz"
        )
        self.temp2dwi_xfm = f"{self.reg_m}/{self.dwi_name}_xfm_temp2dwi.mat"
        self.map_path = f"{self.prep_anat}/{self.t1w_name}_seg"
        self.wm_mask_thr = f"{self.prep_anat}/{self.t1w_name}_wm_thr.nii.gz"
        self.wm_edge = f"{self.reg_a}/{self.t1w_name}_wm_edge.nii.gz"
        self.wm_mask = f"{self.prep_anat}/{self.t1w_name}_seg_pve_2.nii.gz"
        self.gm_mask = f"{self.prep_anat}/{self.t1w_name}_seg_pve_1.nii.gz"
        self.csf_mask = f"{self.prep_anat}/{self.t1w_name}_seg_pve_0.nii.gz"
        self.xfm_roi2mni_init = f"{self.reg_m}/roi_2_mni.mat"
        self.lvent_out_file = f"{self.reg_a}/LVentricle.nii.gz"
        self.rvent_out_file = f"{self.reg_a}/RVentricle.nii.gz"
        self.csf_mask_dwi = f"{self.reg_anat}/{self.t1w_name}_csf_mask_dwi.nii.gz"
        self.gm_in_dwi = f"{self.reg_anat}/{self.t1w_name}_gm_in_dwi.nii.gz"
        self.wm_in_dwi = f"{self.reg_anat}/{self.t1w_name}_wm_in_dwi.nii.gz"
        self.csf_mask_dwi_bin = f"{self.reg_a}/{self.t1w_name}_csf_mask_dwi_bin.nii.gz"
        self.gm_in_dwi_bin = f"{self.reg_a}/{self.t1w_name}_gm_in_dwi_bin.nii.gz"
        self.wm_in_dwi_bin = f"{self.reg_a}/{self.t1w_name}_wm_in_dwi_bin.nii.gz"
        self.vent_mask_dwi = f"{self.reg_a}/{self.t1w_name}_vent_mask_dwi.nii.gz"
        self.vent_csf_in_dwi = f"{self.reg_a}/{self.t1w_name}_vent_csf_in_dwi.nii.gz"
        self.vent_mask_mni = f"{self.reg_a}/vent_mask_mni.nii.gz"
        self.vent_mask_t1w = f"{self.reg_a}/vent_mask_t1w.nii.gz"
        self.wm_gm_int_in_dwi = (
            f"{self.reg_anat}/{self.t1w_name}_wm_gm_int_in_dwi.nii.gz"
        )
        self.wm_gm_int_in_dwi_bin = (
            f"{self.reg_anat}/{self.t1w_name}_wm_gm_int_in_dwi_bin.nii.gz"
        )
        self.input_mni_sched = f"{FSLDIR}/etc/flirtsch/T1_2_MNI152_2mm.cnf"
        self.mni_atlas = f"{atlas_dir}/atlases/label/Human/HarvardOxfordsub-maxprob-thr25_space-MNI152NLin6_label_all_res-{vox_dims}.nii.gz"
        self.mni_vent_loc = f"{atlas_dir}/atlases/mask/HarvardOxford-thr25_space-MNI152NLin6_variant-lateral-ventricles_res-{vox_dims}_descr-brainmask.nii.gz"
        self.corpuscallosum = (
            f"{atlas_dir}/atlases/mask/CorpusCallosum_res_{vox_size}.nii.gz"
        )
        self.corpuscallosum_mask_t1w = (
            f"{self.reg_anat}/{self.t1w_name}_corpuscallosum.nii.gz"
        )
        self.corpuscallosum_dwi = (
            f"{self.reg_anat}/{self.t1w_name}_corpuscallosum_dwi.nii.gz"
        )

    @gen_utils.timer
    def gen_tissue(self):
        """Extracts the brain from the raw t1w image (as indicated by self.t1w), uses it to create WM, GM, and CSF masks,
        reslices all 4 files to the target voxel resolution and extracts the white matter edge. Each mask is saved to
        location indicated by self.map_path
        """

        # TODO: Why is the t1w skullstripped here? Shouldn't this be part of the preprocessing?
        # BET needed for this, as afni 3dautomask only works on 4d volumes
        print("Extracting brain from raw T1w image...")
        reg_utils.t1w_skullstrip(self.t1w, self.t1w_brain, self.skull)

        #  QA part of skull strip
        skullstrip_qa = Path(self.qa) / "skull_strip"
        if not os.path.exists(skullstrip_qa):
            skullstrip_qa.mkdir(parents=True, exist_ok=True)
        print("QA_skullstrip_path  ", skullstrip_qa)
        gen_overlay_pngs(self.t1w_brain, self.t1w, skullstrip_qa)

        # Segment the t1w brain into probability maps
        self.maps = reg_utils.segment_t1w(self.t1w_brain, self.map_path)
        self.wm_mask = self.maps["wm_prob"]
        self.gm_mask = self.maps["gm_prob"]
        self.csf_mask = self.maps["csf_prob"]

        # Generates quality analysis pictures of white matter, gray matter and cerebrospinal fluid
        qa_fast_png(
            self.csf_mask,
            self.gm_mask,
            self.wm_mask,
            str(Path(self.qa_reg) / "qa_fast.png"),
        )

        self.t1w_brain = gen_utils.match_target_vox_res(
            self.t1w_brain, self.vox_size, self.outdir, sens="anat_d"
        )
        self.wm_mask = gen_utils.match_target_vox_res(
            self.wm_mask, self.vox_size, self.outdir, sens="anat_d"
        )
        self.gm_mask = gen_utils.match_target_vox_res(
            self.gm_mask, self.vox_size, self.outdir, sens="anat_d"
        )
        self.csf_mask = gen_utils.match_target_vox_res(
            self.csf_mask, self.vox_size, self.outdir, sens="anat_d"
        )

        # Threshold WM to binary in dwi space
        self.t_img = load_img(self.wm_mask)
        self.mask = math_img("img > 0.2", img=self.t_img)
        self.mask.to_filename(self.wm_mask_thr)

        # Extract wm edge
        # TODO : this should be a function in reg_utils so that we can print it to the log
        cmd = f"fslmaths {self.wm_mask_thr} -edge -bin -mas {self.wm_mask_thr} {self.wm_edge}"
        print("Extracting white matter edge...")
        gen_utils.run(cmd)

    def check_gen_tissue_files(self):
        """Function for checking whether files were resliced or not.
        Only used for `skipreg` option."""

        if self.vox_size == "1mm":
            new_zooms = (1.0, 1.0, 1.0)
        elif self.vox_size == "2mm":
            new_zooms = (2.0, 2.0, 2.0)
        elif self.vox_size == "4mm":
            new_zooms = (4.0, 4.0, 4.0)

        img = nib.load(self.t1w_brain)
        zooms = img.header.get_zooms()[:3]

        if (abs(zooms[0]), abs(zooms[1]), abs(zooms[2])) != new_zooms:
            suffix = "_res.nii.gz"
        else:
            suffix = "_nores.nii.gz"

        # Remove .nii.gz and replace with suffix
        self.t1w_brain = self.t1w_brain[:-7] + suffix
        self.wm_mask = self.wm_mask[:-7] + suffix
        self.gm_mask = self.gm_mask[:-7] + suffix
        self.csf_mask = self.csf_mask[:-7] + suffix

    @gen_utils.timer
    def t1w2dwi_align(self):
        """Alignment from t1w to mni, making t1w_mni, and t1w_mni to dwi. A function to perform self alignment. Uses a local optimisation cost function to get the
        two images close, and then uses bbr to obtain a good alignment of brain boundaries. Assumes input dwi is already preprocessed and brain extracted.
        """

        # Create linear transform/ initializer T1w-->MNI
        reg_utils.align(
            self.t1w_brain,
            self.input_mni,
            xfm=self.t12mni_xfm_init,
            bins=None,
            interp="spline",
            out=None,
            dof=12,
            cost="mutualinfo",
            searchrad=True,
        )

        # Attempt non-linear registration of T1 to MNI template
        if self.simple is False:
            try:
                print("Running non-linear registration: T1w-->MNI ...")
                # Use FNIRT to nonlinearly align T1 to MNI template
                reg_utils.align_nonlinear(
                    self.t1w_brain,
                    self.input_mni,
                    xfm=self.t12mni_xfm_init,
                    out=self.t1_aligned_mni,
                    warp=self.warp_t1w2mni,
                    ref_mask=self.input_mni_mask,
                    config=self.input_mni_sched,
                )

                # Get warp from MNI -> T1
                reg_utils.inverse_warp(
                    self.t1w_brain, self.mni2t1w_warp, self.warp_t1w2mni
                )

                # Get mat from MNI -> T1
                # TODO: I don't think the resulting matrix is used anywhere? Double check and then remove is useless...
                cmd = f"convert_xfm -omat {self.mni2t1_xfm_init} -inverse {self.t12mni_xfm_init}"
                print(cmd)
                gen_utils.run(cmd)

            except RuntimeError("Error: FNIRT failed!"):
                pass
        else:
            # Falling back to linear registration
            reg_utils.align(
                self.t1w_brain,
                self.input_mni,
                xfm=self.t12mni_xfm,
                init=self.t12mni_xfm_init,
                bins=None,
                dof=12,
                cost="mutualinfo",
                searchrad=True,
                interp="spline",
                out=self.t1_aligned_mni,
                sch=None,
            )
        reg_mri_pngs(self.t1_aligned_mni, self.input_mni, self.qa_reg)

        # Align T1w-->DWI
        reg_utils.align(
            self.nodif_B0,
            self.t1w_brain,
            xfm=self.t1w2dwi_xfm,
            bins=None,
            interp="spline",
            dof=6,
            cost="mutualinfo",
            out=None,
            searchrad=True,
            sch=None,
        )
        cmd = f"convert_xfm -omat {self.dwi2t1w_xfm} -inverse {self.t1w2dwi_xfm}"
        print(cmd)
        gen_utils.run(cmd)

        if self.simple is False:
            # Flirt bbr
            try:
                print("Running FLIRT BBR registration: DWI-->T1W ...")
                reg_utils.align(
                    self.nodif_B0,
                    self.t1w_brain,
                    wmseg=self.wm_edge,
                    xfm=self.dwi2t1w_bbr_xfm,
                    init=self.dwi2t1w_xfm,
                    bins=256,
                    dof=7,
                    searchrad=True,
                    interp="spline",
                    out=None,
                    cost="bbr",
                    finesearch=5,
                    sch="${FSLDIR}/etc/flirtsch/bbr.sch",
                )
                cmd = f"convert_xfm -omat {self.t1w2dwi_bbr_xfm} -inverse {self.dwi2t1w_bbr_xfm}"
                gen_utils.run(cmd)

                # Apply the alignment
                reg_utils.align(
                    self.t1w_brain,
                    self.nodif_B0,
                    init=self.t1w2dwi_bbr_xfm,
                    xfm=self.t1wtissue2dwi_xfm,
                    bins=None,
                    interp="spline",
                    dof=7,
                    cost="mutualinfo",
                    out=self.t1w2dwi,
                    searchrad=True,
                    sch=None,
                )
            except RuntimeError("Error: FLIRT BBR failed!"):
                pass
        else:
            # Apply the alignment
            reg_utils.align(
                self.t1w_brain,
                self.nodif_B0,
                init=self.t1w2dwi_xfm,
                xfm=self.t1wtissue2dwi_xfm,
                bins=None,
                interp="spline",
                dof=6,
                cost="mutualinfo",
                out=self.t1w2dwi,
                searchrad=True,
                sch=None,
            )
        reg_mri_pngs(self.t1w2dwi, self.nodif_B0, self.qa_reg)

    def atlas2t1w2dwi_align(self, atlas, dsn=True):
        """alignment from atlas to t1w to dwi. A function to perform atlas alignmet. Tries nonlinear registration first, and if that fails, does a liner
        registration instead.
        Note: for this to work, must first have called t1w2dwi_align.
        Parameters
        ----------
        atlas : str
            path to atlas file you want to use
        dsn : bool, optional
            is your space for tractography native-dsn, by default True
        Returns
        -------
        str
            path to aligned atlas file
        """

        self.atlas = atlas
        self.atlas_name = gen_utils.get_filename(self.atlas)
        self.aligned_atlas_t1mni = (
            f"{self.reg_a}/{self.atlas_name}_aligned_atlas_t1w_mni.nii.gz"
        )
        self.aligned_atlas_skull = (
            f"{self.reg_a}/{self.atlas_name}_aligned_atlas_skull.nii.gz"
        )
        self.dwi_aligned_atlas = (
            f"{self.reg_anat}/{self.atlas_name}_aligned_atlas.nii.gz"
        )

        reg_utils.align(
            self.atlas,
            self.t1_aligned_mni,
            init=None,
            xfm=None,
            out=self.aligned_atlas_t1mni,
            dof=12,
            searchrad=True,
            interp="nearestneighbour",
            cost="mutualinfo",
        )

        if (self.simple is False) and (dsn is False):
            try:
                # Apply warp resulting from the inverse of T1w-->MNI created earlier
                reg_utils.apply_warp(
                    self.t1w_brain,
                    self.aligned_atlas_t1mni,
                    self.aligned_atlas_skull,
                    warp=self.mni2t1w_warp,
                    interp="nn",
                    sup=True,
                )

                # Apply transform to dwi space
                reg_utils.align(
                    self.aligned_atlas_skull,
                    self.nodif_B0,
                    init=self.t1wtissue2dwi_xfm,
                    xfm=None,
                    out=self.dwi_aligned_atlas,
                    dof=6,
                    searchrad=True,
                    interp="nearestneighbour",
                    cost="mutualinfo",
                )
            except:
                print(
                    "Warning: Atlas is not in correct dimensions, or input is low quality,\nusing linear template registration."
                )
                # Create transform to align atlas to T1w using flirt
                reg_utils.align(
                    self.atlas,
                    self.t1w_brain,
                    xfm=self.xfm_atlas2t1w_init,
                    init=None,
                    bins=None,
                    dof=6,
                    cost="mutualinfo",
                    searchrad=True,
                    interp="spline",
                    out=None,
                    sch=None,
                )
                reg_utils.align(
                    self.atlas,
                    self.t1_aligned_mni,
                    xfm=self.xfm_atlas2t1w,
                    out=None,
                    dof=6,
                    searchrad=True,
                    bins=None,
                    interp="spline",
                    cost="mutualinfo",
                    init=self.xfm_atlas2t1w_init,
                )

                # Combine our linear transform from t1w to template with our transform from dwi to t1w space to get a transform from atlas ->(-> t1w ->)-> dwi
                reg_utils.combine_xfms(
                    self.xfm_atlas2t1w, self.t1wtissue2dwi_xfm, self.temp2dwi_xfm
                )

                # Apply linear transformation from template to dwi space
                reg_utils.applyxfm(
                    self.nodif_B0, self.atlas, self.temp2dwi_xfm, self.dwi_aligned_atlas
                )
        elif dsn is False:
            # Create transform to align atlas to T1w using flirt
            reg_utils.align(
                self.atlas,
                self.t1w_brain,
                xfm=self.xfm_atlas2t1w_init,
                init=None,
                bins=None,
                dof=6,
                cost="mutualinfo",
                searchrad=None,
                interp="spline",
                out=None,
                sch=None,
            )
            reg_utils.align(
                self.atlas,
                self.t1w_brain,
                xfm=self.xfm_atlas2t1w,
                out=None,
                dof=6,
                searchrad=True,
                bins=None,
                interp="spline",
                cost="mutualinfo",
                init=self.xfm_atlas2t1w_init,
            )

            # Combine our linear transform from t1w to template with our transform from dwi to t1w space to get a transform from atlas ->(-> t1w ->)-> dwi
            reg_utils.combine_xfms(
                self.xfm_atlas2t1w, self.t1wtissue2dwi_xfm, self.temp2dwi_xfm
            )

            # Apply linear transformation from template to dwi space
            reg_utils.applyxfm(
                self.nodif_B0, self.atlas, self.temp2dwi_xfm, self.dwi_aligned_atlas
            )
        else:
            pass

        # Set intensities to int
        if dsn is False:
            self.atlas_img = nib.load(self.dwi_aligned_atlas)
        else:
            self.atlas_img = nib.load(self.aligned_atlas_t1mni)
        self.atlas_data = np.around(self.atlas_img.get_data()).astype("int16")
        node_num = len(np.unique(self.atlas_data))
        self.atlas_data[self.atlas_data > node_num] = 0

        t_img = load_img(self.wm_gm_int_in_dwi)
        mask = math_img("img > 0", img=t_img)
        mask.to_filename(self.wm_gm_int_in_dwi_bin)

        if dsn is False:
            nib.save(
                nib.Nifti1Image(
                    self.atlas_data.astype(np.int32),
                    affine=self.atlas_img.affine,
                    header=self.atlas_img.header,
                ),
                self.dwi_aligned_atlas,
            )
            reg_mri_pngs(self.dwi_aligned_atlas, self.nodif_B0, self.qa_reg)
            return self.dwi_aligned_atlas
        else:
            nib.save(
                nib.Nifti1Image(
                    self.atlas_data.astype(np.int32),
                    affine=self.atlas_img.affine,
                    header=self.atlas_img.header,
                ),
                self.aligned_atlas_t1mni,
            )
            reg_mri_pngs(self.aligned_atlas_t1mni, self.t1_aligned_mni, self.qa_reg)
            return self.aligned_atlas_t1mni

    @gen_utils.timer
    def tissue2dwi_align(self):
        """alignment of ventricle and CC ROI's from MNI space --> dwi and CC and CSF from T1w space --> dwi
        A function to generate and perform dwi space alignment of avoidance/waypoint masks for tractography.
        First creates ventricle and CC ROI. Then creates transforms from stock MNI template to dwi space.
        NOTE: for this to work, must first have called both t1w2dwi_align and atlas2t1w2dwi_align.
        Raises
        ------
        ValueError
            Raised if FSL atlas for ventricle reference not found
        """

        # Create MNI-space ventricle mask
        print("Creating MNI-space ventricle ROI...")
        if not os.path.isfile(self.mni_atlas):
            raise ValueError("FSL atlas for ventricle reference not found!")
        cmd = f"fslmaths {self.mni_vent_loc} -thr 0.1 -bin {self.mni_vent_loc}"
        gen_utils.run(cmd)

        cmd = f"fslmaths {self.corpuscallosum} -bin {self.corpuscallosum}"
        gen_utils.run(cmd)

        cmd = f"fslmaths {self.corpuscallosum} -sub {self.mni_vent_loc} -bin {self.corpuscallosum}"
        gen_utils.run(cmd)

        # Create a transform from the atlas onto T1w. This will be used to transform the ventricles to dwi space.
        reg_utils.align(
            self.mni_atlas,
            self.input_mni,
            xfm=self.xfm_roi2mni_init,
            init=None,
            bins=None,
            dof=6,
            cost="mutualinfo",
            searchrad=True,
            interp="spline",
            out=None,
        )

        # Create transform to align roi to mni and T1w using flirt
        reg_utils.applyxfm(
            self.input_mni, self.mni_vent_loc, self.xfm_roi2mni_init, self.vent_mask_mni
        )

        if self.simple is False:
            # Apply warp resulting from the inverse MNI->T1w created earlier
            reg_utils.apply_warp(
                self.t1w_brain,
                self.vent_mask_mni,
                self.vent_mask_t1w,
                warp=self.mni2t1w_warp,
                interp="nn",
                sup=True,
            )

            # Apply warp resulting from the inverse MNI->T1w created earlier
            reg_utils.apply_warp(
                self.t1w_brain,
                self.corpuscallosum,
                self.corpuscallosum_mask_t1w,
                warp=self.mni2t1w_warp,
                interp="nn",
                sup=True,
            )

        # Applyxfm tissue maps to dwi space
        reg_utils.applyxfm(
            self.nodif_B0,
            self.vent_mask_t1w,
            self.t1wtissue2dwi_xfm,
            self.vent_mask_dwi,
        )
        reg_mri_pngs(self.vent_mask_dwi, self.nodif_B0, self.qa_reg)
        reg_utils.applyxfm(
            self.nodif_B0,
            self.corpuscallosum_mask_t1w,
            self.t1wtissue2dwi_xfm,
            self.corpuscallosum_dwi,
        )
        reg_mri_pngs(self.corpuscallosum_dwi, self.nodif_B0, self.qa_reg)
        reg_utils.applyxfm(
            self.nodif_B0, self.csf_mask, self.t1wtissue2dwi_xfm, self.csf_mask_dwi
        )
        reg_mri_pngs(self.csf_mask_dwi, self.nodif_B0, self.qa_reg)
        reg_utils.applyxfm(
            self.nodif_B0, self.gm_mask, self.t1wtissue2dwi_xfm, self.gm_in_dwi
        )
        reg_mri_pngs(self.gm_in_dwi, self.nodif_B0, self.qa_reg)
        reg_utils.applyxfm(
            self.nodif_B0, self.wm_mask, self.t1wtissue2dwi_xfm, self.wm_in_dwi
        )
        reg_mri_pngs(self.wm_in_dwi, self.nodif_B0, self.qa_reg)

        # Threshold WM to binary in dwi space
        thr_img = nib.load(self.wm_in_dwi)
        thr_img.get_data()[thr_img.get_data() < 0.15] = 0
        nib.save(thr_img, self.wm_in_dwi_bin)

        # Threshold GM to binary in dwi space
        thr_img = nib.load(self.gm_in_dwi)
        thr_img.get_data()[thr_img.get_data() < 0.15] = 0
        nib.save(thr_img, self.gm_in_dwi_bin)

        # Threshold CSF to binary in dwi space
        thr_img = nib.load(self.csf_mask_dwi)
        thr_img.get_data()[thr_img.get_data() < 0.99] = 0
        nib.save(thr_img, self.csf_mask_dwi)

        # Threshold WM to binary in dwi space
        self.t_img = load_img(self.wm_in_dwi_bin)
        self.mask = math_img("img > 0", img=self.t_img)
        self.mask.to_filename(self.wm_in_dwi_bin)

        # Threshold GM to binary in dwi space
        self.t_img = load_img(self.gm_in_dwi_bin)
        self.mask = math_img("img > 0", img=self.t_img)
        self.mask.to_filename(self.gm_in_dwi_bin)

        # Threshold CSF to binary in dwi space
        self.t_img = load_img(self.csf_mask_dwi)
        self.mask = math_img("img > 0", img=self.t_img)
        self.mask.to_filename(self.csf_mask_dwi_bin)

        # Create ventricular CSF mask
        print("Creating ventricular CSF mask...")
        cmd = f"fslmaths {self.vent_mask_dwi} -kernel sphere 10 -ero -bin {self.vent_mask_dwi}"
        gen_utils.run(cmd)
        print("Creating Corpus Callosum mask...")
        cmd = f"fslmaths {self.corpuscallosum_dwi} -mas {self.wm_in_dwi_bin} -bin {self.corpuscallosum_dwi}"
        gen_utils.run(cmd)
        cmd = f"fslmaths {self.csf_mask_dwi} -add {self.vent_mask_dwi} -bin {self.vent_csf_in_dwi}"
        gen_utils.run(cmd)

        # Create gm-wm interface image
        cmd = (
            f"fslmaths {self.gm_in_dwi_bin} -mul {self.wm_in_dwi_bin} -add {self.corpuscallosum_dwi} "
            f"-sub {self.vent_csf_in_dwi} -mas {self.nodif_B0_mask} -bin {self.wm_gm_int_in_dwi}"
        )
        gen_utils.run(cmd)
