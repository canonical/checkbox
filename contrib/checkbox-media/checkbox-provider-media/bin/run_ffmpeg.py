#!/usr/bin/python3

import wget
import argparse
import os
import subprocess
import glob
from pathlib import Path
import sys
import re

RESOURCES_DIR = "/tmp/"


# get the base filename from a URL
def basename(url):
    return url.split("/")[-1]


def get_all_trace_contents(trace_dir):
    pattern = str(Path(trace_dir) / "libva.trace*")

    # Find all matching files
    matching_files = glob.glob(pattern)

    # Read all content into one string
    all_traces = ""

    for file_path in matching_files:
        try:
            with open(file_path, "r") as f:
                all_traces += "".join(f.readlines())
        except Exception as e:
            print(f"Could not read {file_path}: {e}")

    return all_traces


def has_profile_and_entrypoint(text, profile_val, entrypoint_val):
    profile_vals = profile_val.split(",")
    entrypoint_vals = entrypoint_val.split(",")

    found_profile = False
    found_entrypoint = False
    for profile in profile_vals:
        if f"profile = {profile}" in text:
            found_profile = True
            break

    for entrypoint in entrypoint_vals:
        if f"entrypoint = {entrypoint}" in text:
            found_entrypoint = True
            break

    return found_entrypoint and found_profile


def has_profile_and_entrypoint_old(text, profile_val, entrypoint_val):
    # These additions exist because Checkbox templating removes quotes
    # but parentheses can't be passed as an argument in bash without quotes.
    # So we add the quotes at the start and strip them here
    entrypoint_val = entrypoint_val.strip().strip('"').strip("'")
    profile_val = profile_val.strip().strip('"').strip("'")

    # Wrap values in () if they are just plain digits
    if not re.match(r"^\(.*\)$", profile_val):
        profile_val = f"({profile_val})"
    if not re.match(r"^\(.*\)$", entrypoint_val):
        entrypoint_val = f"({entrypoint_val})"

    profile_pattern = re.compile(rf"profile\s*=\s*{profile_val}")
    entrypoint_pattern = re.compile(rf"entrypoint\s*=\s*{entrypoint_val}")

    return bool(
        profile_pattern.search(text) and entrypoint_pattern.search(text)
    )


def download(url, download_dir):
    print(f"Downloading from: {url}")
    if not os.path.exists(RESOURCES_DIR + basename(url)):
        wget.download(url, out=download_dir)
    else:
        print("Using version already downloaded")


def ffmpeg_decode_command(video_filepath):
    return [
        "ffmpeg",
        "-hwaccel",
        "vaapi",
        "-vaapi_device",
        "/dev/dri/renderD128",
        "-hide_banner",
        "-loglevel",
        "info",
        "-i",
        video_filepath,
        "-t",
        "5",
        "-pix_fmt",
        "yuv420p",
        "-f",
        "rawvideo",
        "-vsync",
        "1",
        "-y",
        RESOURCES_DIR + "out.yuv",
    ]


def ffmpeg_encode_command(
    video_filepath, ffmpeg_output_codec, output_container
):
    return [
        "ffmpeg",
        "-hwaccel",
        "vaapi",
        "-vaapi_device",
        "/dev/dri/renderD128",
        "-hide_banner",
        "-loglevel",
        "info",
        "-i",
        video_filepath,
        "-rc_mode",
        "CQP",
        "-low_power",
        "1",
        "-c:v",
        f"{ffmpeg_output_codec}",
        "-vf",
        "format=nv12,hwupload",
        RESOURCES_DIR + f"output.{output_container}",
        "-y",
    ]


def run_ffmpeg(
    video_filepath,
    libva_profile,
    libva_entrypoint,
    operation,
    ffmpeg_output_codec=None,
    output_container=None,
):
    libva_trace_path = "%s/libva.trace" % RESOURCES_DIR
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = "/lib/x86_64-linux-gnu/"
    env["LIBVA_TRACE"] = libva_trace_path

    command = None
    if operation == "decode":
        command = ffmpeg_decode_command(video_filepath)
    elif operation == "encode":
        command = ffmpeg_encode_command(
            video_filepath, ffmpeg_output_codec, output_container
        )
    else:
        print("Failed: Operation not specified")

    print(" ".join(command))
    process = subprocess.run(command, capture_output=True, text=True, env=env)

    # Check if ffmpeg succeeded
    if process.returncode == 0:
        print("---- [PASS] FFMPEG command completed successfully")
    else:
        print("---- [FAIL] FFMPEG returned an error")

    hw_used = False
    trace = get_all_trace_contents(RESOURCES_DIR)
    if has_profile_and_entrypoint(trace, libva_profile, libva_entrypoint):
        hw_used = True
        print("---- [PASS] using HW %s" % operation)
    else:
        print("---- [FAIL] not using HW %s" % operation)
        print(process.stdout)
        print(process.stderr)

    if not hw_used or not process.returncode == 0:
        exit(1)

    # Clean up extra trace files and media output
    remove_wildcard_filename(RESOURCES_DIR, "libva.trace*")
    for extension in ["mp4", "mkv", "mpg", "yuv"]:
        if os.path.exists(f"output.{extension}"):
            os.remove(f"output.{extension}")


def remove_wildcard_filename(directory, file_string_wildcard):
    files = glob.glob(f"{directory}/{file_string_wildcard}")

    for file_path in files:
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Could not delete {file_path}: {e}", file=sys.stderr)


if __name__ == "__main__":
    # Just download resources to /tmp

    parser = argparse.ArgumentParser(
        description="Runs a media decode operation and checks for HW"
        " acceleration"
    )
    parser.add_argument(
        "--video_url", required=True, help="URL to the video to decode"
    )
    parser.add_argument(
        "--libva_entrypoint",
        required=True,
        help="libva entrypoint found in va/va.h (integer)",
    )
    parser.add_argument(
        "--libva_profile",
        required=True,
        help="Codec profile found in va/va.h (integer)",
    )
    parser.add_argument(
        "--ffmpeg_output_codec",
        required=False,
        help="(Encode only) The ffmpeg name for the codec you want to encode"
        " for (i.e. vp9_vaapi)",
    )
    parser.add_argument(
        "--output_container",
        required=False,
        help="(Encode only) The video container you want to use for encode"
        " output (i.e. mp4, mkv)",
    )
    parser.add_argument(
        "--decode", action="store_true", help="Run a decode operation"
    )
    parser.add_argument(
        "--encode", action="store_true", help="Run an encode operation"
    )
    args = parser.parse_args()

    if args.decode and args.encode:
        print(
            "Failed: Cannot have encode and decode mode enabled at the same"
            " time",
            file=sys.stderr,
        )
        exit(1)

    operation = None
    if args.decode:
        operation = "decode"
    elif args.encode:
        operation = "encode"
    else:
        print(
            "Failed: Must run this script with either --encode or --decode",
            file=sys.stderr,
        )
        exit(1)

    download(args.video_url, RESOURCES_DIR)

    filename = args.video_url.split("/")[-1]
    filepath = RESOURCES_DIR + filename
    if not os.path.exists(filepath):
        print(
            f"Video file {filename} did not download correctly",
            file=sys.stderr,
        )
        exit(1)

    if operation == "decode":
        run_ffmpeg(
            filepath, args.libva_profile, args.libva_entrypoint, operation
        )
    else:
        if args.ffmpeg_output_codec is None or args.output_container is None:
            print(
                "Failed: The --encode flag requires --ffmpeg_output_codec and"
                " --output_container",
                file=sys.stderr,
            )
            exit(1)

        run_ffmpeg(
            filepath,
            args.libva_profile,
            args.libva_entrypoint,
            operation,
            ffmpeg_output_codec=args.ffmpeg_output_codec,
            output_container=args.output_container,
        )
