# m2g

![Downloads shield](https://img.shields.io/pypi/dm/m2g.svg)
[![PyPI](https://img.shields.io/pypi/v/m2g.svg)](https://pypi.python.org/pypi/m2g)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.595684.svg)](https://doi.org/10.5281/zenodo.595684)
[![Code Climate](https://codeclimate.com/github/neurodata/ndmg/badges/gpa.svg)](https://codeclimate.com/github/neurodata/ndmg)
[![DockerHub](https://img.shields.io/docker/pulls/neurodata/m2g.svg)](https://hub.docker.com/r/neurodata/m2g)

NeuroData's MR Graphs package, **m2g**, is a turn-key pipeline which uses structural and diffusion MRI data to estimate multi-resolution connectomes reliably and scalably.

# Contents

- [Overview](#overview)
- [Documentation](#documentation)
- [System Requirements](#system-requirements)
- [Installation Guide](#installation-guide)
- [Usage](#usage)
- [License](#license)
- [Issues](#issues)
- [Citing `m2g`](#citing-m2g)

# Overview

The **m2g** pipeline has been developed as a beginner-friendly solution for human connectome estimation by providing robust and reliable estimates of connectivity across a wide range of datasets. The pipelines are explained and derivatives analyzed in our pre-print, available on [BiorXiv](https://www.biorxiv.org/content/10.1101/2021.11.01.466686v1.full).

# Documentation

Check out some [resources](http://m2g.io) on our website, or our [function reference](https://ndmg.neurodata.io/) for more information about **m2g**.

# System Requirements

## Hardware Requirements

**m2g** pipelines requires only a standard computer with enough RAM (< 16 GB).

## Software Requirements

The **m2g** pipeline:

- was developed and tested primarily on Mac OS (10,11), Ubuntu (16, 18, 20), and CentOS (5, 6);
- made to work on Python 3.8;
- is wrapped in a [Docker container](https://hub.docker.com/r/neurodata/m2g);
- has install instructions via a Dockerfile;
- requires no non-standard hardware to run;
- has key features built upon FSL, AFNI, INDI, Dipy, Nibabel, Nilearn, Networkx, Numpy, Scipy, Scikit-Learn, and others
  - For Python package version numbers, see [requirements.txt](requirements.txt)
  - For binaries required to install AFNI, FSL, INDI, ICA_AROMA, see the [Dockerfile](Dockerfile)
- takes approximately 1-core, < 16-GB of RAM, and 1-2 hours to run for most datasets (varies based on data).

# Installation Guide

Installation and running **m2g** requires both python and docker.

Docker is required to run **m2g** or **CPAC** on your local machine. If you do not have Docker installed, you can download it [here](https://docs.docker.com/get-docker/).

This is because while m2g can run on its own, CPAC will require a Docker container to run. As such, for convienience, we recommend using the Docker container for both.

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

## Demo

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

## Docker Container Usage

If running with the Docker container shown above, the `entrypoint` is already set to `m2g`, so the pipeline can be run directly from the host-system command line as follows:

    docker run -ti -v /path/to/local/data:/data neurodata/m2g /data/ /data/outputs

This will run **m2g** on the local data and save the output files to the directory /path/to/local/data/outputs. Note that if you have created the docker image from github, replace `neurodata/m2g` with `imagename:uniquelabel`.

Also note that currently, running `m2g` on a single bids-formatted dataset directory only runs a single scan. To run the entire dataset, we recommend parallelizing on a high-performance cluster or using `m2g`'s s3 integration.

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

## Working with S3 Datasets

**m2g** has the ability to work on datasets stored on [Amazon's Simple Storage Service](https://aws.amazon.com/s3/), assuming they are in BIDS format. Doing so requires you to set your AWS credentials and read the related s3 bucket documentation. You can find a guide [here](https://github.com/neurodata/m2g/blob/deploy/tutorials/Batch.ipynb).

## Example Datasets

Derivatives have been produced on a variety of datasets, all of which are made available on [our website](http://m2g.io). Each of these datsets is available for access and download from their respective sources. Alternatively, example datasets on the [BIDS website](http://bids.neuroimaging.io) which contain diffusion data can be used and have been tested; `ds114`, for example.

# License

This project is covered under the [Polyform License](https://github.com/neurodata/m2g/blob/deploy/LICENSE).

# Issues

If you're having trouble, notice a bug, or want to contribute (such as a fix to the bug you may have just found) feel free to open a git issue or pull request. Enjoy!

# Citing `m2g`

If you find `m2g` useful in your work, please cite the package via the [m2g paper](https://www.biorxiv.org/content/10.1101/2021.11.01.466686)

> Chung, J., Lawrence, R., Loftus, A., Kiar, G., Bridgeford, E. W., Roncal, W. G., Chandrashekhar, V., ... & Consortium for Reliability and Reproducibility (CoRR). (2024). A low-resource reliable pipeline to democratize multi-modal connectome estimation and analysis. bioRxiv, 2024-04.

## Manuscript Reproduction

The figures produced in our manuscript linked in the [Overview](#overview) are all generated from code contained within Jupyter notebooks and made available at our [paper's Github repository](https://github.com/neurodata/ndmg-paper).
