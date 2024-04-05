#!/usr/bin/env python

"""
m2g.stats.qa_tensor
~~~~~~~~~~~~~~~~~~~~

Contains functions to generate intermediate qa figures for the directional field directions
for models used during the tractrography step.

"""

import warnings

warnings.simplefilter("ignore")
from argparse import ArgumentParser
from scipy import ndimage
import numpy as np
import nibabel as nb
import matplotlib
import itertools

from dipy.viz import window, actor
from fury.actor import orient2rgb
from m2g.utils import qa_utils

matplotlib.use("Agg")  # very important above pyplot import
import matplotlib.pyplot as plt


def generate_3_d_directions(peak_dirs, peak_values):
    """
    Generates 3-d data required for plotting directions for the entire brain volume

    Parameters
    -----------
    peak_dirs: np array
        peak_dirs from tractography model (x,y,z directional vectors)
    peak_values: np array
        peak_values from tractography model (magnitude)

    Returns
    -----------
    centers: np array
        cartesian coordinates
    directions: np array
        vector directions (x,y,z) in flattened format
    directions_colors: np array
        vector directions encoded as RGB colors in flattened format
    heights: np array
        vector magnitudes in flattened format
    """

    # initialize
    centers = []
    directions = []
    heights = []
    directions_colors = []

    xs = range(peak_dirs.shape[0])
    ys = range(peak_dirs.shape[1])
    zs = range(peak_dirs.shape[2])
    for x, y, z in itertools.product(xs, ys, zs):
        centers.append([x, y, z])

        # relies on the fact that peaks_from_models generates peak_dirs and peak_values in descending order
        directions.append(peak_dirs[x, y, z, 0, :])
        heights.append(peak_values[x, y, z, 0])

    # convert to np arrays
    centers = np.asarray(centers)
    directions = np.asarray(directions)
    heights = np.asarray(heights)

    # get rgb based on directional components
    directions_colors = orient2rgb(directions)

    return centers, directions, directions_colors, heights


def plot_directions(peak_dirs, peak_values, x_angle, y_angle, size=(300, 300)):
    """
    Opens a 3-d fury window of the maximum peaks visualized

    To show a slice, provide a sliced volume of the peak_dirs and peak_values and adjust the x_angle and y_angle
    See Tractography Directional Field QA Tutorial for examples

    Parameters
    -----------
    peak_dirs: np array
        peak directional vector (x,y,z)
    peak_values: np array
        peak values/magnitude
    x_angle: int
        angle to rotate image along x axis
    y_angle: int
        angle to rotate image along y axis
    size: tuple
        size of fury window
    """
    centers, directions, directions_colors, heights = generate_3_d_directions(
        peak_dirs, peak_values
    )

    scene = window.Scene()
    arrow_actor = actor.arrow(centers, directions, directions_colors, heights)

    scene.add(arrow_actor)
    scene.roll(x_angle)
    scene.pitch(y_angle)

    window.show(scene, size=size)


def create_qa_figure(peak_dirs, peak_values, output_dir, model):
    """
    Creates a 9x9 figure of the 3-d volume and saves it

    Parameters
    -----------
    peak_dirs: np array
        peak directional vector (x,y,z)
    peak_values: np array
        peak values/magnitude
    output_dir: str
        location to save qa figure
    model: str
        model type used to build tractogram (CSA, CSD). only used to create figure title
    """
    # set shape of image
    im_shape = peak_dirs.shape[:3]
    im_shape_rgb = (*im_shape, 3)

    max_dim = max(im_shape)

    # title
    title = f"QA for Tractography {model.upper()} Model Peak Directions. Scan Volume: {im_shape}"

    # generate 3-d directional data
    centers, directions, directions_colors, heights = generate_3_d_directions(
        peak_dirs, peak_values
    )

    # reshape back into a 3-d volume with voxel encoded RGB values corresponding to directional vectors
    im = directions_colors.reshape(im_shape_rgb)

    slices = (0.35, 0.51, 0.65)

    x = [
        int(im_shape[0] * slices[0]),
        int(im_shape[0] * slices[1]),
        int(im_shape[0] * slices[2]),
    ]
    y = [
        int(im_shape[1] * slices[0]),
        int(im_shape[1] * slices[1]),
        int(im_shape[1] * slices[2]),
    ]
    z = [
        int(im_shape[2] * slices[0]),
        int(im_shape[2] * slices[1]),
        int(im_shape[2] * slices[2]),
    ]

    coords = (x, y, z)
    labs = ["Sagittal Slice", "Coronal Slice", "Axial Slice"]
    var = ["X", "Y", "Z"]

    idx = 0
    for i, coord in enumerate(coords):
        for pos in coord:
            idx += 1
            ax = plt.subplot(3, 3, idx)
            ax.set_title(var[i] + " = " + str(pos))
            if i == 0:
                image = ndimage.rotate(im[pos, :, :, :], 90)
            elif i == 1:
                image = ndimage.rotate(im[:, pos, :, :], 90)
            else:
                image = im[:, :, pos, :]
            if idx % 3 == 1:
                ax.set_ylabel(labs[i])
            # remove axis
            plt.xticks([])
            plt.yticks([])
            image = (image * 255).astype(np.uint8)
            # convert background
            image = np.where(image <= 0.01, 255, image)
            # pad image size
            image = qa_utils.pad_im(image, max_dim, pad_val=255, rgb=True)
            plt.imshow(image)

    fig = plt.gcf()
    fig.suptitle(title)
    fig.set_size_inches(12.5, 10.5, forward=True)
    fig.savefig(output_dir)
