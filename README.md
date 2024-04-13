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
- made to work on Python 3.7-3.10;
- is wrapped in a [Docker container](https://hub.docker.com/r/neurodata/m2g);
- has install instructions via a Dockerfile;
- requires no non-standard hardware to run;
- has key features built upon FSL, AFNI, INDI, Dipy, Nibabel, Nilearn, Networkx, Numpy, Scipy, Scikit-Learn, and others
  - For Python package version numbers, see [requirements.txt](requirements.txt)
  - For binaries required to install AFNI, FSL, INDI, ICA_AROMA, see the [Dockerfile](Dockerfile)
- takes approximately 1-core, < 16-GB of RAM, and 1-2 hours to run for most datasets (varies based on data).

# Installation

Instructions can be found within our documentation: https://docs.neurodata.io/m2g/install.html

# Usage

Instructions can be found within our [documentation](https://docs.neurodata.io/m2g/usage.html) and a demo can be found [here](https://docs.neurodata.io/m2g/usage.html#demo).

# License

This project is covered under the [Polyform License](https://github.com/neurodata/m2g/blob/deploy/LICENSE).

# Issues

If you're having trouble, notice a bug, or want to contribute (such as a fix to the bug you may have just found) feel free to open a git issue or pull request. Enjoy!

# Citing `m2g`

If you find `m2g` useful in your work, please cite the package via the [m2g paper](https://www.biorxiv.org/content/10.1101/2021.11.01.466686)

> Chung, J., Lawrence, R., Loftus, A., Kiar, G., Bridgeford, E. W., Roncal, W. G., Chandrashekhar, V., ... & Consortium for Reliability and Reproducibility (CoRR). (2024). A low-resource reliable pipeline to democratize multi-modal connectome estimation and analysis. bioRxiv, 2024-04.
