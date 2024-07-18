# Copyright 2022 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
#   Zhongning Li <zhongning.li@canonical.com>

import argparse
from os.path import exists
from checkbox_support.snap_utils.system import on_ubuntucore
from subprocess import DEVNULL, run


def get_type() -> str:
    """
    Return the type of image.
    """
    return "core" if on_ubuntucore() else "classic"


def has_desktop_environment(
    desktop_packages=["ubuntu-desktop", "ubuntu-desktop-minimal"]
) -> bool:
    """
    Returns whether there's a desktop environment
    """
    if on_ubuntucore():
        # ubuntu core doesn't have a desktop env by default
        return False

    for package in desktop_packages:
        if (
            run(
                ["dpkg", "-l", package], stdout=DEVNULL, stderr=DEVNULL
            ).returncode
            == 0
        ):
            return True

    return False


def get_source() -> str:
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
