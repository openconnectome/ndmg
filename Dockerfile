FROM neurodata/fsl_1604:0.0.1
LABEL author="Ross Lawrence, Alex Loftus"
LABEL maintainer="rlawre18@jhu.edu"

#--------Environment Variables-----------------------------------------------#
ENV M2G_URL https://github.com/neurodata/m2g.git
ENV M2G_ATLASES https://github.com/neurodata/neuroparc.git
ENV AFNI_URL https://files.osf.io/v1/resources/fvuh8/providers/osfstorage/5a0dd9a7b83f69027512a12b
ENV LIBXP_URL http://mirrors.kernel.org/debian/pool/main/libx/libxp/libxp6_1.0.2-2_amd64.deb
ENV LIBPNG_URL http://mirrors.kernel.org/debian/pool/main/libp/libpng/libpng12-0_1.2.49-1%2Bdeb7u2_amd64.deb

#--------Initial Configuration-----------------------------------------------#
# download/install basic dependencies, and set up python
RUN apt-get update && \
    apt-get install -y zip unzip vim git curl libglu1 python-setuptools zlib1g-dev \
    git libpng-dev libfreetype6-dev pkg-config g++ vim r-base-core libgsl0-dev build-essential \
    openssl

# upgrade python to solve TLS issues
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    apt-get update && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.6 python3.6-dev && \
    curl https://bootstrap.pypa.io/get-pip.py | python3.6

RUN apt-get install -y python2.7 python-pip


RUN pip3.6 install --upgrade pip

# Get neurodebian config
RUN curl -sSL http://neuro.debian.net/lists/stretch.us-tn.full >> /etc/apt/sources.list.d/neurodebian.sources.list && \
    apt-key add /root/.neurodebian.gpg && \
    (apt-key adv --refresh-keys --keyserver hkp://ha.pool.sks-keyservers.net 0xA5D32F012649A5A9 || true) && \
    apt-get update -qq
RUN apt-get -f install



# Configure git-lfs
RUN apt-get install -y apt-transport-https debian-archive-keyring
RUN curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash && \
    apt-get update && \
    apt-get install -y git-lfs

# #---------AFNI INSTALL--------------------------------------------------------#
# # setup of AFNI, which provides robust modifications of many of neuroimaging
# # algorithms
RUN apt-get update -qq && apt-get install -yq --no-install-recommends ed gsl-bin libglu1-mesa-dev libglib2.0-0 libglw1-mesa fsl-atlases \
    libgomp1 libjpeg62 libxm4 netpbm tcsh xfonts-base xvfb && \
    libs_path=/usr/lib/x86_64-linux-gnu && \
    if [ -f $libs_path/libgsl.so.19 ]; then \
    ln $libs_path/libgsl.so.19 $libs_path/libgsl.so.0; \
    fi

RUN mkdir -p /opt/afni && \
    curl -o afni.tar.gz -sSLO "$AFNI_URL" && \
    tar zxv -C /opt/afni --strip-components=1 -f afni.tar.gz && \
    rm -rf afni.tar.gz
ENV PATH=/opt/afni:$PATH

## --------CPAC INSTALLS-----------------------------------------------------#
RUN apt-get install -y graphviz graphviz-dev


# install FSL
RUN apt-get install -y --no-install-recommends \
      fsl-core \
      fsl-atlases \
      fsl-mni152-templates


# Setup FSL environment
ENV FSLDIR=/usr/share/fsl/5.0 \
    FSLOUTPUTTYPE=NIFTI_GZ \
    FSLMULTIFILEQUIT=TRUE \
    POSSUMDIR=/usr/share/fsl/5.0 \
    LD_LIBRARY_PATH=/usr/lib/fsl/5.0:$LD_LIBRARY_PATH \
    FSLTCLSH=/usr/bin/tclsh \
    FSLWISH=/usr/bin/wish \
    PATH=/usr/lib/fsl/5.0:$PATH

# install CPAC resources into FSL
RUN curl -sL http://fcon_1000.projects.nitrc.org/indi/cpac_resources.tar.gz -o /tmp/cpac_resources.tar.gz && \
    tar xfz /tmp/cpac_resources.tar.gz -C /tmp && \
    cp -n /tmp/cpac_image_resources/MNI_3mm/* $FSLDIR/data/standard && \
    cp -n /tmp/cpac_image_resources/MNI_4mm/* $FSLDIR/data/standard && \
    cp -n /tmp/cpac_image_resources/symmetric/* $FSLDIR/data/standard && \
    cp -n /tmp/cpac_image_resources/HarvardOxford-lateral-ventricles-thr25-2mm.nii.gz $FSLDIR/data/atlases/HarvardOxford && \
    cp -nr /tmp/cpac_image_resources/tissuepriors/2mm $FSLDIR/data/standard/tissuepriors && \
    cp -nr /tmp/cpac_image_resources/tissuepriors/3mm $FSLDIR/data/standard/tissueprior


RUN apt-get update

# Install Ubuntu dependencies and utilities
RUN apt-get install -y \
      build-essential \
      cmake \
      git \
      graphviz \
      graphviz-dev \
      gsl-bin \
      libcanberra-gtk-module \
      libexpat1-dev \
      libgiftiio-dev \
      libglib2.0-dev \
      libglu1-mesa \
      libglu1-mesa-dev \
      libjpeg-progs \
      libgl1-mesa-dri \
      libglw1-mesa \
      libxml2 \
      libxml2-dev \
      libxext-dev \
      libxft2 \
      libxft-dev \
      libxi-dev \
      libxmu-headers \
      libxmu-dev \
      libxpm-dev \
      libxslt1-dev \
      m4 \
      make \
      mesa-common-dev \
      mesa-utils \
      netpbm \
      pkg-config \
      rsync \
      tcsh \
      unzip \
      vim \
      xvfb \
      xauth \
      zlib1g-dev \
      debhelper -t xenial-backports

RUN apt-get update

# Install 16.04 dependencies
RUN apt-get install -y \
      dh-autoreconf \
      libgsl-dev \
      libmotif-dev \
      libtool \
      libx11-dev \
      libxext-dev \
      x11proto-xext-dev \
      x11proto-print-dev \
      xutils-dev \
      environment-modules
#libinsighttoolkit4.10

# Install libpng12
RUN curl -sLo /tmp/libpng12.deb http://mirrors.kernel.org/ubuntu/pool/main/libp/libpng/libpng12-0_1.2.54-1ubuntu1_amd64.deb && \
    dpkg -i /tmp/libpng12.deb && \
    rm /tmp/libpng12.deb

# Compiles libxp- this is necessary for some newer versions of Ubuntu
# where the is no Debian package available.
RUN git clone git://anongit.freedesktop.org/xorg/lib/libXp /tmp/libXp && \
    cd /tmp/libXp && \
    ./autogen.sh && \
    ./configure && \
    make && \
    make install && \
    cd - && \
    rm -rf /tmp/libXp

# Installing and setting up c3d
RUN mkdir -p /opt/c3d && \
    curl -sSL "http://downloads.sourceforge.net/project/c3d/c3d/1.0.0/c3d-1.0.0-Linux-x86_64.tar.gz" \
    | tar -xzC /opt/c3d --strip-components 1
ENV C3DPATH /opt/c3d/
ENV PATH $C3DPATH/bin:$PATH


# download OASIS templates for niworkflows-ants skullstripping
RUN mkdir /ants_template && \
    curl -sL https://s3-eu-west-1.amazonaws.com/pfigshare-u-files/3133832/Oasis.zip -o /tmp/Oasis.zip && \
    unzip /tmp/Oasis.zip -d /tmp &&\
    mv /tmp/MICCAI2012-Multi-Atlas-Challenge-Data /ants_template/oasis && \
    rm -rf /tmp/Oasis.zip /tmp/MICCAI2012-Multi-Atlas-Challenge-Data

RUN apt-get -f --yes --force-yes install

RUN apt-get --yes --force-yes install insighttoolkit4-python
RUN apt-get update && apt-get -y upgrade insighttoolkit4-python

# install ANTs
#ENV PATH=/usr/lib/ants:$PATH
#RUN apt-get install -y ants

#--------M2G SETUP-----------------------------------------------------------#
# setup of python dependencies for m2g itself, as well as file dependencies
RUN \
    pip3.6 install --no-cache-dir numpy nibabel scipy python-dateutil pandas boto3 awscli virtualenv
RUN \
    pip3.6 install --no-cache-dir matplotlib nilearn sklearn pandas cython vtk pyvtk fury
RUN \
    pip3.6 install --no-cache-dir yamlordereddictloader awscli==1.15.40 requests ipython duecredit graspy scikit-image networkx dipy pybids

RUN \
    pip3.6 install --no-cache-dir plotly==1.12.9 setuptools>=40.0 configparser>=3.7.4

# install ICA-AROMA
RUN mkdir -p /opt/ICA-AROMA
RUN curl -sL https://github.com/rhr-pruim/ICA-AROMA/archive/v0.4.3-beta.tar.gz | tar -xzC /opt/ICA-AROMA --strip-components 1
RUN chmod +x /opt/ICA-AROMA/ICA_AROMA.py
ENV PATH=/opt/ICA-AROMA:$PATH

# install miniconda
RUN curl -sO https://repo.anaconda.com/miniconda/Miniconda3-py37_4.8.2-Linux-x86_64.sh && \
    bash Miniconda3-py37_4.8.2-Linux-x86_64.sh -b -p /usr/local/miniconda && \
    rm Miniconda3-py37_4.8.2-Linux-x86_64.sh

# update path to include conda
ENV PATH=/usr/local/miniconda/bin:$PATH

# install conda dependencies
RUN conda update conda -y && \
    conda install -y  \
        blas \
        matplotlib==3.1.3 \
        networkx==2.4 \
        nose==1.3.7 \
        numpy==1.16.4 \
        pandas==0.23.4 \
        scipy==1.4.1 \
        traits==4.6.0 \
        wxpython
#pip

# install torch
RUN pip3.6 install torch==1.2.0 torchvision==0.4.0 -f https://download.pytorch.org/whl/torch_stable.html


WORKDIR /

RUN mkdir /input && \
    chmod -R 777 /input

RUN mkdir /output && \
    chmod -R 777 /output


# install PyPEER
RUN pip install git+https://github.com/ChildMindInstitute/PyPEER.git


# grab atlases from neuroparc
RUN mkdir /m2g_atlases

RUN \

    git lfs clone https://github.com/neurodata/neuroparc && \

    mv /neuroparc/atlases /m2g_atlases && \
    rm -rf /neuroparc
RUN chmod -R 777 /m2g_atlases

# Grab m2g from deploy.
RUN git clone -b cpac-py3 $M2G_URL /m2g && \
    cd /m2g && \
    pip3.6 install .
RUN chmod -R 777 /usr/local/bin/m2g_bids

ENV MPLCONFIGDIR /tmp/matplotlib
ENV PYTHONWARNINGS ignore

# copy over the entrypoint script
#ADD ./.vimrc .vimrc
RUN ldconfig

# and add it as an entrypoint
ENTRYPOINT ["m2g"]


# Clear apt-get caches (try adding sudo)
RUN apt-get clean

# Installing and setting up c3d
RUN mkdir -p /opt/c3d && \
    curl -sSL "http://downloads.sourceforge.net/project/c3d/c3d/1.0.0/c3d-1.0.0-Linux-x86_64.tar.gz" \
    | tar -xzC /opt/c3d --strip-components 1
ENV C3DPATH /opt/c3d/
ENV PATH $C3DPATH/bin:$PATH

# Set up the functional pipeline
RUN cd / && \
    git clone --branch v1.6.2 --single-branch https://github.com/FCP-INDI/C-PAC.git && \
    mkdir /code && \
    mv /C-PAC/dev/docker_data/* /code/ && \
    mv /C-PAC/* /code/ && \
    rm -R /C-PAC && \
    chmod +x /code/run.py && \
    cd /

RUN ls /code/

# install cpac templates
RUN mv /code/cpac_templates.tar.gz / && \
    tar xvzf /cpac_templates.tar.gz

# install AFNI [PUT AFTER CPAC IS CALLED]
RUN mv /code/required_afni_pkgs.txt /opt/required_afni_pkgs.txt
RUN if [ -f /usr/lib/x86_64-linux-gnu/mesa/libGL.so.1.2.0]; then \
        ln -svf /usr/lib/x86_64-linux-gnu/mesa/libGL.so.1.2.0 /usr/lib/x86_64-linux-gnu/libGL.so.1; \
    fi && \
    libs_path=/usr/lib/x86_64-linux-gnu && \
    if [ -f $libs_path/libgsl.so.23 ]; then \
        ln -svf $libs_path/libgsl.so.23 $libs_path/libgsl.so.19 && \
        ln -svf $libs_path/libgsl.so.23 $libs_path/libgsl.so.0; \
    elif [ -f $libs_path/libgsl.so.23.0.0 ]; then \
        ln -svf $libs_path/libgsl.so.23.0.0 $libs_path/libgsl.so.0; \
    elif [ -f $libs_path/libgsl.so ]; then \
        ln -svf $libs_path/libgsl.so $libs_path/libgsl.so.0; \
    fi && \
    LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH && \
    export LD_LIBRARY_PATH && \
    curl -O https://afni.nimh.nih.gov/pub/dist/bin/linux_ubuntu_16_64/@update.afni.binaries && \
    tcsh @update.afni.binaries -package linux_openmp_64 -bindir /opt/afni -prog_list $(cat /opt/required_afni_pkgs.txt) && \
    ldconfig


# install python dependencies
RUN cp /code/requirements.txt /opt/requirements.txt
RUN pip3.6 install --upgrade setuptools
RUN pip3.6 install --upgrade pip
RUN pip3.6 install -r /opt/requirements.txt
RUN pip3.6 install xvfbwrapper

RUN mkdir /cpac_resources
RUN mv /code/default_pipeline.yml /cpac_resources/default_pipeline.yml
RUN mv /code/dev/circleci_data/pipe-test_ci.yml /cpac_resources/pipe-test_ci.yml

#COPY . /code
RUN pip3.6 install -e /code

#COPY dev/docker_data /code/docker_data
#RUN mv /code/docker_data/* /code && rm -Rf /code/docker_data && chmod +x /code/run.py


# Link libraries for Singularity images
#RUN ldconfig


#https://stackoverflow.com/questions/18649512/unicodedecodeerror-ascii-codec-cant-decode-byte-0xe2-in-position-13-ordinal
RUN export LC_ALL=C.UTF-8 && \
    apt-get clean && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN virtualenv -p /usr/bin/python2.7 venv && \
    . venv/bin/activate
