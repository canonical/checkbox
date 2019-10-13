# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Jonathan Cave <jonathan.cave@canonical.com>

import io
import os
import re
import subprocess as sp
import yaml

from checkbox_support.parsers.kernel_cmdline import parse_kernel_cmdline
from checkbox_support.snap_utils.snapd import Snapd


def get_kernel_snap():
    snap = None
    assertion_stream = Snapd().get_assertions('model')
    count = int(assertion_stream.headers['X-Ubuntu-Assertions-Count'])
    if count > 0:
        for line in io.StringIO(assertion_stream.text):
            if line.count(':') == 1:
                key, val = [x.strip() for x in line.split(':')]
                if key == 'kernel':
                    if '=' in val:
                        snap, _ = [x.strip() for x in val.split('=')]
                    else:
                        snap = val
                    break
    return snap


def get_gadget_snap():
    snap = None
    assertion_stream = Snapd().get_assertions('model')
    count = int(assertion_stream.headers['X-Ubuntu-Assertions-Count'])
    if count > 0:
        for line in io.StringIO(assertion_stream.text):
            if line.count(':') == 1:
                key, val = [x.strip() for x in line.split(':')]
                if key == 'gadget':
                    if '=' in val:
                        snap, _ = [x.strip() for x in val.split('=')]
                    else:
                        snap = val
                    break
    return snap


def get_bootloader():
    bootloader = None
    gadget_yaml = '/snap/{}/current/meta/gadget.yaml'.format(get_gadget_snap())
    with open(gadget_yaml) as f:
        data = yaml.load(f)
        for k in data['volumes'].keys():
            bootloader = data['volumes'][k]['bootloader']
    return bootloader


def get_lk_bootimg_path():
    with open('/proc/cmdline', 'r') as f:
        cmdline = f.readline()
    result = parse_kernel_cmdline(cmdline)
    try:
        snap_kernel = result.params['snap_kernel']
        # get the bootimg matrix using `lk-boot-env -r`
        snap_boot_selection = sp.run(
            ['lk-boot-env', '-r', '/dev/disk/by-partlabel/snapbootsel'],
            check=True, stdout=sp.PIPE).stdout.decode()
        match = re.search(
            'bootimg_matrix\s+\[(.*?)\]\[{}\]'.format(snap_kernel),
            snap_boot_selection, re.M)
        if match:
            path = os.path.join('/dev/disk/by-partlabel', match.group(1))
    except (KeyError, AttributeError, FileNotFoundError):
        path = 'unknown'
    return path
