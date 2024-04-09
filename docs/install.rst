.. include:: links.rst

------------
Installation
------------

.. contents:: Table of Contents

There are two ways to install **m2g**:

* using container technologies - `Docker execution`_ - (RECOMMENDED); or
* within a `Manually Prepared Environment (Python 3.10+)`_, also known as *bare-metal installation*.

However, the *bare-metal installation* is not recommended, as it is more complex and error-prone.


Docker Container
================================================
*m2g* is distributed as a Docker image, which is the recommended way to run the pipeline. See :doc:`Docker <./docker>`.

The Docker image contains all the necessary software dependencies, and the pipeline is executed in a containerized environment.
This ensures that the pipeline runs in a consistent environment, regardless of the host system.

Pull docker container::

    docker pull neurodata/m2g

Run ``m2g`` participant pipeline::

    docker run -ti -v /path/to/local/data:/data neurodata/m2g /data/ /data/outputs


Manually Prepared Environment (Python 3.10+)
============================================

.. warning::

   This method is not recommended! Please consider using containers.

Make sure all of *m2g*'s `External Dependencies`_ are installed.
These tools must be installed and their binaries available in the
system's ``$PATH``.
A relatively interpretable description of how your environment can be set-up
is found in the `Dockerfile <https://github.com/neurodata/m2g/blob/deploy/Dockerfile>`_.

On a functional Python 3.10 (or above) environment with ``pip`` installed,
*m2g* can be installed using the habitual command ::

    $ python -m pip install m2g

Check your installation with the ``--version`` argument ::

    $ m2g --version


External Dependencies
---------------------

.. warning::

   External dependencies may be difficult to install! Please consider using containers.

*m2g* requires other neuroimaging software that are not handled by the Python's packaging system (Pypi):

- FSL_ (version 6.0.6.2)
- ANTs_ (version 2.4.4)
- AFNI_ (version 23.1.05)
- `C3D <https://sourceforge.net/projects/c3d/>`_ (version 1.3.0)


Other Requirements
====================

Hardware Requirements
---------------------

The pipeline only requires 1-core and 8-GB of RAM, and takes approximately 1 hour to run for most datasets.


Python Requirements
-------------------

The m2g pipeline was developed and tested for >=Python3.8 on linux systems, such as Ubuntu, CentOS and macOS.
With `Docker execution`_, ``m2g`` can run on almost all systems that support Docker.

While m2g is quite robust to Python package versions (with only few exceptions, mentioned in the installation guide), an example of possible versions (taken from the m2g Docker Image with version v0.3.0) is shown below.
Note: this list excludes many libraries which are standard with a Python distribution, and a complete list with all packages and versions can be produced by running pip freeze within the Docker container mentioned above. ::

    awscli==1.16.210
     , boto3==1.9.200 , botocore==1.12.200 , colorama==0.3.9 , configparser>=3.7.4 ,
    Cython==0.29.13 , dipy==0.16.0 , duecredit==0.7.0 , fury==0.3.0 , graspologic==0.0.3 , ipython==7.7.0 ,
    matplotlib==3.1.1 , networkx==2.3 , nibabel==2.5.0 , nilearn==0.5.2 , numpy==1.17.0 , pandas==0.25.0,
    Pillow==6.1.0 , plotly==1.12.9, pybids==0.6.4 , python-dateutil==2.8.0 , PyVTK==0.5.18 ,
    requests==2.22.0 , s3transfer==0.2.1 , setuptools>=40.0 scikit-image==0.13.0 , scikit-learn==0.21.3 ,
    scipy==1.3.0 , sklearn==8.0 , vtk==8.1.2