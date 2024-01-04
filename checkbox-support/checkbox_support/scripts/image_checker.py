#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
# Originally copied from https://git.launchpad.net/~checkbox-dev/
# checkbox-iiotg/+git/checkbox-provider-intliotg/tree/bin/image_checker.py

import argparse
from os.path import exists
from checkbox_support.snap_utils.system import on_ubuntucore


def get_type():
    """
    Return the type of image.
    """
    return "core" if on_ubuntucore() else "classic"


def get_source():
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
                is_oem_source = (len(lines) > 1)
        except FileNotFoundError as e:
            print(e)
            return 'unknown'
    else:
        is_oem_source = exists("/var/lib/ubuntu_dist_channel")

    return 'oem' if is_oem_source else 'stock'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--get_type', action='store_true')
    parser.add_argument('-s', '--get_source', action='store_true')
    args = parser.parse_args()

    if args.get_type:
        print("type: {}".format(get_type()))
    if args.get_source:
        print("source: {}".format(get_source()))


if __name__ == "__main__":
    raise SystemExit(main())
