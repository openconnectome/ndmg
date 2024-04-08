import os
import shutil
import subprocess
import sys

import numpy as np
import regex as re
import yaml

from m2g.utils.gen_utils import run


def make_dataconfig(input_dir, sub, ses, anat, func, acquisition="alt+z", tr=2.0):
    """Generates the data_config file needed by cpac

    Arguments:
        input_dir {str} -- Path of directory containing input files
        sub {int} -- subject number
        ses {int} -- session number
        anat {str} -- Path of anatomical nifti file
        func {list} -- Path of functional nifti file
        acquisition {str} -- acquisition method for funcitonal scan
        tr {float} -- TR (seconds) of functional scan

    Returns:
        None
    """

    for idx, funcf in enumerate(func):
        # Extract information from the
        ffile = funcf.find("/func/sub-")
        ffile = funcf[(ffile + 6) :]
        taskname = re.compile(r"task-(\w*)_")
        acq = re.compile(r"_acq-(\w*)_bold")
        task = taskname.search(ffile)
        task = task.groups()[0]
        acq = acq.search(ffile)
        try:
            acq = acq.groups()[0]
            float(acq)
            new_tr = str(float(acq) / 1000)
            print(f"TR extracted from filename of {ffile}")
        except:
            print(f"No TR information found in {ffile}")
            new_tr = tr

        if idx == 0:
            Data = [
                {
                    "subject_id": sub,
                    "unique_id": f"ses-{ses}",
                    "anat": anat,
                    "func": {
                        #'rest_run-1': {
                        f"{task}-{acq}": {
                            "scan": funcf,
                            "scan_parameters": {
                                "acquisition": acquisition,
                                "tr": new_tr,
                            },
                        }
                    },
                }
            ]
        else:
            Data[0]["func"][f"{task}-{acq}"] = {
                "scan": funcf,
                "scan_parameters": {"acquisition": acquisition, "tr": new_tr},
            }

    config_file = f"{input_dir}/data_config.yaml"
    with open(config_file, "w", encoding="utf-8") as outfile:
        yaml.dump(Data, outfile, default_flow_style=False)

    return config_file


def make_script(input_dir, output_dir, data_config, pipeline_config, mem_gb, n_cpus):
    """Make a bash script file for calling the m2g-f pipeline from CPAC

    Args:
        input_dir {str}: path to input directory containing fMRI data in BIDS format
        output_dir {str}: path to directory containing outputs from CPAC
        data_config {str}: path to data configuration file for this run of CPAC
        pipeline_config {str}: path to pipeline configuration file for this run of CPAC
        mem_gb {str}: number of gigabytes available for CPAC use
        n_cpus {str}: number of cpus available for CPAC use

    Returns:
        _type_: _description_
    """
    cpac_script = "/root/.m2g/cpac_script.sh"
    with open(cpac_script, "w+", encoding="utf-8") as script:
        script.write(
            f"""#! /bin/bash
        python3 /code/run.py --data_config_file {data_config} --pipeline_file {pipeline_config} --n_cpus {n_cpus} --mem_gb {mem_gb} {input_dir} {output_dir} participant
        """
        )

    run(f"chmod +x {cpac_script}")

    return cpac_script


def func_dir_reorg(outDir):
    """Functional directory reorganization. Takes the CPAC outputs for the m2g-f pipeline and reorganizes it into a more user-friendly format

    Args:
        outDir {string}: string containing path to functional pipeline output directory
    """
    subj_pattern = r"(?<=sub-)(\w*)(?=/ses)"
    sesh_pattern = r"(?<=ses-)(\d*)"
    atlas_pattern = r"(?<=Human..)\S*"  # (?=/roi)"

    # Convert connectomes into edgelists
    for root, dirs, files in os.walk(outDir + "/output"):
        for file in files:

            # Create non-absolute value connectome from timeseries
            if file.endswith("roi_stats.npz"):
                try:
                    sub = re.findall(subj_pattern, root)[0]
                    ses = re.findall(sesh_pattern, root)[0]
                    atlas = re.findall(atlas_pattern, root)[0]

                    edg_dir = f"{outDir}/connectomes_f/{atlas}"
                    subsesh = f"sub-{sub}_ses-{ses}"

                    a = np.load(os.path.join(root, file))
                    dat = a["arr_0"][1:, :]
                    my_data = np.corrcoef(dat.T)
                    my_data = np.nan_to_num(my_data).astype(object)

                    a = sum(range(1, len(my_data)))
                    arr = np.zeros((a, 3))
                    z = 0
                    for num in range(len(my_data)):
                        for j in range(len(my_data[num])):
                            if j > num:
                                # print(f'{num+1} {i+1} {my_data[num][i]}')
                                arr[z][0] = f"{num+1}"
                                arr[z][1] = f"{j+1}"
                                arr[z][2] = my_data[num][j]
                                z = z + 1

                    os.makedirs(f"{edg_dir}", exist_ok=True)
                    np.savetxt(
                        f"{edg_dir}/{subsesh}_func_{atlas}_edgelist.csv",
                        arr,
                        fmt="%d %d %f",
                        delimiter=" ",
                    )

                    my_data = np.abs(np.corrcoef(dat.T))
                    my_data = np.nan_to_num(my_data).astype(object)

                    a = sum(range(1, len(my_data)))
                    arr = np.zeros((a, 3))
                    z = 0
                    for num in range(len(my_data)):
                        for j in range(len(my_data[num])):
                            if j > num:
                                arr[z][0] = f"{num+1}"
                                arr[z][1] = f"{j+1}"
                                arr[z][2] = my_data[num][j]
                                z = z + 1

                    np.savetxt(
                        f"{edg_dir}/{subsesh}_func_{atlas}_abs_edgelist.csv",
                        arr,
                        fmt="%d %d %f",
                        delimiter=" ",
                    )

                    print(f"{file} converted to edgelist")

                    # Move roi-timeseries folders without stupid naming convention
                    shutil.move(
                        os.path.join(root),
                        os.path.join("/", os.path.join(*root.split("/")[:-1]), atlas),
                    )
                except:
                    print("Already converted roi_stats found")

    # Reorganize the folder structure
    reorg = {
        "anat_f": [
            "anatomical_b",
            "anatomical_w",
            "anatomical_c",
            "anatomical_r",
            "anatomical_t",
            "anatomical_g",
            "seg_",
        ],
        "func/preproc": [
            "coordinate",
            "frame_w",
            "functional_b",
            "functional_f",
            "functional_n",
            "functional_p",
            "motion",
            "slice",
            "raw",
        ],
        "func/register": [
            "mean_functional",
            "functional_to",
            "functional_in",
            "max_",
            "movement_par",
            "power_",
            "roi",
        ],
        "qa_f": [
            "mni_normalized_",
            "carpet",
            "csf_gm",
            "mean_func_",
            "rot_plot",
            "trans_plot",
            "skullstrip_vis",
            "snr_",
        ],
    }

    moved = set()
    for root, dirs, files in os.walk(outDir, topdown=False):
        if "cpac_" and "functional_pipeline_settings.yaml" in files:
            os.makedirs(os.path.join(outDir, "log_f"), exist_ok=True)
            for i in files:
                shutil.move(os.path.join(root, i), os.path.join(outDir, "log_f", i))
            moved.add(root)
        if ("cpac_individual_timing_m2g.csv" in files) or ("pypeline.log" in files):
            os.makedirs(os.path.join(outDir, "log_f"), exist_ok=True)
            for i in files:
                shutil.move(os.path.join(root, i), os.path.join(outDir, "log_f", i))
            moved.add(root)

    for root, dirs, files in os.walk(outDir + "/output"):
        if root not in moved and "workingDirectory" not in root:
            for cat in reorg:
                for nam in reorg[cat]:
                    if nam in root.split("/")[-1]:
                        # Get rid of the stupid in-between subdirectory
                        if "_scan_rest-None" in dirs:
                            _ = os.path.join(outDir, cat, root.split("/")[-1])
                            os.makedirs(_, exist_ok=True)
                            for fil in os.listdir(
                                os.path.join(root, "_scan_rest-None")
                            ):
                                try:
                                    shutil.move(
                                        os.path.join(root, "_scan_rest-None", fil), _
                                    )
                                except:
                                    print(
                                        f"Target: {_} already exists. Skipping file movement..."
                                    )

                            moved.add(root)

                        else:
                            _ = os.path.join(outDir, cat)
                            if cat != "connectomes_f" and cat != "log_f":
                                os.makedirs(_, exist_ok=True)
                            try:
                                shutil.move(root, _)
                            except:
                                print(
                                    f"Target: {_} already exists. Skipping file movement..."
                                )

                            moved.add(root)
                            _ = os.path.join(_, root.split("/")[-1])

                        for r, d, ff in os.walk(_):
                            nono = ["_montage_", "_selector_", "ses-"]
                            for i, element in enumerate(d):
                                for q in nono:
                                    if q in element:
                                        for f in os.listdir(os.path.join(r, d[i])):
                                            try:
                                                shutil.move(os.path.join(r, d[i], f), _)
                                            except:
                                                print(
                                                    f"Target: {_} already exists. Skipping file movement..."
                                                )
                                        # os.rmdir(os.path.join(r,d[i]))
                                        shutil.rmtree(
                                            os.path.join(r, d[i]), ignore_errors=True
                                        )
    # get rid of cpac output folder
    shutil.rmtree(os.path.join(outDir, "output"), ignore_errors=True)
    shutil.rmtree(os.path.join(outDir, "log"), ignore_errors=True)


def m2g_func_worker(
    input_dir,
    output_dir,
    sub,
    ses,
    anat,
    bold,
    vox,
    parcellations,
    acquisition,
    tr,
    mem_gb,
    n_cpus,
):
    """Creates the requisite files to run CPAC, then calls CPAC and runs it in a terminal

    Arguments:
        input_dir {str} -- Path to input directory
        output_dir {str} -- Path to output directory
        sub {int} -- subject number
        ses {int} -- session number
        anat {str} -- Path of anatomical nifti file
        bold {str} -- Path of functional nifti file
        parcellations {list} -- Parcellation(s) that will be used in the analysis
        acquisition {str} -- Acquisition method for funcitional scans
        tr {str} -- TR time, in seconds
    """

    pipeline_config = "/m2g/m2g/functional/m2g_pipeline.yaml"

    # If parcellations specified, create dictionary to alter yaml file
    if parcellations:
        os.makedirs(f"{output_dir}", exist_ok=True)
        parcs = {}

        for p in parcellations:
            parcs[p] = "Avg"

        # Read in desired parcellations
        with open(pipeline_config, "r", encoding="utf-8") as func_config:
            config = yaml.safe_load(func_config)

        # Replace 'tsa_roi_paths'
        config["tsa_roi_paths"][0] = parcs

        # Change voxel size to match user input
        config["resolution_for_anat"] = vox
        config["resolution_for_func_preproc"] = vox
        config["resolution_for_func_derivative"] = vox

        # Create new pipeline yaml file in a different location
        pipeline_config = f"{output_dir}/functional_pipeline_settings.yaml"

        with open(pipeline_config, "w", encoding="utf-8") as outfile:
            yaml.dump(config, outfile, default_flow_style=False)

    if not isinstance(bold, list):
        bold = (bold,)
        print("Single functional nifti file found")

    data_config = make_dataconfig(input_dir, sub, ses, anat, bold, acquisition, tr)
    cpac_script = make_script(
        input_dir, output_dir, data_config, pipeline_config, mem_gb, n_cpus
    )

    # Run pipeline with resource monitor
    # subprocess.Popen(['free','-m','-c',f'{itterations}','-s',f'{period}'])
    subprocess.call([cpac_script], shell=True)
