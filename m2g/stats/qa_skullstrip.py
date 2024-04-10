#!/usr/bin/env python

"""
m2g.stats.qa_skullstrip
~~~~~~~~~~~~~~~~~~~~~~
The top level m2g quality assurance for skull strip module.
In this module, m2g:
1. Takes an original t1w nifti file and the skull-stripped nifti file as inputs
2. Shows the skull-stripped brain (green) overlaid on the original t1w (magenta)
3. Saves the image into output directory
"""

import warnings

warnings.simplefilter("ignore")

import matplotlib as mpl
import nibabel as nb
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from scipy import ndimage

mpl.use("Agg")  # very important above pyplot import
import matplotlib.pyplot as plt
from nilearn.plotting.edge_detect import _edge_map as edge_map

from m2g.utils.gen_utils import get_braindata, get_filename
from m2g.utils.qa_utils import get_min_max, opaque_colorscale, pad_im


def gen_overlay_pngs(
    brain, original, outdir, loc=0, mean=False, minthr=2, maxthr=95, edge=False
):
    """Generate a QA image for skullstrip.
    will call the function plot_overlays_skullstrip

    Parameters
    ----------
    brain: nifti file
        Path to the skull-stripped nifti brain
    original: nifti file
        Path to the original t1w brain, with the skull included
    outdir: str
        Path to the directory where QA will be saved
    loc: int
        which dimension of the 4d brain data to use
    mean: bool
        whether to calculate the mean of the 4d brain data
        If False, the loc=0 dimension of the data (mri_data[:, :, :, loc]) is used
    minthr: int
        lower percentile threshold
    maxthr: int
        upper percentile threshold
    edge: bool
        whether to use normalized luminance data
        If None, the respective min and max of the color array is used.
    """
    original_name = get_filename(original)
    brain_data = nb.load(brain).get_data()
    if brain_data.ndim == 4:  # 4d data, so we need to reduce a dimension
        if mean:
            brain_data = brain_data.mean(axis=3)
        else:
            brain_data = brain_data[:, :, :, loc]

    fig = plot_overlays_skullstrip(brain_data, original)

    # name and save the file
    fig.savefig(f"{outdir}/qa_skullstrip__{original_name}.png", format="png")


def plot_overlays_skullstrip(
    brain, original, cmaps=None, minthr=2, maxthr=95, edge=False
):
    """Shows the skull-stripped brain (green) overlaid on the original t1w (magenta)

    Parameter
    ---------
    brain: str, nifti image, numpy.ndarray
        an object to open the data for a skull-stripped brain. Can be a string (path to a brain file),
        nibabel.nifti1.nifti1image, or a numpy.ndarray.
    original: str, nifti image, numpy.ndarray
        an object to open the data for t1w brain, with the skull included. Can be a string (path to a brain file),
        nibabel.nifti1.nifti1image, or a numpy.ndarray.
    cmaps: matplotlib colormap objects
        colormap objects based on lookup tables using linear segments.
    minthr: int
        lower percentile threshold
    maxthr: int
        upper percentile threshold
    edge: bool
        whether to use normalized luminance data
        If None, the respective min and max of the color array is used.

    Returns
    ---------
    foverlay: matplotlib.figure.Figure

    """

    plt.rcParams.update({"axes.labelsize": "x-large", "axes.titlesize": "x-large"})
    foverlay = plt.figure()

    original = get_braindata(original)
    brain_shape = get_braindata(brain).shape
    brain = get_braindata(brain)
    if original.shape != brain.shape:
        raise ValueError("Two files are not the same shape.")
    brain = pad_im(brain, max(brain_shape[0:3]), pad_val=0, rgb=False)
    original = pad_im(original, max(brain_shape[0:3]), pad_val=0, rgb=False)

    if cmaps is None:
        cmap1 = LinearSegmentedColormap.from_list("mycmap1", ["white", "magenta"])
        cmap2 = LinearSegmentedColormap.from_list("mycmap2", ["white", "green"])
        cmaps = [cmap1, cmap2]

    x, y, z = get_true_volume(brain)
    coords = (x, y, z)

    labs = [
        "Sagittal Slice",
        "Coronal Slice",
        "Axial Slice",
    ]
    var = ["X", "Y", "Z"]
    # create subplot for first slice
    # and customize all labels
    idx = 0
    if edge:
        min_val = 0
        max_val = 1
    else:
        min_val, max_val = get_min_max(brain, minthr, maxthr)

    for i, coord in enumerate(coords):
        for pos in coord:
            idx += 1
            ax = foverlay.add_subplot(3, 3, idx)
            ax.set_title(var[i] + " = " + str(pos))
            if i == 0:
                image = ndimage.rotate(brain[pos, :, :], 90)
                atl = ndimage.rotate(original[pos, :, :], 90)
            elif i == 1:
                image = ndimage.rotate(brain[:, pos, :], 90)
                atl = ndimage.rotate(original[:, pos, :], 90)
            else:
                image = ndimage.rotate(brain[:, :, pos], 0)
                atl = ndimage.rotate(original[:, :, pos], 0)

            if idx % 3 == 1:
                ax.set_ylabel(labs[i])
                ax.yaxis.set_ticks([0, image.shape[0] / 2, image.shape[0] - 1])
                ax.xaxis.set_ticks([0, image.shape[1] / 2, image.shape[1] - 1])
            if edge:
                image = edge_map(image).data
                image[image > 0] = max_val
                image[image == 0] = min_val
            # Set the axis invisible
            plt.xticks([])
            plt.yticks([])

            # Set the frame invisible
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["bottom"].set_visible(False)
            ax.spines["left"].set_visible(False)
            ax.imshow(atl, interpolation="none", cmap=cmaps[0], alpha=0.9)
            ax.imshow(
                opaque_colorscale(
                    cmaps[1], image, alpha=0.9, vmin=min_val, vmax=max_val
                )
            )
            if idx == 3:
                plt.plot(0, 0, "-", c="magenta", label="skull")
                plt.plot(0, 0, "-", c="green", label="brain")
                # box = ax.get_position()
                # ax.set_position([box.x0, box.y0, box.width, box.height*0.8])
                plt.legend(
                    loc="best", fontsize=15, frameon=False, bbox_to_anchor=(1.5, 1.5)
                )

    # Set title for the whole picture
    a, b, c = brain_shape
    title = "Skullstrip QA. Scan Volume : " + str(a) + "*" + str(b) + "*" + str(c)
    foverlay.suptitle(title, fontsize=24)
    foverlay.set_size_inches(12.5, 10.5, forward=True)
    return foverlay


def get_true_volume(brain_volume):
    """returns percentile dimensions to slice actual brain volume for qa_skullstrip plotting

    Parameter
    ---------
    brain_volume: numpy array
        3-d brain volume
    """
    img_arr = brain_volume.astype(int)
    threshold = int(1)
    img_arr[img_arr <= threshold] = 0
    img_arr[img_arr > threshold] = 1
    true_volume = np.where(img_arr == 1)
    x = get_range(true_volume, 0)
    y = get_range(true_volume, 1)
    z = get_range(true_volume, 2)
    return x, y, z


def get_range(array, i):
    """get percentiles of array

    Parameter
    ---------
    array: numpy array
        3-d brain volume
    i: int
        dimension of array to get percentiles
    """
    min_num = min(array[i])
    max_num = max(array[i])
    arrange = np.arange(min_num, max_num)
    quarter = np.percentile(arrange, [25, 50, 75]).astype(int)
    return quarter
