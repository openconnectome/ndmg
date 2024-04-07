.. m2g documentation master file, created by
   sphinx-quickstart on Wed Dec 19 13:35:38 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. _BiorXiv: https://www.biorxiv.org/content/early/2018/04/24/188706

m2g
================================

NeuroData’s MR Graphs package, m2g (pronounced “nutmeg”), is the successor of the MRCAP, MIGRAINE, and m2g pipelines. m2g combines dMRI and sMRI data from a single subject to estimate a high-level connectome reliably and scalably.

The m2g pipeline has been developed as a one-click solution for human connectome estimation by providing robust and reliable estimates of connectivity across a wide range of datasets. The pipelines are explained and derivatives analyzed in our pre-print, available on BiorXiv_.

.. toctree::
   :caption: Tutorials
   :maxdepth: 3

   tutorials/install
   tutorials/funcref

.. toctree::
   :caption: Pipeline Overview
   :maxdepth: 2

   pipeline/diffusion
   pipeline/functional

.. toctree::
   :caption: Function Reference
   :maxdepth: 1

.. toctree::
   :maxdepth: 1
   :caption: Useful Links

   m2g @ GitHub <http://www.github.com/neurodata/m2g/>
   m2g @ PyPI <https://pypi.org/project/m2g/>
   Issue Tracker <https://github.com/neurodata/m2g/issues>
