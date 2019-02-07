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

NM_CON_DIR = '/etc/NetworkManager/system-connections'
SAVE_DIR = os.path.join(os.path.expandvars(
    '$PLAINBOX_SESSION_SHARE'), 'stored-system-connections')


def get_nm_connections():
    c = []
    cmd = 'nmcli -t -f TYPE,NAME c'
    output = sp.check_output(cmd, shell=True)
    for line in output.decode(sys.stdout.encoding).splitlines():
        con_type, name = line.strip().split(':')
        if con_type == '802-11-wireless':
            c.append(name)
    return c


def reload_nm_connections():
    cmd = 'nmcli c reload'
    sp.check_call(cmd, shell=True)


def save_connections(con_list):
    if len(con_list) == 0:
        print('No stored 802.11 connections to save')
        return
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
    for c in con_list:
        print('Save connection {}'.format(c))
        c_loc = os.path.join(NM_CON_DIR, c)
        if not os.path.exists(c_loc):
            print('  No stored connection fount at {}'.format(c_loc))
            continue
        print('  Found file {}'.format(c_loc))
        save_f = shutil.copy(c_loc, SAVE_DIR)
        print('  Saved copy at {}'.format(save_f))


def restore_connections():
    saved_list = [f for f in os.listdir(
        SAVE_DIR) if os.path.isfile(os.path.join(SAVE_DIR, f))]
    if len(saved_list) == 0:
        print('No stored 802.11 connections found')
        return
    for f in saved_list:
        save_f = os.path.join(SAVE_DIR, f)
        print('Restore connection {}'.format(save_f))
        restore_f = shutil.copy(save_f, NM_CON_DIR)
        print('  Restored file at {}'.format(restore_f))
        os.remove(save_f)
        print('  Removed copy from {}'.format(save_f))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('ERROR: please specify save or restore')
    action = sys.argv[1]

    if action == 'save':
        save_connections(get_nm_connections())
    elif action == 'restore':
        restore_connections()
        reload_nm_connections()
    else:
        raise SystemExit('ERROR: unrecognised action')
