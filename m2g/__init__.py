"""
m2g
~~~~

an end-to-end connectome estimation pipeline
"""

# naming convention for __version__ : major.minor.bugs
__version__ = "1.0.0"


# to call `m2g.graph`, etc
__all__ = ["graph", "preproc", "register", "track"]  # modules
__all__.extend(["functional", "scripts", "stats", "utils"])  # subpackages

from . import *
