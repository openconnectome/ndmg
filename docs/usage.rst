================================
Usage
================================


.. contents:: Table of Contents


Execution
================================


.. _Dockerhub : https://hub.docker.com/r/neurodata/m2g/
.. _documentation : https://docs.docker.com/

In order to share data between our container and the rest of our machine in Docker, we need to mount a volume.
Docker does this with the -v flag. Docker expects its input formatted as: ``-v path/to/local/data:/path/in/container``.
We'll do this when we launch our container, as well as give it a helpful name so we can locate it later on.

The ``neurodata/m2g`` Docker container enables users to run end-to-end connectome estimation on structural MRI or functional MRI right from container launch. The pipeline requires that data be organized in accordance with the BIDS spec. If the data you wish to process is available on S3 you simply need to provide your s3 credentials at build time and the pipeline will auto-retrieve your data for processing.

If you have never used Docker before, it is useful to run through the Docker documentation_.

**Getting Docker container**::

    $ docker pull neurodata/m2g

Structural Connectome Pipeline (`m2g-d`)
----------------------------------------

The structural connectome pipeline can be ran with::

    $ m2g --pipeline dwi <input_directory> <output_directory>

We recommend specifying an atlas and lowering the default seed density on test runs (although, for real runs, we recommend using the default seeding -- lowering seeding simply decreases runtime)::

    $ m2g --pipeline dwi --seeds 1 --parcellation Desikan <input_directory> <output_directory>

You can set a particular scan and session as well (recommended for batch scripts)::

    $ m2g --pipeline dwi --seeds 1 --parcellation Desikan --participant_label <label> --session_label <label> <input_directory> <output_directory>

The outputs of the pipeline are organized as described `here <diffusion.html#pipeline-outputs>`_.


Functional Connectome Pipeline (`m2g-f`)
----------------------------------------

The functional connectome pipeline can be ran with::

    $ m2g --pipeline func <input_directory> <output_directory>

or::

    $ m2g --pipeline func --parcellation Desikan <input_directory> <output_directory>

You can set a particular scan and session as well (recommended for batch scripts)::

    $ m2g --pipeline func --parcellation Desikan --participant_label <label> --session_label <label> <input_directory> <output_directory>

The outputs of the pipeline are organized as described `here <functional.html#pipeline-outputs>`_.



Running both `m2g-d` and `m2g-f`
--------------------------------

Both pipelines can be run by setting the `pipeline` parameter to `both`::

    $ m2g --pipeline both <input_directory> <output_directory>


Demo
=====

To install and run a tutorial of the latest Docker image of m2g, pull the docker image from DockerHub using the following command. Then enter it using `docker run`::

    $ docker pull neurodata/m2g:latest
    $ docker run -ti --entrypoint /bin/bash neurodata/m2g:latest

Once inside of the Docker container, download a tutorial dataset of fMRI and diffusion MRI data from the `open-neurodata <https://registry.opendata.aws/open-neurodata/>`_` AWS S3 bucket to the `/input` directory in your container (make sure you are connected to the internet)::

    $ aws s3 sync --no-sign-request s3://open-neurodata/m2g/TUTORIAL /input

Now you can run the `m2g` pipeline for both the functional and diffusion MRI data using the command below. The number of `seeds` is intentionally set lower than recommended, along with a larger than recommended `voxelsize` for a faster run time (approximately 25 minutes). For more information as to what these input arguments represent, see the Tutorial section below.::

    $ m2g --participant_label 0025864 --session_label 1 --parcellation AAL_ --pipeline both --seeds 1 --voxelsize 4mm /input /output

Once the pipeline is done running, the resulting outputs can be found in `/output/sub-0025864/ses-1/`, see Outputs section below for a description of each file.



Working with S3 Datasets
========================

**m2g** has the ability to work on datasets stored on `Amazon's Simple Storage Service <https://aws.amazon.com/s3/>`_, assuming they are in BIDS format. Doing so requires you to set your AWS credentials and read the related s3 bucket documentation. You can find a guide `here <https://github.com/neurodata/m2g/blob/deploy/tutorials/Batch.ipynb>`_.


Example Datasets
----------------

Derivatives have been produced on a variety of datasets, all of which are made available on `our website <http://m2g.io>`_. Each of these datsets is available for access and download from their respective sources. Alternatively, example datasets on the `BIDS website <http://bids.neuroimaging.io>`_ which contain diffusion data can be used and have been tested; `ds114`, for example.


Command-Line Arguments
======================

Below is the help output generated by running **m2g** with the ``-h`` command. All parameters are explained in this output. ::

    $ docker run -ti neurodata/m2g -h

    usage: m2g [-h]
            [--participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]]
            [--session_label SESSION_LABEL [SESSION_LABEL ...]]
            [--pipeline PIPELINE] [--acquisition ACQUISITION] [--tr TR]
            [--push_location PUSH_LOCATION]
            [--parcellation PARCELLATION [PARCELLATION ...]] [--skipeddy]
            [--skipreg] [--voxelsize VOXELSIZE] [--mod MOD]
            [--track_type TRACK_TYPE] [--diffusion_model DIFFUSION_MODEL]
            [--space SPACE] [--seeds SEEDS] [--skull SKULL] [--mem_gb MEM_GB]
            [--n_cpus N_CPUS]
            input_dir output_dir

    This is an end-to-end connectome estimation pipeline from fMRI and diffusion
    weighted MRI data.

    positional arguments:
    input_dir             The directory with the input dataset formatted
                            according to the BIDS standard. To use data from s3,
                            put the bucket and directory location as the input
                            directory: `s3://<bucket>/<dataset>` downloaded file
                            will be stored in ~/.m2g/input. If directory already
                            exists it will be deleted.
    output_dir            The local directory where the output files should be
                            stored.

    optional arguments:
    -h, --help            show this help message and exit
    --participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]
                            The label(s) of the participant(s) that should be
                            analyzed. The label corresponds to
                            sub-<participant_label> from the BIDS spec (so it does
                            not include "sub-"). If this parameter is not provided
                            all subjects should be analyzed. Multiple participants
                            can be specified with a space separated list.
    --session_label SESSION_LABEL [SESSION_LABEL ...]
                            The label(s) of the session that should be analyzed.
                            The label corresponds to ses-<participant_label> from
                            the BIDS spec (so it does not include "ses-"). If this
                            parameter is not provided all sessions should be
                            analyzed. Multiple sessions can be specified with a
                            space separated list.
    --pipeline PIPELINE   Pipline to use when analyzing the input data, either
                            func, dwi, or both. Default is dwi.
    --acquisition ACQUISITION
                            Acquisition method for functional data: altplus -
                            Alternating in the +z direction alt+z - Alternating in
                            the +z direction alt+z2 - Alternating, but beginning
                            at slice #1 altminus - Alternating in the -z direction
                            alt-z - Alternating in the -z direction alt-z2 -
                            Alternating, starting at slice #nz-2 instead of #nz-1
                            seqplus - Sequential in the plus direction seqminus -
                            Sequential in the minus direction, default is alt+z.
                            For more information:https://fcp-
                            indi.github.io/docs/user/func.html
    --tr TR               functional scan TR (seconds), default is 2.0
    --push_location PUSH_LOCATION
                            Name of folder on s3 to push output data to, if the
                            folder does not exist, it will be created.Format the
                            location as `s3://<bucket>/<path>`
    --parcellation PARCELLATION [PARCELLATION ...]
                            The parcellation(s) being analyzed. Multiple
                            parcellations can be provided with a space separated
                            list. If not parcellations are defined, will use all
                            parcellations from neuroparc.
    --skipeddy            Whether to skip eddy correction if it has already been
                            run and the files can be found in output_dir.
    --skipreg             Shether to skip registration of the parcellations if
                            it has already been run and the files can be fround in
                            output_dir
    --voxelsize VOXELSIZE
                            Voxel size : 2mm, 1mm. Voxel size of both parcellation
                            and reference structural image to use for template
                            registrations.
    --mod MOD             Deterministic (det) or probabilistic (prob) tracking
                            method for the dwi tractography. Default is det.
    --track_type TRACK_TYPE
                            Tracking approach: local, particle. Default is local.
    --diffusion_model DIFFUSION_MODEL
                            Diffusion model: csd or csa. Default is csa.
    --space SPACE         Space for tractography: native, native_dsn. Default is
                            native.
    --seeds SEEDS         Seeding density for tractography in the m2g-d
                            pipeline. Default is 20.
    --skull SKULL         Special actions to take when skullstripping t1w image
                            based on default skullstrip ('none') failure: Excess
                            tissue below brain: below Chunks of cerebelum missing:
                            cerebelum Frontal clipping near eyes: eye Excess
                            clipping in general: general,
    --mem_gb MEM_GB       Memory, in GB, to allocate to functional pipeline
    --n_cpus N_CPUS       Number of cpus to allocate to either the functional
                            pipeline or the diffusion connectome generation