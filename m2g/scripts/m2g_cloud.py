#!/usr/bin/env python

"""
m2g.scripts.m2g_cloud
~~~~~~~~~~~~~~~~~~~~~~~

Contains functionality for running m2g in batch on AWS.
For a tutorial on setting this up, see here : https://github.com/neurodata/m2g/blob/deploy/tutorials/Batch.ipynb
"""

# standard library imports
import subprocess
import re
import os
import sys
import json
from copy import deepcopy
from collections import OrderedDict
from argparse import ArgumentParser
from pathlib import Path

# m2g imports
import m2g
from m2g.utils import gen_utils
from m2g.utils.cloud_utils import get_credentials
from m2g.utils.cloud_utils import get_matching_s3_objects
from m2g.utils.cloud_utils import s3_client


def batch_submit(
    bucket,
    path,
    jobdir,
    credentials=None,
    state="participant",
    dataset=None,
    modif="",
    pipe="dwi",
    acquisition="alt+z",
    tr="2.0",
    mem_gb="10",
    n_cpus="2",
    parcellation="desikan",
    voxel_size="2mm",
    mod_type="det",
    filtering_type="local",
    diffusion_model="csa",
    space="native",
    seed=20,
):
    """Searches through an S3 bucket, gets all subject-ids, creates json files for each,
    submits batch jobs, and returns list of job ids to query status upon later

    Parameters
    ----------
    bucket : str
        The S3 bucket with the input dataset formatted according to the BIDS standard.
    path : str
        The directory where the dataset is stored on the S3 bucket
    jobdir : str
        Directory of batch jobs to generate/check up on
    credentials : [type], optional
        AWS formatted csv of credentials, by default None
    state : str, optional
        determines the function to be performed by this function ("participant", "status", "kill"), by default "participant"
    dataset : str, optional
        Name given to the output directory containing analyzed data set "m2g-<version>-<dataset>", by default None
    modif : str, optional
        Name of folder on s3 to push to. If empty, push to a folder with m2g's version number, by default ""
    pipe : str, optional
        Which pipeline, 'dwi' for diffusion MRI or 'func' for fMRI, default is 'dwi'
    acquisition : str, optional
        The acquisition method for the fMRI data being analyze (only needed for functional pipeline), default is 'alt+z'
    tr : str, optional
        TR (in seconds) for the fMRI data (only needed for functional pipeline), default is '2.0'
    parcellation : str, optional
        The parcellation(s) being analyzed. Multiple parcellations can be provided with a space separated list. Default is 'desikan'
    voxel_size : str, optional
        Voxel size : 2mm, 1mm. Voxel size to use for template registrations. Default is '2mm'
    mod_type : str, optional
        Determinstic (det) or probabilistic (prob) tracking, by default "det"
    filtering_type : str, optional
        Tracking approach: local, particle. Default is local
    diffusion_model : str, optional
        Diffusiont model: csd or csa. Default is csa
    space : str, optional
        Space for tractography, by default "native"
    seed : int optional
        Seed density for tractography. Default is 20
    """

    print(f"Getting list from s3://{bucket}/{path}/...")
    threads = crawl_bucket(bucket, path, jobdir)

    print("Generating job for each subject...")
    jobs = create_json(
        bucket,
        path,
        threads,
        jobdir,
        credentials=credentials,
        dataset=dataset,
        modif=modif,
        pipe=pipe,
        acquisition=acquisition,
        tr=tr,
        mem_gb=mem_gb,
        n_cpus=n_cpus,
        parcellation=parcellation,
        voxel_size=voxel_size,
        mod_type=mod_type,
        filtering_type=filtering_type,
        diffusion_model=diffusion_model,
        space=space,
        seed=seed,
    )

    print("Submitting jobs to the queue...")
    submit_jobs(jobs, jobdir)


def crawl_bucket(bucket, path, jobdir):
    """Gets subject list for a given s3 bucket and path

    Parameters
    ----------
    bucket : str
        s3 bucket
    path : str
        The directory where the dataset is stored on the S3 bucket
    jobdir : str
        Directory of batch jobs to generate/check up on

    Returns
    -------
    OrderedDict
        dictionary containing all subjects and sessions from the path location
    """

    # if jobdir has seshs info file in it, use that instead
    sesh_path = f"{jobdir}/seshs.json"
    if os.path.isfile(sesh_path):
        print("seshs.json found -- loading bucket info from there")
        with open(sesh_path, "r") as f:
            seshs = json.load(f)
        print("Information obtained from s3.")
        return seshs

    # set up bucket crawl
    subj_pattern = r"(?<=sub-)(\w*)(?=/ses)"
    sesh_pattern = r"(?<=ses-)(\d*)"
    all_subfiles = get_matching_s3_objects(bucket, path + "/sub-", ".nii.gz")
    subjs = list(set(re.findall(subj_pattern, obj)[0] for obj in all_subfiles))
    seshs = OrderedDict()

    # populate seshs
    for subj in subjs:
        prefix = f"{path}/sub-{subj}/"
        all_seshfiles = get_matching_s3_objects(bucket, prefix, ".nii.gz")
        sesh = list(set([re.findall(sesh_pattern, obj)[0] for obj in all_seshfiles]))
        if sesh != []:
            seshs[subj] = sesh
            print(f"{subj} added to seshs.")
        else:
            seshs[subj] = None
            print(f"{subj} not added (no sessions).")

    # print session IDs and create json cache
    print(
        (
            "Session IDs: "
            + ", ".join(
                [
                    subj + "-" + sesh if sesh is not None else subj
                    for subj in subjs
                    for sesh in seshs[subj]
                ]
            )
        )
    )
    with open(sesh_path, "w") as f:
        json.dump(seshs, f)
    print(f"{sesh_path} created.")
    print("Information obtained from s3.")
    return seshs


def create_json(
    bucket,
    path,
    threads,
    jobdir,
    credentials=None,
    dataset=None,
    modif="",
    pipe="dwi",
    acquisition="alt+z",
    tr="2.0",
    mem_gb="10",
    n_cpus="2",
    parcellation="desikan",
    voxel_size="2mm",
    mod_type="det",
    filtering_type="local",
    diffusion_model="csa",
    space="native",
    seed=20,
):
    """Creates the json files for each of the jobs

    Parameters
    ----------
    bucket : str
        The S3 bucket with the input dataset formatted according to the BIDS standard.
    path : str
        The directory where the dataset is stored on the S3 bucket
    threads : OrderedDict
        dictionary containing all subjects and sessions from the path location
    jobdir : str
        Directory of batch jobs to generate/check up on
    credentials : [type], optional
        AWS formatted csv of credentials, by default None
    dataset : [type], optional
        Name added to the generated json job files "m2g_<version>_<dataset>_sub-<sub>_ses-<ses>", by default None
    modif : str, optional
        Name of folder on s3 to push to. If empty, push to a folder with m2g's version number, by default ""
    pipe : str, optional
        Which pipeline, 'dwi' for diffusion MRI or 'func' for fMRI, default is 'dwi'
    acquisition : str, optional
        The acquisition method for the fMRI data being analyze (only needed for functional pipeline), default is 'alt+z'
    tr : str, optional
        TR (in seconds) for the fMRI data (only needed for functional pipeline), default is '2.0'
    parcellation : str, optional
        The parcellation(s) being analyzed. Multiple parcellations can be provided with a space separated list. Default is 'desikan'
    voxel_size : str, optional
        Voxel size : 2mm, 1mm. Voxel size to use for template registrations. Default is '2mm'
    mod_type : str, optional
        Determinstic (det) or probabilistic (prob) tracking, by default "det"
    space : str, optional
        Space for tractography, by default ""
    filtering_type : str, optional
        Tracking approach: local, particle. Default is local
    diffusion_model : str, optional
        Diffusiont model: csd or csa. Default is csa
    space : str, optional
        Space for tractography, by default "native"
    seed : int optional
        Seed density for tractography. Default is 20

    Returns
    -------
    list
        list of job jsons
    """
    jobsjson = f"{jobdir}/jobs.json"
    if os.path.isfile(jobsjson):
        with open(jobsjson, "r") as f:
            jobs = json.load(f)
        return jobs

    # set up infrastructure
    jobdir = Path(jobdir)
    (jobdir / "jobs").mkdir(parents=True, exist_ok=True)
    (jobdir / "ids").mkdir(parents=True, exist_ok=True)
    jobdir = str(jobdir)
    seshs = threads

    templ = os.path.dirname(__file__)
    tpath = templ[: templ.find("/m2g/scripts")]

    with open(f"{tpath}/templates/m2g_cloud_participant.json", "r") as inf:
        template = json.load(inf)

    cmd = template["containerOverrides"]["command"]
    env = template["containerOverrides"]["environment"]

    # TODO : This checks for any credentials csv file, rather than `/.aws/credentials`.
    # modify template
    if credentials is not None:
        env[0]["value"], env[1]["value"] = get_credentials()
    else:
        env = []
    template["containerOverrides"]["environment"] = env

    # edit non-defaults
    jobs = []
    cmd[cmd.index("<PIPE>")] = pipe
    cmd[cmd.index("<ACQ>")] = acquisition
    cmd[cmd.index("<TR>")] = tr
    cmd[cmd.index("<MEM>")] = mem_gb
    cmd[cmd.index("<CPUS>")] = n_cpus
    cmd[cmd.index("<PUSH>")] = f"s3://{bucket}/{path}/{modif}"
    cmd[cmd.index("<PARCEL>")] = parcellation
    cmd[cmd.index("<VOX>")] = voxel_size
    cmd[cmd.index("<MOD>")] = mod_type
    cmd[cmd.index("<FILTER>")] = filtering_type
    cmd[cmd.index("<DIFF>")] = diffusion_model
    cmd[cmd.index("<SPACE>")] = space
    cmd[cmd.index("<SEED>")] = seed
    cmd[cmd.index("<INPUT>")] = f"s3://{bucket}/{path}"

    # edit participant-specific values ()
    # loop over every session of every participant
    for subj in seshs.keys():
        print(f"... Generating job for sub-{subj}")
        # and for each subject number in each participant number,
        for sesh in seshs[subj]:
            # add format-specific commands,
            job_cmd = deepcopy(cmd)
            job_cmd[job_cmd.index("<SUBJ>")] = subj
            if sesh is not None:
                job_cmd[job_cmd.index("<SESH>")] = sesh

            # then, grab the template,
            # add additional parameters,
            # make the json file for this iteration,
            # and add the path to its json file to `jobs`.
            job_json = deepcopy(template)
            ver = m2g.__version__.replace(".", "-")
            if dataset:
                name = f"m2g_{ver}_{dataset}_sub-{subj}"
            else:
                name = f"m2g_{ver}_sub-{subj}"
            if sesh is not None:
                name = f"{name}_ses-{sesh}"
            print(job_cmd)
            job_json["jobName"] = name
            job_json["containerOverrides"]["command"] = job_cmd
            job = os.path.join(jobdir, "jobs", name + ".json")
            with open(job, "w") as outfile:
                json.dump(job_json, outfile)
            jobs += [job]

    # return list of job jsons
    with open(jobsjson, "w") as f:
        json.dump(jobs, f)
    return jobs


def submit_jobs(jobs, jobdir):
    """Give list of jobs to submit, submits them to AWS Batch

    Parameters
    ----------
    jobs : list
        Name of the json files for all jobs to submit
    jobdir : str
        Directory of batch jobs to generate/check up on

    Returns
    -------
    int
        0
    """

    batch = s3_client(service="batch")

    for job in jobs:
        with open(job, "r") as f:
            kwargs = json.load(f)
        print(f"... Submitting job {job}...")
        submission = batch.submit_job(**kwargs)
        print((f'Job Name: {submission["jobName"]}, Job ID: {submission["jobId"]}'))
        sub_file = os.path.join(jobdir, "ids", submission["jobName"] + ".json")
        with open(sub_file, "w") as outfile:
            json.dump(submission, outfile)
        print("Submitted.")
    return 0


def kill_jobs(jobdir, reason='"Killing job"'):
    """Given a list of jobs, kills them all

    Parameters
    ----------
    jobdir : str
        Directory of batch jobs to generate/check up on
    reason : str, optional
        Task you want to perform on the jobs, by default '"Killing job"'
    """

    print(f"Cancelling/Terminating jobs in {jobdir}/ids/...")
    jobs = os.listdir(jobdir + "/ids/")
    batch = s3_client(service="batch")
    jids = []
    names = []

    # grab info about all the jobs
    for job in jobs:
        with open(f"{jobdir}/ids/{job}", "r") as inf:
            submission = json.load(inf)
        jid = submission["jobId"]
        name = submission["jobName"]
        jids.append(jid)
        names.append(name)

    for jid in jids:
        print(f"Terminating job {jid}")
        batch.terminate_job(jobId=jid, reason=reason)


# %%
def main():
    parser = ArgumentParser(
        description="This is a pipeline for running BIDs-formatted diffusion MRI datasets through AWS S3 to produce connectomes."
    )
    parser.add_argument(
        "--state",
        choices=["participant", "status", "kill"],
        default="participant",
        help="determines the function to be performed by m2g_cloud.",
    )
    parser.add_argument(
        "--bucket",
        help="""The S3 bucket with the input dataset
         formatted according to the BIDS standard.""",
    )
    parser.add_argument(
        "--bidsdir",
        help="""The path of the directory where the dataset
        lives on the S3 bucket.""",
    )
    parser.add_argument(
        "--jobdir",
        action="store",
        help="""Local directory where the generated batch jobs will be
        saved/run through in case of batch termination or check-up.""",
    )
    parser.add_argument(
        "--modif",
        action="store",
        help="""Name of folder on s3 to push to. Data will be saved at '<bucket>/<bidsdir>/<modif>' on the s3 bucket
        If empty, push to a folder with m2g's version number.""",
        default="",
    )
    parser.add_argument(
        "--credentials", action="store", help="csv formatted AWS credentials."
    )
    # parser.add_argument("--dataset", action="store", help="Dataset name")
    parser.add_argument(
        "--pipeline",
        action="store",
        help="""Pipline to use when analyzing the input data, 
        either func or dwi. If  Default is dwi.""",
        default="dwi",
    )
    parser.add_argument(
        "--acquisition",
        action="store",
        help="""Acquisition method for functional data:
        altplus - Alternating in the +z direction
        alt+z - Alternating in the +z direction
        alt+z2 - Alternating, but beginning at slice #1
        altminus - Alternating in the -z direction
        alt-z - Alternating in the -z direction
        alt-z2 - Alternating, starting at slice #nz-2 instead of #nz-1
        seqplus - Sequential in the plus direction
        seqminus - Sequential in the minus direction,
        default is alt+z. For more information:https://fcp-indi.github.io/docs/user/func.html""",
        default="alt+z",
    )
    parser.add_argument(
        "--tr",
        action="store",
        help="functional scan TR (seconds). Not required for dwi pipeline. Default is 2.0",
        default="2.0",
    )
    parser.add_argument(
        "--mem_gb",
        action="store",
        help="The memory (in gigabytes) that the functional pipeline has access to. Not required for dwi pipeline. Default is 10 Gb",
        default="10",
    )
    parser.add_argument(
        "--n_cpus",
        action="store",
        help="Number of cpus that the functional pipeline has access to. Not required for dwi pipeline. Default is 2 cpus.",
    )
    parser.add_argument(
        "--parcellation",
        action="store",
        help="The parcellation(s) being analyzed. Multiple parcellations can be provided with a space separated list.",
        nargs="+",
        default=None,
    )
    parser.add_argument(
        "--voxelsize",
        action="store",
        default="2mm",
        help="Voxel size : 2mm, 1mm. Voxel size to use for template registrations.",
    )
    parser.add_argument(
        "--mod",
        action="store",
        help="Determinstic (det) or probabilistic (prob) tracking. Default is det.",
        default="det",
    )
    parser.add_argument(
        "--filtering_type",
        action="store",
        help="Tracking approach: local, particle. Default is local.",
        default="local",
    )
    parser.add_argument(
        "--diffusion_model",
        action="store",
        help="Diffusion model: csd, csa. Default is csa.",
        default="csa",
    )
    parser.add_argument(
        "--space",
        action="store",
        help="Space for tractography. Default is native.",
        default="native",
    )
    parser.add_argument(
        "--seeds",
        action="store",
        help="Seeding density for tractography. Default is 20.",
        default="20",
    )

    result = parser.parse_args()

    state = result.state
    bucket = result.bucket
    path = result.bidsdir
    path = path.strip("/") if path is not None else path
    dset = path.split("/")[-1] if path is not None else None
    jobdir = result.jobdir
    modif = result.modif
    creds = result.credentials
    pipe = result.pipeline
    acquisition = result.acquisition
    tr = result.tr
    mem_gb = result.mem_gb
    n_cpus = result.n_cpus
    parcellation = result.parcellation
    vox = result.voxelsize
    mod_type = result.mod
    filtering_type = result.filtering_type
    diffusion_model = result.diffusion_model
    space = result.space
    seed = result.seeds

    if jobdir is None:
        jobdir = "./"

    if (bucket is None or path is None) and (state != "status" and state != "kill"):
        sys.exit(
            "Requires either path to bucket and data, or the status flag"
            " and job IDs to query.\n  Try:\n    m2g_cloud --help"
        )
    if state == "kill":
        print("Killing jobs...")
        kill_jobs(jobdir)
    elif state == "participant":
        print("Beginning batch submission process...")
        if not os.path.exists(jobdir):
            print("job directory not found. Creating...")
            Path(jobdir).mkdir(parents=True)
        batch_submit(
            bucket,
            path,
            jobdir,
            credentials=creds,
            state=state,
            dataset=dset,
            modif=modif,
            pipe=pipe,
            acquisition=acquisition,
            tr=tr,
            mem_gb=mem_gb,
            n_cpus=n_cpus,
            parcellation=parcellation,
            voxel_size=vox,
            mod_type=mod_type,
            filtering_type=filtering_type,
            diffusion_model=diffusion_model,
            space=space,
            seed=seed,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
