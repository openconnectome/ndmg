#!/usr/bin/env python

"""
m2g.preproc
~~~~~~~~~~~~

Contains functionality for normalizing b-vectors.
TODO : depracate or change name. Add other preprocessing functions created from m2g_dwi_pipeline.
"""

# package imports
import numpy as np
import subprocess

# m2g imports
from m2g.utils import gen_utils
from m2g.utils.gen_utils import print_arguments


@print_arguments(inputs=[0], outputs=[1])
def eddy_correct(dwi, corrected_dwi, idx):
    """Performs eddy-correction (or self-alignment) of a stack of 3D images

    Parameters
    ----------
    dwi : str
        Path for the DTI image to be eddy-corrected
    corrected_dwi : str
        Path for the corrected and aligned DTI volume in a nifti file
    idx : str
        Index of the first B0 volume in the stack
    """

    cmd = f". /venv/bin/activate && eddy_correct {dwi} {corrected_dwi} {str(idx)} && deactivate"
    gen_utils.run(cmd)


def rescale_bvec(bvec, bvec_new):
    """Normalizes b-vectors to be of unit length for the non-zero b-values. If the b-value is 0, the vector is untouched

    Parameters
    ----------
    bvec : str
        Path to the original b-vectors file (bvec)
    bvec_new : str
        Path to the new (normalized) b-vectors file. Must have extension '.bvec'
    """

    bv1 = np.array(np.loadtxt(bvec))
    # Enforce proper dimensions
    bv1 = bv1.T if bv1.shape[0] == 3 else bv1

    # Normalize values not close to norm 1
    bv2 = [
        b / np.linalg.norm(b) if not np.isclose(np.linalg.norm(b), 0) else b
        for b in bv1
    ]

    try:
        assert "bvec" in bvec_new
        np.savetxt(bvec_new, bv2)

    except AssertionError:
        print(
            "Error: your new b-vector file must have extension .bvec to"
            + " be compatible with the the pipeline."
        )
    else:
        pass
