# m2g

![Downloads shield](https://img.shields.io/pypi/dm/m2g.svg)
[![PyPI](https://img.shields.io/pypi/v/m2g.svg)](https://pypi.python.org/pypi/m2g)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.595684.svg)](https://doi.org/10.5281/zenodo.595684)
[![Code Climate](https://codeclimate.com/github/neurodata/ndmg/badges/gpa.svg)](https://codeclimate.com/github/neurodata/ndmg)
[![DockerHub](https://img.shields.io/docker/pulls/neurodata/m2g.svg)](https://hub.docker.com/r/neurodata/m2g)

NeuroData's MR Graphs package, **m2g**, is a turn-key pipeline which uses structural and diffusion MRI data to estimate multi-resolution connectomes reliably and scalably.

# Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Installation Guide](#installation-guide)
- [Docker](#docker)
- [Tutorial](#tutorial)
- [Outputs](#outputs)
- [Usage](#usage)
- [Working with S3 Datasets](#Working-with-S3-Datasets)
- [Example Datasets](#example-datasets)
- [Documentation](#documentation)
- [License](#license)
- [Manuscript Reproduction](#manuscript-reproduction)
- [Issues](#issues)

# Overview

The **m2g** pipeline has been developed as a beginner-friendly solution for human connectome estimation by providing robust and reliable estimates of connectivity across a wide range of datasets. The pipelines are explained and derivatives analyzed in our pre-print, available on [BiorXiv](https://www.biorxiv.org/content/10.1101/2021.11.01.466686v1.full).

# System Requirements

The **m2g** pipeline:

- was developed and tested primarily on Mac OS (10,11), Ubuntu (16, 18, 20), and CentOS (5, 6);
- made to work on Python 3.7;
- is wrapped in a [Docker container](https://hub.docker.com/r/neurodata/m2g);
- has install instructions via a Dockerfile;
- requires no non-standard hardware to run;
- has key features built upon FSL, AFNI, INDI, Dipy, Nibabel, Nilearn, Networkx, Numpy, Scipy, Scikit-Learn, and others
  - For Python package version numbers, see [requirements.txt](requirements.txt)
  - For binaries required to install AFNI, FSL, INDI, ICA_AROMA, see the [Dockerfile](Dockerfile)
- takes approximately 1-core, < 16-GB of RAM, and 1-2 hours to run for most datasets (varies based on data).

# Demo

To install and run a tutorial of the latest Docker image of m2g, pull the docker image from DockerHub using the following command. Then enter it using `docker run`:

```
docker pull neurodata/m2g:latest
docker run -ti --entrypoint /bin/bash neurodata/m2g:latest
```

Once inside of the Docker container, download a tutorial dataset of fMRI and diffusion MRI data from the `open-neurodata` AWS S3 bucket to the `/input` directory in your container (make sure you are connected to the internet):

```
aws s3 sync --no-sign-request s3://open-neurodata/m2g/TUTORIAL /input
```

Now you can run the `m2g` pipeline for both the functional and diffusion MRI data using the command below. The number of `seeds` is intentionally set lower than recommended, along with a larger than recommended `voxelsize` for a faster run time (approximately 25 minutes). For more information as to what these input arguments represent, see the Tutorial section below.

```
m2g --participant_label 0025864 --session_label 1 --parcellation AAL_ --pipeline both --seeds 1 --voxelsize 4mm /input /output
```

Once the pipeline is done running, the resulting outputs can be found in `/output/sub-0025864/ses-1/`, see Outputs section below for a description of each file.

# Installation Guide

## Docker

While you can install **m2g** from `pip` using the command `pip install m2g`, as there are several dependencies needed for both **m2g** and **CPAC**, it is highly recommended to use **m2g** through a docker container:

**m2g** is available through Dockerhub, and the most recent docker image can be pulled using:

    docker pull neurodata/m2g:latest

The image can then be used to create a container and run directly with the following command (and any additional options you may require for Docker, such as volume mounting):

    docker run -ti --entrypoint /bin/bash neurodata/m2g:latest

**m2g** docker containers can also be made from m2g's Dockerfile.

    git clone https://github.com/neurodata/m2g.git
    cd m2g
    docker build -t <imagename:uniquelabel> .

Where "uniquelabel" can be whatever you wish to call this Docker image (for example, m2g:latest). Additional information about building Docker images can be found [here](https://docs.docker.com/engine/reference/commandline/image_build/).
Creating the Docker image should take several minutes if this is the first time you have used this docker file.
In order to create a docker container from the docker image and access it, use the following command to both create and enter the container:

    docker run -it --entrypoint /bin/bash m2g:uniquelabel

## Local Installation [COMING SOON]

We highly recommend the use of the Docker container provided above.

Due to the versioning required for CPAC, along with `m2g-d`, we are currently working on streamlining the installation of `m2g`. Stay tuned for updates.

- Requires numerous system level dependencies with specified versions. As such, CPAC on its own runs on a docker container, and we recommond the usage

# Usage

The **m2g** pipeline can be used to generate connectomes as a command-line utility on [BIDS datasets](http://bids.neuroimaging.io) with the following:

    m2g --pipeline <pipe> /input/bids/dataset /output/directory

Note that more options are available which can be helpful if running on the Amazon cloud, which can be found and documented by running `m2g -h`.

## Docker Container Usage

If running with the Docker container shown above, the `entrypoint` is already set to `m2g`, so the pipeline can be run directly from the host-system command line as follows:

    docker run -ti -v /path/to/local/data:/data neurodata/m2g /data/ /data/outputs

This will run **m2g** on the local data and save the output files to the directory /path/to/local/data/outputs. Note that if you have created the docker image from github, replace `neurodata/m2g` with `imagename:uniquelabel`.

Also note that currently, running `m2g` on a single bids-formatted dataset directory only runs a single scan. To run the entire dataset, we recommend parallelizing on a high-performance cluster or using `m2g`'s s3 integration.

# Tutorial

## Structural Connectome Pipeline (`m2g-d`)

Once you have the pipeline up and running, you can run the structural connectome pipeline with:

    m2g --pipeline dwi <input_directory> <output_directory>

We recommend specifying an atlas and lowering the default seed density on test runs (although, for real runs, we recommend using the default seeding -- lowering seeding simply decreases runtime):

    m2g --pipeline dwi --seeds 1 --parcellation Desikan <input_directory> <output_directory>

You can set a particular scan and session as well (recommended for batch scripts):

    m2g --pipeline dwi --seeds 1 --parcellation Desikan --participant_label <label> --session_label <label> <input_directory> <output_directory>

## Functional Connectome Pipeline (`m2g-f`)

Once you have the pipeline up and running, you can run the functional connectome pipeline with:

    m2g --pipeline func <input_directory> <output_directory>

We recommend specifying an atlas and lowering the default seed density on test runs (although, for real runs, we recommend using the default seeding -- lowering seeding simply decreases runtime):

    m2g --pipeline func --seeds 1 --parcellation Desikan <input_directory> <output_directory>

You can set a particular scan and session as well (recommended for batch scripts):

    m2g --pipeline func --seeds 1 --parcellation Desikan --participant_label <label> --session_label <label> <input_directory> <output_directory>

## Running both `m2g-d` and `m2g-f`

Both pipelines can be run by setting the `pipeline` parameter to `both`:

    m2g --pipeline both <input_directory> <output_directory>

# Outputs

## Diffusion Pipeline

The organization of the output files generated by the m2g-d pipeline are shown below. If you only care about the connectome edgelists (**m2g**'s fundamental output), you can find them in `/output/connectomes_d`.

```
File labels that may appear on output files, these denote additional actions m2g may have done:
RAS = File was originally in RAS orientation, so no reorientation was necessary
reor_RAS = File has been reoriented into RAS+ orientation
nores = File originally had the desired voxel size specified by the user (default 2mmx2mmx2mm), resulting in no reslicing
res = The file has been resliced to the desired voxel size specified by the user

/output
    /anat_d

        /preproc
            t1w_aligned_mni.nii.gz = preprocessed t1w_brain anatomical image in mni space
            t1w_brain.nii.gz = t1w anatomical image with only the brain
            t1w_seg_mixeltype.nii.gz = mixeltype image of t1w image (denotes where there are more than one tissue type in each voxel)
            t1w_seg_pve_0.nii.gz = probability map of Cerebrospinal fluid for original t1w image
            t1w_seg_pve_1.nii.gz = probability map of grey matter for original t1w image
            t1w_seg_pve_2.nii.gz = probability map of white matter for original t1w image
            t1w_seg_pveseg.nii.gz = t1w image mapping wm, gm, ventricle, and csf areas
            t1w_wm_thr.nii.gz = binary white matter mask for resliced t1w image

        /registered
            t1w_corpuscallosum.nii.gz = atlas corpus callosum mask in t1w space
            t1w_corpuscallosum_dwi.nii.gz = atlas corpus callosum in dwi space
            t1w_csf_mask_dwi.nii.gz = t1w csf mask in dwi space
            t1w_gm_in_dwi.nii.gz = t1w grey matter probability map in dwi space
            t1w_in_dwi.nii.gz = t1w in dwi space
            t1w_wm_gm_int_in_dwi.nii.gz = t1w white matter-grey matter interfact in dwi space
            t1w_wm_gm_int_in_dwi_bin.nii.gz = binary mask of t12_2m_gm_int_in_dwi.nii.gz
            t1w_wm_in_dwi.nii.gz = atlas white matter probability map in dwi space

    /dwi
        /fiber
            Streamline track file(s)

        /preproc    (files created during the preprocessing of the dwi data)
            #_B0.nii.gz = B0 image (there can be multiple B0 images per dwi file, # is the numerical location of each B0 image)
            bval.bval = original b-values for dwi image
            bvec.bvec = original b-vectors for dwi image
            bvecs_reor.bvecs = bvec_scaled.bvec data reoriented to RAS+ orientation
            bvec_scaled.bvec = b-vectors normalized to be of unit length, only non-zero b-values are changed
            eddy_corrected_data.nii.gz = eddy corrected dwi image
            eddy_corrected_data.ecclog = eddy correction log output
            eddy_corrected_data_reor_RAS.nii.gz = eddy corrected dwi image reoriented to RAS orientation
            eddy_corrected_data_reor_RAS_res.nii.gz = eddy corrected image reoriented to RAS orientation and resliced to desired voxel resolution
            nodif_B0.nii.gz = mean of all B0 images
            nodif_B0_bet.nii.gz = nodif_B0 image with all non-brain matter removed
            nodif_B0_bet_mask.nii.gz = mask of nodif_B0_bet.nii.gz brain
            tensor_fa.nii.gz = tensor image fractional anisotropy map

        /tensor
            Contains the rgb tensor file(s) for the dwi data if tractography is being done in MNI space

    /connectomes_d
            Location of connectome(s) created by the pipeline, with a directory given to each atlas you use for your analysis

    /qa_d
        /graphs_plotting
            Png file of an adjacency matrix made from the connectome
        /reg
            <atlas>_atlas_2_nodif_B0_bet.png = overlay of registered atlas on top of anatomical image
            qa_fast.png = overlay of white/grey matter and csf regions on top of anatomical image
            t1w_aligned_mni_2_MNI152_T1_<vox>_brain.png = overlay of registered anatomical image on top of MNI152 anatomical reference image
            t1w_corpuscallosum_dwi_2_nodif_B0_bet.png = corpus callosum region highlighted on registered anatomical image
            t1w_csf_mask_dwi_2_nodif_B0_bet.png = overlay of csf mask on top of registered anatomical image
            t1w_gm_in_dwi_2_nodif_B0_bet.png = overlay of grey matter mask on top of registered anatomical image
            t1w_in_dwi_2_nodif_B0_bet.png = overlay of dwi image on top of anatomical image registered to dwi space
            t1w_vent_mask_dwi_2_nodif_B0_bet.png = display of ventrical masks
            t1w_wm_in_dwi_2_nodif_B0_bet.png = overlay of white matter mask on top of registered anatomical image
        /skull_strip
            qa_skullstrip__<sub>_<ses>_T1w_reor_RAS_res.png = overlay of skullstripped anatomical image on top of original anatomical image

    /tmp_d
        /reg_a (Intermediate files created during the processing of the anatomical data)
            mni2t1w_warp.nii.gz = nonlinear warp coefficients/fields for mni to t1w space
            t1w_csf_mask_dwi_bin.nii.gz = binary mask of t1w_csf_mask_dwi.nii.gz
            t1w_gm_in_dwi_bin.nii.gz = binary mask of t12_gm_in_dwi.nii.gz
            t1w_vent_csf_in_dwi.nii.gz = t1w ventricle+csf mask in dwi space
            t1w_vent_mask_dwi.nii.gz = atlas ventricle mask in dwi space
            t1w_wm_edge.nii.gz = mask of the outer border of the resliced t1w white matter
            t1w_wm_in_dwi_bin.nii.gz = binary mask of t12_wm_in_dwi.nii.gz
            vent_mask_mni.nii.gz = altas ventricle mask in mni space using roi_2_mni_mat
            vent_mask_t1w.nii.gz = atlas ventricle mask in t1w space
            warp_t12mni.nii.gz = nonlinear warp coefficients/fields for t1w to mni space

        /reg_m (Intermediate files created during the processing of the diffusion data)
            dwi2t1w_bbr_xfm.mat = affine transform matrix of t1w_wm_edge.nii.gz to t1w space
            dwi2t1w_xfm.mat = inverse transform matrix of t1w2dwi_xfm.mat
            roi_2_mni.mat = affine transform matrix of selected atlas to mni space
            t1w2dwi_bbr_xfm.mat = inverse transform matrix of dwi2t1w_bbr_xfm.mat
            t1w2dwi_xfm.mat = affine transform matrix of t1w_brain.nii.gz to nodif_B0.nii.gz space
            t1wtissue2dwi_xfm.mat = affine transform matrix of t1w_brain.nii.gz to nodif_B0.nii.gz, using t1w2dwi_bbr_xfm.mat or t1w2dwi_xfm.mat as a starting point
            xfm_mni2t1w_init.mat = inverse transform matrix of xfm_t1w2mni_init.mat
            xfm_t1w2mni_init.mat = affine transform matrix of preprocessed t1w_brain to mni space
```

## Functional Pipeline

The organization of the output files generated by the m2g-f pipeline are shown below. If you only care about the connectome edgelists (**m2g**'s fundamental output), you can find them in `/output/connectomes_f`.

```
File labels that may appear on output files, these denote additional actions m2g may have done:
RAS = File was originally in RAS orientation, so no reorientation was necessary
reor_RAS = File has been reoriented into RAS+ orientation
nores = File originally had the desired voxel size specified by the user (default 2mmx2mmx2mm), resulting in no reslicing
res = The file has been resliced to the desired voxel size specified by the user

/output
    /anat_f
        /anatomical_brain
            <subject>_<session>_T1w_resample_calc.nii.gz = resampled and skullstripped brain from anatomical image
        /anatomical_brain_mask
            <subject>_<session>_T1w_resample_skullstrip_calc.nii.gz = mask of resampled and skullstripped brain from anatomical image
        /anatomical_csf_mask
            segment_seg_0_maths_maths.nii.gz = mask of csf area of anatomical image
        /anatomical_gm_mask
            segment_seg_1_maths_maths.nii.gz = mask of grey matter area of anatomical image
        /anatomical_reorient
            <subject>_<session>_T1w_resample.nii.gz = reorientated and resampled anatomical image
        /anatomical_to_mni_nonlinear_xfm
            <subject>_<session>_T1w_resample_fieldwarp.nii.gz = fieldwarp for registering the anatomical image to MNI space
        /anatomical_to_standard
            <subject>_<session>_T1w_resample_calc_warp.nii.gz = anatomical image registered to MNI space
        /anatomical_wm_mask
            segment_seg_2_maths_maths.nii.gz = mask of white matter area of anatomical image
        /seg_mixeltype
            segment_mixeltype.nii.gz = mixeltype representation of anatomical image
        /seg_partial_volume_files
            segment_pve_0.nii.gz = mask of grey matter regions of anatomical image
            segment_pve_1.nii.gz = mask of grey matter/white matter boundary of anatomical image
            segment_pve_2.nii.gz = mask of white matter regions of anatomical image
        /seg_partial_volume_map
            segment_pveseg.nii.gz = partial volume map of anatomical image
        /seg_probability_maps
            segment_prob_0.nii.gz = probability map of anatomical image for grey matter
            segment_prob_1.nii.gz = probability map of grey/white matter boundary
            segment_prob_2.nii.gz = probability map of anatomical image for white matter
    /connectomes_f
        /<atlas>
            <sub>_<ses>_func_<atlas>_abs_edgelist.csv = edgelist file for estimated connectome where the absolute value of the correlation is given
            <sub>_<ses>_func_<atlas>_edgelist.csv = edgelist file for estimated connectome
    /func
        /preproc
            /coordinate_transformation
                <subject>_<session>_task-rest_bold_calc_tshift_resample.aff12.1D =
            /frame_wise_displacement_jenkinson
                FD_J.1D = vector containing Jenkinson measurement of framewise displacement for each frame of the functional image file
            /frame_wise_displacement_power
                FD.1D = vector containing power of framewise displacement for each frame of the functional image file
            /functional_brain_mask
                <subject>_<session>_task-rest_bold_calc_tshift_resample_volreg_mask.nii.gz = brain mask for the functional image
            /functional_brain_mask_to_standard
                <subject>_<session>_task-rest_bold_calc_tshift_rasample_volreg_mask_warp.nii.gz = functional brain mask registered to MNI152 space
            /functional_freq_filtered
                bandpassed_demeaned_filtered.nii.gz = frequency filtered functional file
            /functional_nuisance_regressors
                nuisance_regressors.1D
            /functional_nuisance_residuals
                residuals.nii.gz
            /functional_preprocessed
                <subject>_<session>_task-rest_bold_calc_tshift_resample_volreg_calc_maths.nii.gz = skullstripped brain from motion corrected functional image file resampled to voxel dimensions specified by user
            /functional_preprocessed_mask
                <subject>_<session>_task-rest_bold_calc_tshift_resample_volreg_calc_maths_maths.nii.gz = mask for image contained in /functional_preprocessed
            /motion_correct
                <subject>_<session>_task-rest_bold_calc_tshift_resample_volreg.nii.gz = motion corrected functional image file resampled to voxel dimensions specified by user
            /motion_correct_to_standard_smooth
                /_fwhm_4
                    <subject>_<session>_task-rest_bold_calc_tshift_resample_volreg_warp_maths.nii.gz
            /motion_params
                motion_parameters.txt = statistical measurements of motion correction performed on functional image
            /raw_functional
                <subject>_<session>_task-rest_bold.nii.gz = unaltered input functional image
            /slice_time_corrected
                <subject>_<session>_task-rest_bold_calc_tshift.nii.gz = slice time corrected functional image
        /register
            /functional_to_anat_linear_xfm
                <subject>_<session>_task-rest_bold_calc_tshift_resample_volreg_calc_tstat_flirt.mat =
            /functional_to_standard
                bandpassed_demeaned_filtered_warp.nii.gz = bandpassed and demeaned filtered warp map for registering the functional image to MNI space
            /max_displacement
                max_displacement.1D
            /mean_functional
                <subject>_<session>_task-rest_bold_calc_tshift_resample_volreg_calc_tstat.nii.gz = mean functional image from all volumes
            /mean_functional_in_anat
                <subject>_<session>_task-rest_bold_calc_tshift_resample_volreg_calc_tstat_flirt.nii.gz = mean functional image registered to the anatomical image
            /mean_functional_to_standard
                <subject>_<session>_task-rest_bold_calc_tshift_resample_volreg_calc_tstat_warp.nii.gz = mean functional image registered to MNI space
            /movement_parameters
                <subject>_<session>_task-rest_bold_calc_tshift_resample.1D = movement parameters applied to each volumen of functional image
            /power_params
                pow_params.txt = different measurements on the power of functional images
            /roi_timeseries
                /<atlas>
                    roi_stats.csv = mean voxel intensity for each region of interest at each time point, used to calculate functional connectome
                    roi_stats.npz = pickeled version of roi_stats.csv

    /log_f
        callback.log = nipype log for modules made for pipeline
        cpac_data_config_<date>.yml = file containing functional and anatomical image directory location
        cpac_individual_timing_m2g.csv = record of the elapsed time from the run of m2g-f
        cpac_pipeline_config_<date>.yml = copy of CPAC configuration file
        functional_pipeline_settings.yaml = record of CPACP pipeline parameter settings
        pypeline.lock = intermediate file created for pipeline running
        pypeline.log = nipype log with record of everything printed to terminal
        subject_info_<subject>_<session>.pkl = pickle file of functional and anatomical file information

    /qa_f
        /carpet
            carpet_seg.png
        /csf_gm_wm_a
            montage_csf_gm_wm_a.png = axial view of mask of csf/grey matter/white matter regions overlaid on top of anatomical image
        /csf_gm_wm_s
            montage_csf_gm_wm_s.png = sagittal view of mask of csf/grey matter/white matter regions overlaid on top of anatomical image
        /mean_func_with_mni_edge_a
            MNI_edge_on_mean_func_mni_a.png = axial view of outline of MNI reference anatimical image overlaid on top of mean functional image
        /mean_func_with_mni_edge_s
            MNI_edge_on_mean_func_mni_s.png = sagittal view of outline of MNI reference anatimical image overlaid on top of mean functional image
        /mean_func_with_t1_edge_a
            t1_edge_on_mean_func_in_t1_a.png = axial view of outline of anatomical image overlaid on top of mean functional image registered to the anatomical image
        /mean_func_with_t1_edge_s
            t1_edge_on_mean_func_in_t1_s.png = sagittal view of outline of anatomical image overlaid on top of mean functional image registered to the anatomical image
        /mni_normalized_anatomical_a
            mni_anat_a.png = axial view of anatomical image registered to MNI image
        /mni_normalized_anatomical_s
            mni_anat_s.png = sagittal view of anatomical image registered to MNI image
        /movement_rot_plot
            motion_rot_plot.png = movement rotation plot for rotation correction of functional image
        /movement_trans_plot
            motion_trans_plot.png = movement translational plot for translation correction of functional image
        /skullstrip_vis_a
            skull_vis_a.png = axial view of original anatomical image overlaid on top of skullstripped anatomical image
        /skullstrip_vis_s
            skull_vis_s.png = sagittal view of original anatomical image overlaid on top of skullstripped anatomical imag
        /snr_a
            snr_a.png = axial view of signal to noise ratio for functional image
        /snr_hist
            snr_hist_plot.png = signal to noise ratio intensity plot
        /snr_s
            snr_s.png = sagittal view of signal to noise ratio for functional image
        /snr_val
            average_snr_file.txt = single value of average signal to noise ratio for functional image

```

## Working with S3 Datasets

**m2g** has the ability to work on datasets stored on [Amazon's Simple Storage Service](https://aws.amazon.com/s3/), assuming they are in BIDS format. Doing so requires you to set your AWS credentials and read the related s3 bucket documentation. You can find a guide [here](https://github.com/neurodata/m2g/blob/deploy/tutorials/Batch.ipynb).

## Example Datasets

Derivatives have been produced on a variety of datasets, all of which are made available on [our website](http://m2g.io). Each of these datsets is available for access and download from their respective sources. Alternatively, example datasets on the [BIDS website](http://bids.neuroimaging.io) which contain diffusion data can be used and have been tested; `ds114`, for example.

## Documentation

Check out some [resources](http://m2g.io) on our website, or our [function reference](https://ndmg.neurodata.io/) for more information about **m2g**.

## License

This project is covered under the [Apache 2.0 License](https://github.com/neurodata/m2g/blob/m2g/LICENSE.txt).

## Manuscript Reproduction

The figures produced in our manuscript linked in the [Overview](#overview) are all generated from code contained within Jupyter notebooks and made available at our [paper's Github repository](https://github.com/neurodata/ndmg-paper).

## Issues

If you're having trouble, notice a bug, or want to contribute (such as a fix to the bug you may have just found) feel free to open a git issue or pull request. Enjoy!
