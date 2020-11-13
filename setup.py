#!/usr/bin/env python
"""
setup.py
~~~~~~~~

on package install:
- generates metadata
- installs json files for use in m2g_cloud
- installs `m2g` script keywords to the command line
- ensures python version
- installs m2g dependencies

Use `pip install .` to install the package.
Use `pip install -e .` to install the package in developer mode.
See our README for more details on package installation : https://github.com/neurodata/m2g/blob/staging/README.md
"""

from setuptools import setup, find_packages
from m2g import __version__

# initial setup
kwargs = {}

# add metadata
kwargs.update(
    dict(
        name="m2g",
        version=__version__,
        description="Neuro Data MRI to Graphs Pipeline",
        author="Derek Pisner, Alex Loftus, Greg Kiar, Eric Bridgeford, and Will Gray Roncal",
        author_email="dpisner@utexas.edu, aloftus2@jhu.edu, gkiar@jhu.edu, wgr@jhu.edu, ebridge2@jhu.edu",
        url="https://github.com/neurodata/m2g",
        download_url="https://github.com/neurodata/m2g/tarball/" + __version__,
        keywords=["connectome", "mri", "pipeline"],
        classifiers=["Programming Language :: Python :: 3.6"],
    )
)

# add utility info
kwargs.update(
    dict(
        packages=find_packages(),
        package_data={"templates": ["*.json"]},
        include_package_data=False,  # only include the m2g_cloud template jsons
        entry_points={
            "console_scripts": [
                "m2g=m2g.scripts.m2g_bids:main",
                "m2g_dwi_pipeline=m2g.scripts.m2g_dwi_pipeline:main",
                "m2g_cloud=m2g.scripts.m2g_cloud:main",
                "m2g_bids=m2g.scripts.m2g_bids:main",  # for backwards compatibility
            ]
        },
        python_requires=">=3.6",
    )
)

# add requirements
kwargs.update(
    dict(
        install_requires=[
            "nibabel",
            "numpy",
            "dipy>=1.0.0",
            "scipy",
            "boto3",
            "matplotlib",
            "nilearn",
            "fury~=0.6.0",
            "pybids>=0.9.0",
            "networkx>=2.4",
            "configparser>=3.7.4",
            "pytest",
        ]
    )
)

# run setup
setup(**kwargs)
