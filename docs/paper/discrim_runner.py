# standard library imports
import os
from argparse import ArgumentParser

# m2g imports
# from m2g.scripts.discrim import discrim_runner, avgconnectome
# from .discrim import discrim_runner, avgconnectome
import discrim
from m2g.utils import cloud_utils
from m2g.utils.gen_utils import as_directory


def main():
    """Starting point of the m2g pipeline, assuming that you are using a BIDS organized dataset"""
    parser = ArgumentParser(
        description="This is an end-to-end connectome estimation pipeline from M3r Images."
    )
    parser.add_argument(
        "input_dir",
        help="""The directory with the input dataset
        formatted according to the BIDS standard.
        To use data from s3, just pass `s3://<bucket>/<dataset>` as the input directory.""",
    )
    parser.add_argument(
        "output_dir",
        help="""The local directory where the output
        files should be stored.""",
    )
    parser.add_argument(
        "pipeline",
        help="""Pipeline that created the data, either 'dwi' or 'func'""",
    )
    parser.add_argument(
        "--ptr", action="store", help="whether to pass to ranks", default=True
    )
    parser.add_argument(
        "--discrim",
        action="store",
        help="Whether or not to calculate discriminability",
        default=True,
    )
    parser.add_argument(
        "--push_location",
        action="store",
        help="Name of folder on s3 to push output data to, if the folder does not exist, it will be created."
        "Format the location as `s3://<bucket>/<path>`",
        default=None,
    )
    parser.add_argument(
        "--atlases",
        action="store",
        help="which atlases to use",
        nargs="+",
        default=None,
    )
    result = parser.parse_args()
    input_dir = result.input_dir
    output_dir = result.output_dir
    pipe = result.pipeline
    ptr = result.ptr
    disc = result.discrim
    push_location = result.push_location
    atlases = result.atlases

    ##---------------------------------------------------Start Discrim Calc--------------------------------------------------------------##

    # Inputs needed:

    # input_dir = location on bucket to download from
    # push_location = where to push the discrim values and resulting connectomes
    # ptr = whether to do PTR for functional
    # atlases = which atlases to analyze (if none spceified, just get them all)

    # grab files from s3
    creds = bool(cloud_utils.get_credentials())

    buck, remo = cloud_utils.parse_path(input_dir)
    home = os.path.expanduser("~")
    input_dir = as_directory(home + "/.m2g/input", remove=True)
    if (not creds) and push_location:
        raise AttributeError(
            """No AWS credentials found, but "--push_location" flag called. 
            Pushing will most likely fail."""
        )

    # Get S3 input data if needed
    if pipe == "func":
        if atlases is not None:
            for atlas in atlases:
                info = f"{atlas}"
                cloud_utils.s3_get_data(
                    buck, remo, input_dir, info=info
                )  # , pipe=pipe)
        else:
            info = ""
            cloud_utils.s3_get_data(buck, remo, input_dir, info=info)  # , pipe=pipe)
    elif pipe == "dwi":
        if atlases is not None:
            for atlas in atlases:
                info = f"{atlas}"
                cloud_utils.s3_get_data(
                    buck, remo, input_dir, info=info
                )  # , pipe=pipe)
        else:
            info = ""
            cloud_utils.s3_get_data(buck, remo, input_dir, info=info)  # , pipe=pipe)

    # now /root/.m2g/input/mask_.... has all these edgelists:

    latlas = os.listdir(home + "/.m2g/input")

    # Calculate discrim and average and push it
    if isinstance(ptr, str):
        ptr = ptr == "True"
    if isinstance(disc, str):
        disc = disc == "True"

    for at in latlas:
        os.makedirs(f"{output_dir}/{at}", exist_ok=True)
        if disc:
            print(at)
            discr = discrim.discrim_runner(input_dir, at, ptr=False)
            discr_ptr = discrim.discrim_runner(input_dir, at, ptr=True)

            f = open(f"{output_dir}/Discrim_values.txt", "a")
            f.write(f"{at} Discriminability is : {discr}\n")
            f.write(f"{at} PTR Discriminability is : {discr_ptr}\n")
            f.close()

        # Create averaged/variance connectomes and save them
        # avgconnectome(input_dir, output_dir, at)

        # if push_location:
        #    print(f"Pushing to s3 at {push_location}.")
        #    push_buck, push_remo = cloud_utils.parse_path(push_location)
        #    cloud_utils.s3_push_data(
        #        push_buck,
        #        push_remo,
        #        output_dir,
        #        discrim=disc,
        #        atlas=at,
        #        creds=creds,
        #    )


if __name__ == "__main__":
    main()
