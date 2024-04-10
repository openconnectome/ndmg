# m2g on AWS Batch

To run m2g on entire datasets, we use AWS Batch. <br>

## Requirements

- Docker
- An AWS account
- Your dataset on S3

## Overview

Our Batch pipeline works as follows.

1. Parse a BIDs-formatted dataset on s3 into a set of scans.
2. For each scan, create a JSON file containing its subject ID, session ID, and m2g parameters.
3. For each JSON file, send a job to AWS.
4. AWS, upon receiving each job, creates a new EC2 instance, grabs our Docker image, and then runs a container using the arguments specified in the JSON.
5. The container then pulls the input data for that particular scan from S3, runs m2g using that data, and upon completion, pushes the data back to S3 in the relevant location.

Steps 4 and 5 above occur in parallel -- meaning, if you have a dataset with 200 scans, there will be 200 EC2 instances running at the same time.

For arbitrarily large datasets, full runs generally take a little over an hour, at roughly \$.05/scan.

## Batch Setup : Console

This section shows you how to set up a batch environment such that you can easily run m2g in parallel. For more in-depth documentation, see the [AWS official documentation](https://docs.aws.amazon.com/batch/index.html).

### Compute Environment

Your compute environment defines the compute resources AWS will use for its instances.

For m2g, we recommend using using `r5.large` instance types for `csd` and `r5.xlarge` for `csa`.

#### Initial Setup

**TODO : check if default roles can access s3 <br>**
Here, you define who can access the environment. We recommend using the default IAM roles.

1. Use Managed
2. Define a compute environment name
3. Define a service role. The default IAM is best.
4. Define an instance role. The default IAM (ecsInstanceRole) is best.
5. If you want to connect to your environments, you'll need a key-pair. This is optional; if you want to set this up, see the [official documentation](https://docs.aws.amazon.com/batch/latest/userguide/get-set-up-for-aws-batch.html#create-a-key-pair).

![initial compute](https://i.imgur.com/vEmEpuf.png)

#### Compute Resources

This section lets you define what resources your environment will use. You don't need to use any launch templates here; essentially the only thing necessary is to set the instance type to `r5.large`, and to raise the maximum vCPUs (in case you're running large datasets)

1. Set Allowed Instance types to `r5.large`
2. Set minimum vCPUs to 0

![Compute Resources](https://i.imgur.com/QZh4IlG.png)

You can leave the rest of the options set as default in compute environments.

### Job Queue

Now, attach the compute environment to the job queue.

1. Click "create queue" in "Job Queues"
2. Give a queue name
3. Give a priority (e.g., `1`)
4. Attach the compute environment you just created to the job queue
5. Click "Create Job Queue"

![queue](https://i.imgur.com/wJk8Og0.png)

### Job Definition

The job definition is where you specify the container, the job role, the vCPUs, and the memory.

1. For "container image", you can use `neurodata/m2g:latest`.
2. For vCPUs, use 2.
3. Because we want to use one r5.large EC2 instance per scan, use `15200` for the memory.

You can leave the other parameters empty.

![def1](https://i.imgur.com/n1l2lPo.png)

## Running the Pipeline

Given that you've set up your batch environment properly, and your IAM credentials are set up properly, submitting jobs to batch is relatively simple:

        m2g_cloud participant --bucket <bucket> --bidsdir <path on bucket> --jobdir <local/jobdir> --modif <name-of-s3-directory-output>

An example using one of our s3 buckets can be seen below. Note that your dataset must be BIDs-formatted.:

        m2g_cloud participant --bucket ndmg-data --sp native --bidsdir HNU1 --jobdir ~/.ndmg/jobs/HNU1-08-21-native --modif ndmg-08-21-native --dataset HNU1

Note that the above example won't work for people without access to our bucket.

Behind the scenes, what happens here is:

1. `m2g` parses through your s3 bucket, and gets the locations of all subjects and sessions
2. A unique `json` file is created for each scan, containing the m2g run parameters for that scan.
3. Every `json` file is submitted sequentially to `AWS-Batch`, and a job begins that runs that scan.
4. Once the scan is done, the output data is pushed to the output location on `s3` specified by `--modif`.

## Monitoring Runs

You can see all of your runs in the `Batch` Dashboard.

![batch-runs](https://i.imgur.com/b9GbKdT.png)

You can monitor the outputs of a given run by clicking on it and clicking `View logs for the most recent attempt in the CloudWatch console`.

![cloudwatch](https://i.imgur.com/K4djTW1.png)

When all of your runs finish, the outputs will on `s3`, and you can use your favorite way to pull your graphs to your local machine!
