.. include:: links.rst

------------
Installation
------------

.. contents:: Table of Contents

There are two ways to install **m2g**:

* using container technologies - `Docker Container`_ - (RECOMMENDED) or
* within a Manually Prepared Environment (For ``m2g-d`` pipeline).

However, the manually prepared environment is not recommended, as it is more complex and error-prone.


Docker Container
================================================
**m2g** is distributed as a Docker image, which is the recommended way to run the pipeline. See :doc:`Docker <./docker>`.

The Docker image contains all the necessary software dependencies, and the pipeline is executed in a containerized environment.
This ensures that the pipeline runs in a consistent environment, regardless of the host system.

The most recent docker image can be pulled using::

    $ docker pull neurodata/m2g:latest

The image can then be used to create a container and run directly with the following command (and any additional options you may require for Docker, such as volume mounting)::

    $ docker run -ti --entrypoint /bin/bash neurodata/m2g:latest

**m2g** docker containers can also be made from m2g's Dockerfile::

    $ git clone https://github.com/neurodata/m2g.git
    $ cd m2g
    $ docker build -t <imagename:uniquelabel> .

Where "uniquelabel" can be whatever you wish to call this Docker image (for example, `m2g:latest`).
Additional information about building Docker images can be found `here <https://docs.docker.com/engine/reference/commandline/image_build/>`_.
Creating the Docker image should take several minutes if this is the first time you have used this docker file.
In order to create a docker container from the docker image and access it, use the following command to both create and enter the container::

    $ docker run -it --entrypoint /bin/bash m2g:uniquelabel

Manually Prepared Environment (For ``m2g-d`` pipeline)
=======================================================

.. warning::

   This method is not recommended! Please consider using containers.

.. warning::

   Without Docker, you can only run ``m2g-d`` portion of the pipeline. ``m2g-f`` requires CPAC, which also runs
   on a Docker container.


Make sure all of **m2g**'s `External Dependencies`_ are installed.
These tools must be installed and their binaries available in the
system's ``$PATH``.
A relatively interpretable description of how your environment can be set-up
is found in the `Dockerfile <https://github.com/neurodata/m2g/blob/deploy/Dockerfile>`_.

On a functional Python 3.8 (or above) environment with ``pip`` installed,
**m2g** can be installed using the habitual command ::

    $ python -m pip install m2g

Check your installation with the ``--version`` argument ::

    $ m2g --version


External Dependencies
---------------------

**m2g** requires other neuroimaging software that are not handled by the Python's packaging system (Pypi):

- FSL_ (version 6.0.6.5)
- ANTs_ (version 2.4.3)
- AFNI_ (version 23.3.09)
- `C3D <https://sourceforge.net/projects/c3d/>`_ (version 1.3.0)


Requirements
====================

Hardware Requirements
---------------------

The pipeline only requires 1-core and 16-GB of RAM, and takes approximately 1 hour to run for most datasets.


Python Requirements
-------------------

The m2g pipeline was developed and tested for Python <=3.8 and <=3.10 on linux systems, such as Ubuntu, CentOS and macOS.
With `Docker execution`_, **m2g** can run on almost all systems that support Docker.

While m2g is quite robust to Python package versions (with only few exceptions, mentioned in the installation guide), an example of possible versions (taken from the m2g Docker Image with version v0.3.0) is shown below. ::

    boto3==1.28.4
    configparser>=3.7.4
    dipy==0.16.0
    graspologic>=3.3.0
    networkx==2.3
    nibabel==2.5.0
    nilearn==0.5.2
    numpy==1.17.0