# Copyright (C) 2022-2023  C-PAC Developers

# This file is part of C-PAC.

# C-PAC is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.

# C-PAC is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public
# License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with C-PAC. If not, see <https://www.gnu.org/licenses/>.
FROM ghcr.io/fcp-indi/c-pac/stage-base:lite-v1.8.6.dev1
LABEL org.opencontainers.image.description "Full C-PAC image without FreeSurfer"
LABEL org.opencontainers.image.source https://github.com/FCP-INDI/C-PAC
USER root

# install C-PAC
RUN git clone --branch v1.8.6 --depth 1 --single-branch https://github.com/FCP-INDI/C-PAC.git /code/ && \
    mkdir /docker_data && \
    cp -r /code/dev/docker_data/* /docker_data && \
    mkdir /cpac_resources && \
    cp /code/dev/circleci_data/pipe-test_ci.yml /cpac_resources/pipe-test_ci.yml

# install cpac templates
COPY --from=ghcr.io/fcp-indi/c-pac_templates:latest /cpac_templates /cpac_templates
RUN pip cache purge && pip install -e /code
# set up runscript
RUN mkdir /code/docker_data/ && \
    cp -r /code/dev/docker_data/* /code/
RUN rm -Rf /code/docker_data/checksum && \
    chmod +x /code/run.py && \
    rm -Rf /code/run-with-freesurfer.sh
# ENTRYPOINT ["/code/run.py"]


#--------M2G SETUP-----------------------------------------------------------#
# grab atlases from neuroparc
RUN mkdir /m2g_atlases

RUN git clone https://github.com/neurodata/neuroparc && \
    mv /neuroparc/atlases /m2g_atlases && \
    rm -rf /neuroparc
RUN chmod -R 777 /m2g_atlases

# Grab m2g from deploy.
RUN git clone --branch docker https://github.com/neurodata/m2g /m2g && \
    pip install -e /m2g
# RUN chmod -R 777 /usr/local/bin/m2g_bids

# link libraries & clean up
RUN rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cache/* \
    && find / -type f -print0 | sort -t/ -k2 | xargs -0 rdfind -makehardlinks true \
    && rm -rf results.txt \
    && apt-get remove rdfind -y \
    && apt-get clean \
    && apt-get autoremove -y \
    && ldconfig \
    && chmod 777 / \
    && chmod 777 $(ls / | grep -v sys | grep -v proc)
ENV PYTHONUSERBASE=/home/c-pac_user/.local
ENV PATH=$PATH:/home/c-pac_user/.local/bin \
    PYTHONPATH=$PYTHONPATH:$PYTHONUSERBASE/lib/python3.10/site-packages

# set user
WORKDIR /
ENTRYPOINT ["m2g"]

