#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
#
# Save/Restore NetworkManager wifi connections

import os
import shutil
import subprocess as sp
import sys
import glob

from packaging import version as version_parser


NM_CON_DIR = "/etc/NetworkManager/system-connections"
SAVE_DIR = os.path.join(
    os.path.expandvars("$PLAINBOX_SESSION_SHARE"), "stored-system-connections"
)


# versions of NM in cosmic or later allow you to request the keyfile name
# in `nmcli -t -f <FIELDS> c` output used below
def legacy_nmcli():
    cmd = "nmcli -v"
    output = sp.check_output(cmd, shell=True)
    version = version_parser.parse(output.strip().split()[-1].decode())
    # check if using an earlier nmcli version with different api
    # nmcli in cosmic is 1.12.4, bionic is 1.10
    return version < version_parser.parse("1.12.0")


# Creation of keyfile names can be found in:
# https://gitlab.freedesktop.org/NetworkManager/NetworkManager/blob/master/libnm-core/nm-keyfile.c#L4046
# Old format is to replace path separators with '*', in versions that use
# the new format we can just use the filename supplied by nmcli
def get_nm_keyfiles():
    filenames = []
    if legacy_nmcli():
        cmd = "nmcli -t -f TYPE,NAME c"
        output = sp.check_output(cmd, shell=True)
        for line in output.decode(sys.stdout.encoding).splitlines():
            con_type, name = line.strip().split(":")
            if con_type == "802-11-wireless":
                filename = name.replace("/", "*")
                filenames.append(os.path.join(NM_CON_DIR, filename))
    else:
        cmd = "nmcli -t -f TYPE,FILENAME c"
        output = sp.check_output(cmd, shell=True)
        for line in output.decode(sys.stdout.encoding).splitlines():
            con_type, filename = line.strip().split(":")
            if con_type == "802-11-wireless":
                filenames.append(filename)
    return filenames


def reload_nm_connections():
    cmd = "nmcli c reload"
    sp.check_call(cmd, shell=True)


def save_connections(keyfile_list):
    os.makedirs(SAVE_DIR, exist_ok=True)

    if not keyfile_list:
        print("No stored 802.11 connections to save")
        return

    for f in keyfile_list:
        print("Save connection {}".format(f))

        if not os.path.exists(f):
            print("  No stored connection found at {}".format(f))
            continue

        print("  Found file {}".format(f))

        basedir = os.path.dirname(f)
        backup_loc = os.path.join(SAVE_DIR, *basedir.split("/"))

        os.makedirs(backup_loc, exist_ok=True)
        save_f = shutil.copy(f, backup_loc)
        print("  Saved copy at {}".format(save_f))


def restore_connections():
    saved_list = glob.glob(
        "{}/**/*.nmconnection".format(SAVE_DIR), recursive=True
    )
    if len(saved_list) == 0:
        print("No stored 802.11 connections found")
        return
    for f in saved_list:
        save_f = f[len(SAVE_DIR) :]
        print("Restore connection {}".format(save_f))
        shutil.move(f, save_f)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("ERROR: please specify save or restore")
    action = sys.argv[1]

    if action == "save":
        save_connections(get_nm_keyfiles())
    elif action == "restore":
        restore_connections()
        reload_nm_connections()
    else:
        raise SystemExit("ERROR: unrecognised action")
