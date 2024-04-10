import numpy as np
import os
import csv
import networkx as nx
from matplotlib import pyplot as plt
import m2g.utils.cloud_utils as cloud_utils
from m2g.utils.gen_utils import as_directory
from graspologic.utils import pass_to_ranks, import_edgelist
from argparse import ArgumentParser

import json
from plotly.graph_objs import *


def load_avg_ptr():

    localpath = "/discrim-data/diffusion"
    datasets = [
        "SWU4",
        "HNU1",
        "NKIENH",
        "XHCUMS",
        "BNU1",
        "BNU3",
        "IPCAS8",
        "NKI1",
        "NKI24",
        "MRN1",
    ]
    dsize = [382, 298, 192, 120, 114, 46, 40, 36, 36, 20]

    atlas = "Desikan_space-MNI152NLin6_res-2x2x2"
    # atlas = 'Hammersmith_space-MNI152NLin6_res-2x2x2/'
    # atlas = 'AAL_space-MNI152NLin6_res-2x2x2/'

    # localpath = '/discrim-data/functional'
    # datasets = ['SWU4','HNU1','NYU2','XHCUMS','UPSM1','BNU3','IPCAS7','SWU1','IPCAS1','BNU1']
    # dsize = [429,300,300,247,230,144,144,119,114,106]
    # atlas = '_mask_Desikan_space-MNI152NLin6_res-2x2x2_mask_file_..m2g_atlases..atlases..label..Human..Desikan_space-MNI152NLin6_res-2x2x2.nii.gz'
    # atlas='_mask_Hammersmith_space-MNI152NLin6_res-2x2x2_mask_file_..m2g_atlases..atlases..label..Human..Hammersmith_space-MNI152NLin6_res-2x2x2.nii.gz/'
    # atlas='_mask_AAL_space-MNI152NLin6_res-2x2x2_mask_file_..m2g_atlases..atlases..label..Human..AAL_space-MNI152NLin6_res-2x2x2.nii.gz/'

    # Calculate total size of scans
    tot = sum(dsize)

    for idx, dset in enumerate(datasets):
        # get list of all files belonging to atlas:
        connectomes = os.listdir(f"{localpath}/{dset}/{atlas}")

        if idx > 0:
            for name in connectomes:
                if "mean-ptr" in name:
                    mean_files.append(f"{localpath}/{dset}/{atlas}/{str(name)}")
                if "variance-ptr" in name:
                    var_files.append(f"{localpath}/{dset}/{atlas}/{str(name)}")

        else:  # itterate through list and calculate mean and variance of edgelist
            mean_files = [
                f"{localpath}/{dset}/{atlas}/{str(name)}"
                for name in connectomes
                if "mean-ptr" in name
            ]
            var_files = [
                f"{localpath}/{dset}/{atlas}/{str(name)}"
                for name in connectomes
                if "variance-ptr" in name
            ]

    # Create the weighted averages for mean and variance
    list_of_means, verts = import_edgelist(
        mean_files, delimiter=" ", return_vertices=True
    )
    if not isinstance(list_of_means, list):
        list_of_means = [list_of_means]

    mean_connectome = np.array(
        [array * (dsize[idx] / tot) for idx, array in enumerate(list_of_means)]
    )
    mean_connectome = np.atleast_3d(mean_connectome)
    mean_connectome = np.sum(mean_connectome, axis=0)

    return mean_connectome


def ipsi_calc(connectome, atlas, pipeline="dwi", verbose=False):
    if "DKT" in atlas:
        ipsi = []
        contra = []
        hom = []

        with open("/DKT_space-MNI152NLin6_res-1x1x1.json") as f:
            des_dat = json.load(f)

        r, c, _ = connectome.shape
        for j in range(r):
            for i in range(c):
                if (
                    des_dat["rois"][str(i)]["label"]
                    and des_dat["rois"][str(j)]["label"]
                ):
                    if i > j:
                        if (
                            des_dat["rois"][str(i)]["label"][0]
                            == des_dat["rois"][str(j)]["label"][0]
                        ):
                            ipsi.append(connectome[j][i])
                        elif i == j + 41:
                            hom.append(connectome[i][j])
                        elif (
                            des_dat["rois"][str(i)]["label"][0]
                            != des_dat["rois"][str(j)]["label"][0]
                        ):
                            contra.append(connectome[j][i])

        # r,c,_ = connectome.shape
        # for j in range(r):
        #    for i in range(c):
        #        if i>j:
        #            if j+35==i:
        #                hom.append(connectome[j][i])
        #            elif i<35 and j<35:
        #                ipsi.append(connectome[j][i])
        #            elif i>=35 and j>=35:
        #                ipsi.append(connectome[j][i])
        #            else:
        #                contra.append(connectome[j][i])

    if "Hammer" in atlas:
        ipsi = []
        contra = []
        hom = []

        r, c, _ = connectome.shape
        for j in range(r):
            for i in range(c):
                if i not in {43, 48} and j not in {43, 48}:
                    if i > j:
                        if (i == j + 1) and (j % 2 == 1):
                            hom.append(connectome[j][i])
                        elif i % 2 == j % 2:
                            ipsi.append(connectome[j][i])
                        else:
                            contra.append(connectome[j][i])

    if "AAL" in atlas:
        ipsi = []
        contra = []
        hom = []

        r, c, _ = connectome.shape
        for j in range(r):
            for i in range(c):
                if i > j:
                    if (i == j + 1) and (j % 2 == 1):
                        hom.append(connectome[j][i])
                    elif i % 2 == j % 2:
                        ipsi.append(connectome[j][i])
                    else:
                        contra.append(connectome[j][i])

    hom = np.array(hom)
    ipsi = np.array(ipsi)
    contra = np.array(contra)

    if pipeline == "dwi":
        tot = np.sum(ipsi) + np.sum(hom) + np.sum(contra)
        tot_ipsi = np.sum(ipsi)
        tot_hom = np.sum(hom)
        tot_contra = np.sum(contra)

        mean_ipsi = np.mean(ipsi)
        mean_hom = np.mean(hom)
        mean_contra = np.mean(contra)

        if verbose:
            print(f"Total = {tot}")
            print(f"Ipsilateral = {mean_ipsi} ({tot_ipsi/tot})")
            print(f"Homotopic = {mean_hom} ({tot_hom/tot})")
            print(f"Contralateral = {mean_contra} ({tot_contra/tot})")

        if max([mean_ipsi, mean_hom, mean_contra]) == mean_ipsi:
            ans = "i"
        elif max([mean_ipsi, mean_hom, mean_contra]) == mean_hom:
            ans = "h"
        else:
            ans = "c"

        return (
            ans,
            mean_ipsi,
            mean_hom,
            mean_contra,
            tot_ipsi / tot,
            tot_hom / tot,
            tot_contra / tot,
        )

    elif pipeline == "func":
        # Because the functional connectomes are correlation, there isn't any normalizing to be done
        tot_ipsi = np.mean(ipsi)
        tot_hom = np.mean(hom)
        tot_contra = np.mean(contra)

        if verbose:
            print(f"Ipsilateral = {tot_ipsi}")
            print(f"Homotopic = {tot_hom}")
            print(f"Contralateral = {tot_contra}")

        if max([tot_ipsi, tot_hom, tot_contra]) == tot_ipsi:
            ans = "i"
        elif max([tot_ipsi, tot_hom, tot_contra]) == tot_hom:
            ans = "h"
        else:
            ans = "c"

        return ans, tot_ipsi, tot_hom, tot_contra


def main():
    parser = ArgumentParser(
        description="This is an end-to-end connectome estimation pipeline from M3r Images."
    )
    parser.add_argument(
        "output_dir",
        help="""The local directory where the output
        files should be stored.""",
    )
    parser.add_argument(
        "pipeline",
        help="""Pipeline that created the data""",
    )
    parser.add_argument(
        "--input_dirs",
        action="store",
        help="""The directory with the input dataset
        formatted according to the BIDS standard.
        To use data from s3, just pass `s3://<bucket>/<dataset>` as the input directory.""",
        nargs="+",
        default=None,
    )
    parser.add_argument(
        "--ptr", action="store", help="whether to pass to ranks", default=False
    )
    parser.add_argument(
        "--atlases",
        action="store",
        help="which atlases to use",
        nargs="+",
        default=None,
    )
    result = parser.parse_args()
    input_dirs = result.input_dirs
    output_dir = result.output_dir
    pipe = result.pipeline
    PTR = result.ptr
    atlases = result.atlases

    for input_dir in input_dirs:
        title = input_dir.split("/")[3]
        atlases = result.atlases
        # Inputs needed:

        if "s3://" in input_dir:
            # grab files from s3
            creds = bool(cloud_utils.get_credentials())

            buck, remo = cloud_utils.parse_path(input_dir)
            home = os.path.expanduser("~")
            input_dir = as_directory(home + "/.m2g/input", remove=True)
            if not creds:
                raise AttributeError("""No AWS credentials found""")

            # Get S3 input data if needed
            if pipe == "func":
                if atlases is not None:
                    for atlas in atlases:
                        info = f"_mask_{atlas}"
                        cloud_utils.s3_get_data(
                            buck, remo, input_dir, info=info, pipe=pipe
                        )
                else:
                    info = "_mask_"
                    cloud_utils.s3_get_data(buck, remo, input_dir, info=info, pipe=pipe)
            elif pipe == "dwi":
                if atlases is not None:
                    for atlas in atlases:
                        info = f"{atlas}"
                        cloud_utils.s3_get_data(
                            buck, remo, input_dir, info=info, pipe=pipe
                        )
                else:
                    info = ""
                    cloud_utils.s3_get_data(buck, remo, input_dir, info=info, pipe=pipe)

        # DEF LOAD and AVERAGE NON-PTR CONNECTOMES
        if PTR:
            mean_connectome = load_avg_ptr()

        if pipe == "func":  # Because CPAC makes terrible output directory trees
            atlases = os.listdir(f"{input_dir}")

        # Write the dataset being analyzed
        # with open('results.csv', mode='a') as result_file:
        #    result_writer = csv.writer(result_file, delimiter=" ")
        #    result_writer.writerow([f"{title}"])

        for atlas in atlases:
            # ACTUAL IPSI-CALC OCCURING HERE
            connectomes = os.listdir(f"{input_dir}/{atlas}")

            results = []
            ipsi = []
            hom = []
            contra = []

            # just for percentage of edges calculation
            ipsi_t = []
            hom_t = []
            contra_t = []

            for cons in connectomes:
                node_weights, nodes = import_edgelist(
                    f"{input_dir}/{atlas}/{cons}", delimiter=" ", return_vertices=True
                )
                connectome = np.array(node_weights)
                connectome = np.atleast_3d(connectome)

                if pipe == "dwi":
                    spread, i, h, c, i_t, h_t, c_t = ipsi_calc(
                        connectome, atlas, pipeline=pipe, verbose=False
                    )
                    ipsi_t.append(i_t)
                    hom_t.append(h_t)
                    contra_t.append(c_t)

                else:
                    spread, i, h, c = ipsi_calc(
                        connectome, atlas, pipeline=pipe, verbose=False
                    )

                results.append(spread)
                ipsi.append(i)
                hom.append(h)
                contra.append(c)

            if "DKT" in atlas:
                a = "dkt"
                atlas = "DKT"
            elif "Hammer" in atlas:
                a = "hammer"
                atlas = "Hammer"
            elif "AAL" in atlas:
                a = "aal"
                atlas = "AAL"

            if pipe == "func":
                ipsi_t = ipsi
                contra_t = contra
                hom_t = hom

            with open(f"{pipe}_ipsi_{a}.csv", mode="a") as result_file:
                result_writer = csv.writer(result_file, delimiter=" ")
                result_writer.writerow([f"Dataset", f"Atlas", f"Type", f"Value"])
                for idx, i in enumerate(ipsi_t):
                    result_writer.writerow([f"{title}", f"{atlas}", f"Ipsi", i])
                for idx, i in enumerate(hom_t):
                    result_writer.writerow([f"{title}", f"{atlas}", f"Hom", i])
                for idx, i in enumerate(contra_t):
                    result_writer.writerow([f"{title}", f"{atlas}", f"Contra", i])

            print(f"{atlas}:")
            print(f"Ipsi count: {results.count('i')}")
            print(f"Mean: {np.array(ipsi).mean()} and STD: {np.array(ipsi).std()}")
            print(f"Homotopic count: {results.count('h')}")
            print(f"Mean: {np.array(hom).mean()} and STD: {np.array(hom).std()}")
            print(f"Contra count: {results.count('c')}")
            print(
                f"Mean: {np.array(contra).mean()} and STD: {np.array(contra).std()}\n\n"
            )

            if pipe == "dwi":
                print(
                    f"Ipsi Mean: {np.array(ipsi_t).mean()} and STD: {np.array(ipsi_t).std()}"
                )
                print(
                    f"Homotopic Mean: {np.array(hom_t).mean()} and STD: {np.array(hom_t).std()}"
                )
                print(
                    f"Contra Mean: {np.array(contra_t).mean()} and STD: {np.array(contra_t).std()}\n\n"
                )

            # Print info to csv file

            with open("results.csv", mode="a") as result_file:
                result_writer = csv.writer(result_file, delimiter=" ")
                result_writer.writerow(
                    [
                        f"{atlas}",
                        f"{results.count('i')}",
                        f"{np.array(ipsi).mean()}",
                        f"{np.array(ipsi).std()}",
                        f"{np.array(ipsi_t).mean()}",
                        f"{np.array(ipsi_t).std()}",
                        f"{results.count('h')}",
                        f"{np.array(hom).mean()}",
                        f"{np.array(hom).std()}",
                        f"{np.array(hom_t).mean()}",
                        f"{np.array(hom_t).std()}",
                        f"{results.count('c')}",
                        f"{np.array(contra).mean()}",
                        f"{np.array(contra).std()}",
                        f"{np.array(contra_t).mean()}",
                        f"{np.array(contra_t).std()}",
                    ]
                )


if __name__ == "__main__":
    main()
