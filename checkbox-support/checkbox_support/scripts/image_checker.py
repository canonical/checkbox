# Copyright 2022 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>

import argparse
from os.path import exists
from checkbox_support.snap_utils.system import on_ubuntucore
import shutil
import subprocess
from subprocess import PIPE
from typing import Literal


def get_type() -> Literal["core", "classic"]:
    """
    Return the type of image.
    """
    return "core" if on_ubuntucore() else "classic"


def has_desktop_environment() -> bool:
    if not shutil.which("dpkg"):
        # core and server image doesn't have dpkg
        return False

    # if we found any of these packages, we are on desktop
    if (
        subprocess.run(
            ["dpkg", "-l", "ubuntu-desktop"], stdout=PIPE, stderr=PIPE
        ).returncode
        == 0
        or subprocess.run(
            ["dpkg", "-l", "ubuntu-desktop-minimal"], stdout=PIPE, stderr=PIPE
        ).returncode
        == 0
    ):
        return True

    return False


def get_source() -> Literal["oem", "stock", "unknown"]:
    """
    Return the source of image.
    """
    is_oem_source = False

    if get_type() == "core":
        try:
            with open("/run/mnt/ubuntu-seed/.disk/info") as file:
                lines = file.readlines()
                # Only one timestamp such as 20221021.4 if it's stock image
                # There're three lines in info file if it's oem image
                is_oem_source = len(lines) > 1
        except FileNotFoundError as e:
            print(e)
            return "unknown"
    else:
        is_oem_source = exists("/var/lib/ubuntu_dist_channel")

    return "oem" if is_oem_source else "stock"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--type", action="store_true")
    parser.add_argument("-s", "--source", action="store_true")
    parser.add_argument("-d", "--detect_desktop", action="store_true")
    args = parser.parse_args()

    if args.type:
        print("type: {}".format(get_type()))
    if args.source:
        print("source: {}".format(get_source()))
    if args.detect_desktop:
        print("Has desktop environment? {}".format(has_desktop_environment()))


if __name__ == "__main__":
    raise SystemExit(main())
