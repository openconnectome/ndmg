"""
m2g.scripts
~~~~~~~~~~~~

Contains top-level, self-contained scripts.

m2g_bids : top-level pipeline entrypoint
m2g_dwi_pipeline : the pipeline itself
m2g_cloud : for performing batch processing on AWS
"""

from . import m2g_bids, m2g_cloud, m2g_dwi_pipeline
