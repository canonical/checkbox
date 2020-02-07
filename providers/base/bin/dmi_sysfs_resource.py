#!/usr/bin/env python3
# Copyright 2015-2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Jonathan Cave <jonathan.cave@canonical.com>

"""Collect information about all sysfs attributes related to DMI."""

import os

"""
Collect information about all sysfs attributes related to DMI.

This program reads all the readable files in /sys/class/dmi/id/ and
presents them a single RFC822 record.

@EPILOG@

Unreadable files (typically due to permissions) are silently skipped.
Please run this program as root if you wish to access various serial
numbers.
"""


def main():
    sysfs_root = '/sys/class/dmi/id/'
    if not os.path.isdir(sysfs_root):
        return
    for dmi_attr in sorted(os.listdir(sysfs_root)):
        dmi_filename = os.path.join(sysfs_root, dmi_attr)
        if not os.path.isfile(dmi_filename):
            continue
        if not os.access(dmi_filename, os.R_OK):
            continue
        with open(dmi_filename, 'rt', encoding='utf-8') as stream:
            dmi_data = stream.read().strip()
        print("{}: {}".format(dmi_attr, dmi_data))


if __name__ == "__main__":
    main()
