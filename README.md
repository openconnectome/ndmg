# ndmg

![Downloads shield](https://img.shields.io/pypi/dm/m2g.svg)
[![PyPI](https://img.shields.io/pypi/v/m2g.svg)](https://pypi.python.org/pypi/m2g)
[![Travis CI](https://travis-ci.org/neurodata/m2g.svg?branch=deploy)](https://travis-ci.org/github/neurodata/m2g)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.595684.svg)](https://doi.org/10.5281/zenodo.595684)
[![Code Climate](https://codeclimate.com/github/neurodata/ndmg/badges/gpa.svg)](https://codeclimate.com/github/neurodata/ndmg)
[![DockerHub](https://img.shields.io/docker/pulls/bids/ndmg.svg)](https://hub.docker.com/r/bids/ndmg)

NeuroData's MR Graphs package, **ndmg** (pronounced "**_nutmeg_**"), is a turn-key pipeline which uses structural and diffusion MRI data to estimate multi-resolution connectomes reliably and scalably.

## Contents

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

## Overview

The **ndmg** pipeline has been developed as a one-click solution for human connectome estimation by providing robust and reliable estimates of connectivity across a wide range of datasets. The pipelines are explained and derivatives analyzed in our pre-print, available on [BiorXiv](https://www.biorxiv.org/content/early/2017/09/16/188706).

## System Requirements

The **ndmg** pipeline:

- was developed and tested primarily on Mac OSX, Ubuntu (12, 14, 16, 18), and CentOS (5, 6);
- made to work on Python 3.6;
- is wrapped in a [Docker container](https://hub.docker.com/r/bids/ndmg/);
- has install instructions via a [Dockerfile](https://github.com/BIDS-Apps/ndmg/blob/master/Dockerfile#L6);
- requires no non-standard hardware to run;
- has key features built upon FSL, AFNI, Dipy, Nibabel, Nilearn, Networkx, Numpy, Scipy, Scikit-Learn, and others;
- takes approximately 1-core, 8-GB of RAM, and 1 hour to run for most datasets.

## Installation Guide

**ndmg** relies on [FSL](http://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation), [AFNI](https://afni.nimh.nih.gov/), [Dipy](http://nipy.org/dipy/), [networkx](https://networkx.github.io/), and [nibabel](http://nipy.org/nibabel/), [numpy](http://www.numpy.org/) [scipy](http://www.scipy.org/), [scikit-learn](http://scikit-learn.org/stable/), [scikit-image](http://scikit-image.org/), [nilearn](http://nilearn.github.io/). You should install FSL and AFNI through the instructions on their website, then install other Python dependencies as well as the package itself with the following:

    git clone https://github.com/neurodata/ndmg.git
    cd ndmg
    pip install -r requirements.txt
    pip install .

For the most up-to-date version of ndmg, you can use the staging branch. This version is updated regularly, but may be less stable:

    git clone https://github.com/neurodata/ndmg.git
    cd ndmg
    git checkout staging
    pip install -r requirements.txt
    pip install .

You can also install **ndmg** from `pip` as shown below. Installation shouldn't take more than a few minutes, but depends on your internet connection. Note that to install the most up-to-date version of the pipeline, we currently recommend installing from github.

### Install from pip

    pip install ndmg

## Docker

**ndmg** is available through Dockerhub, and the most recent docker image can be pulled using:

    docker pull neurodata/ndmg_dev:latest

The image can then be used to create a container and run directly with the following command (and any additional options you may require for Docker, such as volume mounting):

    docker run -ti --entrypoint /bin/bash neurodata/ndmg_dev:latest

**ndmg** docker containers can also be made from ndmg's Dockerfile.

    git clone https://github.com/neurodata/ndmg.git
    cd ndmg
    docker build -t <imagename:uniquelabel> .

Where "uniquelabel" can be whatever you wish to call this Docker image (for example, ndmg:latest). Additional information about building Docker images can be found [here](https://docs.docker.com/engine/reference/commandline/image_build/).
Creating the Docker image should take several minutes if this is the first time you have used this docker file.
In order to create a docker container from the docker image and access it, use the following command to both create and enter the container:

    docker run -it --entrypoint /bin/bash ndmg:uniquelabel
    
Note that `ndmg` has particularly high RAM requirements, and docker containers are given low memory by default. We recommend changing the default preferences to give docker access to at least 6 GB of RAM.

## Tutorial

Once you have the pipeline up and running, you can run it with:
  
 ndmg <input_directory> <output_directory>
  
We recommend specifying an atlas and lowering the default seed density on test runs:

    ndmg --seeds 1 --parcellation desikan <input_directory> <output_directory>

You can set a particular scan and session as well (recommended for batch scripts):

    ndmg --seeds 1 --parcellation desikan --participant_label <label> --session_label <label> <input_directory> <output_directory>

For more detailed instructions, tutorials on the **ndmg** pipeline can be found in [ndmg/tutorials](https://github.com/neurodata/ndmg/tree/staging/tutorials)

## Outputs

The organization of the output files generated by the ndmg pipeline are shown below. If you only care about the connectome edgelists (**ndmg**'s fundamental output), you can find them in `/output/dwi/roi-connectomes`.

```
File labels that may appear on output files, these denote additional actions ndmg may have done:
RAS = File was originally in RAS orientation, so no reorientation was necessary
reor_RAS = File has been reoriented into RAS+ orientation
nores = File originally had the desired voxel size specified by the user (default 2mmx2mmx2mm), resulting in no reslicing
res = The file has been resliced to the desired voxel size specified by the user

/output
     /anat
          /preproc
               Files created during the preprocessing of the anatomical data
                   t1w_aligned_mni.nii.gz = preprocessed t1w_brain anatomical image in mni space
                   t1w_brain.nii.gz = t1w anatomical image with only the brain
                   t1w_seg_mixeltype.nii.gz = mixeltype image of t1w image (denotes where there are more than one tissue type in each voxel)
                   t1w_seg_pve_0.nii.gz = probability map of Cerebrospinal fluid for original t1w image
                   t1w_seg_pve_1.nii.gz = probability map of grey matter for original t1w image
                   t1w_seg_pve_2.nii.gz = probability map of white matter for original t1w image
                   t1w_seg_pveseg.nii.gz = t1w image mapping wm, gm, ventricle, and csf areas
                   t1w_wm_thr.nii.gz = binary white matter mask for resliced t1w image

          /registered
               Files created during the registration process
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
          /preproc
               Files created during the preprocessing of the dwi data
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
          /roi-connectomes
               Location of connectome(s) created by the pipeline, with a directory given to each atlas you use for your analysis
          /tensor
               Contains the rgb tensor file(s) for the dwi data if tractography is being done in MNI space
     /qa
          /adjacency
          /fibers
          /graphs
          /graphs_plotting
               Png file of an adjacency matrix made from the connectome
          /mri
          /reg
          /tensor
     /tmp
          /reg_a
               Intermediate files created during the processing of the anatomical data
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

          /reg_m
               Intermediate files created during the processing of the diffusion data
                    dwi2t1w_bbr_xfm.mat = affine transform matrix of t1w_wm_edge.nii.gz to t1w space
                    dwi2t1w_xfm.mat = inverse transform matrix of t1w2dwi_xfm.mat
                    roi_2_mni.mat = affine transform matrix of selected atlas to mni space
                    t1w2dwi_bbr_xfm.mat = inverse transform matrix of dwi2t1w_bbr_xfm.mat
                    t1w2dwi_xfm.mat = affine transform matrix of t1w_brain.nii.gz to nodif_B0.nii.gz space
                    t1wtissue2dwi_xfm.mat = affine transform matrix of t1w_brain.nii.gz to nodif_B0.nii.gz, using t1w2dwi_bbr_xfm.mat or t1w2dwi_xfm.mat as a starting point
                    xfm_mni2t1w_init.mat = inverse transform matrix of xfm_t1w2mni_init.mat
                    xfm_t1w2mni_init.mat = affine transform matrix of preprocessed t1w_brain to mni space
```

Other files may end up in the output folders, depending on what settings or atlases you choose to use. Using MNI space for tractography or setting `--clean` to `True` will result in fewer files.

## Usage

The **ndmg** pipeline can be used to generate connectomes as a command-line utility on [BIDS datasets](http://bids.neuroimaging.io) with the following:

    ndmg /input/bids/dataset /output/directory

Note that more options are available which can be helpful if running on the Amazon cloud, which can be found and documented by running `ndmg -h`.
If running with the Docker container shown above, the `entrypoint` is already set to `ndmg`, so the pipeline can be run directly from the host-system command line as follows:

    docker run -ti -v /path/to/local/data:/data neurodata/ndmg_dev /data/ /data/outputs

This will run **ndmg** on the local data and save the output files to the directory /path/to/local/data/outputs. Note that if you have created the docker image from github, replace `neurodata/ndmg_dev` with `imagename:uniquelabel`.

Also note that currently, running `ndmg` on a single bids-formatted dataset directory only runs a single scan. To run the entire dataset, we recommend parallelizing on a high-performance cluster or using `ndmg`'s s3 integration.

## Working with S3 Datasets

**ndmg** has the ability to work on datasets stored on [Amazon's Simple Storage Service](https://aws.amazon.com/s3/), assuming they are in BIDS format. Doing so requires you to set your AWS credentials and read the related s3 bucket documentation. You can find a guide [here](https://github.com/neurodata/ndmg/blob/deploy/tutorials/Batch.ipynb).

## Example Datasets

Derivatives have been produced on a variety of datasets, all of which are made available on [our website](http://m2g.io). Each of these datsets is available for access and download from their respective sources. Alternatively, example datasets on the [BIDS website](http://bids.neuroimaging.io) which contain diffusion data can be used and have been tested; `ds114`, for example.

For some downsampled test data, see [neuroparc](https://github.com/neurodata/neuroparc/tree/master/data/)

## Documentation

Check out some [resources](http://m2g.io) on our website, or our [function reference](https://ndmg.neurodata.io/) for more information about **ndmg**.

## License

This project is covered under the [Apache 2.0 License](https://github.com/neurodata/ndmg/blob/ndmg/LICENSE.txt).

## Manuscript Reproduction

The figures produced in our manuscript linked in the [Overview](#overview) are all generated from code contained within Jupyter notebooks and made available at our [paper's Github repository](https://github.com/neurodata/ndmg-paper).

## Issues

If you're having trouble, notice a bug, or want to contribute (such as a fix to the bug you may have just found) feel free to open a git issue or pull request. Enjoy!
