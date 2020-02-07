#!/usr/bin/env python3
# Copyright 2015-2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Jonathan Cave <jonathan.cave@canonical.com>

"""
Collect information about all sysfs attributes related to TPM.

This program traverses all the TPM device nodes found in /sys/class/tpm/.
Each present device is subsequently inspected by reading all readable files
in /sys/class/tpm/*/device/* and presenting the data present there as
subsequent RFC822 records. There is one record per TPM chip. In order to
differentiate each chip, each record contains the field x-sysfs-device-name
that stores the full sysfs directory name of the chip.

@EPILOG@

Unreadable files (typically due to permissions) are silently skipped.
"""

import os


def main():
    # This is found on 4.2 kernels
    sysfs_root_tpm = '/sys/class/tpm/'
    # This is found on 3.19 kernels
    sysfs_root_misc = '/sys/class/misc/'
    if os.path.isdir(sysfs_root_tpm):
        sysfs_root = sysfs_root_tpm
    elif os.path.isdir(sysfs_root_misc):
        sysfs_root = sysfs_root_misc
    else:
        return
    for tpm_id in sorted(os.listdir(sysfs_root)):
        if sysfs_root == sysfs_root_misc and not tpm_id.startswith('tpm'):
            continue
        print("x-sysfs-device-name: {}".format(tpm_id))
        tpm_dirname = os.path.join(sysfs_root, tpm_id, 'device')
        for tpm_attr in sorted(os.listdir(tpm_dirname)):
            tpm_filename = os.path.join(tpm_dirname, tpm_attr)
            if not os.path.isfile(tpm_filename):
                continue
            if not os.access(tpm_filename, os.R_OK):
                continue
            with open(tpm_filename, 'rt', encoding='utf-8') as stream:
                tpm_data = stream.read()
            tpm_data = tpm_data.rstrip()
            if '\n' in tpm_data:
                print("{}:".format(tpm_attr))
                for tpm_data_chunk in tpm_data.splitlines():
                    print(" {}".format(tpm_data_chunk))
            else:
                print("{}: {}".format(tpm_attr, tpm_data))
        print()


if __name__ == "__main__":
    main()
