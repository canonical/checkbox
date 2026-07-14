#!/usr/bin/env python3
import subprocess
import argparse
import shlex
import os
import json
import logging

RESOLUTIONS = {
    "2160p": {"width": 3840, "height": 2160},
    "1440p": {"width": 2560, "height": 1440},
    "1080p": {"width": 1920, "height": 1080},
    "720p": {"width": 1280, "height": 720},
    "480p": {"width": 640, "height": 480},
}

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)


def run_cmd(command):
    ret = subprocess.run(
        shlex.split(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
    )
    return ret


def read_json_file(path):
    """Read the content of a JSON file"""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        logging.error("Fail to load the '{}' file".format(f))
        raise


def get_camera_list(args):
    """Print connected cameras and their supported resolutions"""

    path = os.path.expandvars(
        "$PLAINBOX_PROVIDER_DATA/camera/supported_cameras.json"
    )
    supported_cameras = read_json_file(path)

    cameras = args.cameras.split()
    for c in cameras:
        try:
            index, name = c.split(":", 1)
        except ValueError:
            logging.error("Invalid input format, expected index:name")
            return 1

        if name not in supported_cameras:
            logging.error("Cannot find resolutions for {}".format(name))
            return 1

        for rate in supported_cameras[name]:
            print("name: {}".format(name))
            print("camera: {}".format(index))
            print("resolution: {}".format(rate))
            print("width: {}".format(RESOLUTIONS[rate]["width"]))
            print("height: {}".format(RESOLUTIONS[rate]["height"]))
            print()


def main():
    commands = {
        "camera-list": get_camera_list,
    }
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "subcommand", help=("subcommand to run"), choices=commands.keys()
    )
    parser.add_argument(
        "-c", "--cameras", type=str, help="connected cameras and index"
    )
    args = parser.parse_args()

    return commands[args.subcommand](args)


if __name__ == "__main__":
    raise SystemExit(main())
