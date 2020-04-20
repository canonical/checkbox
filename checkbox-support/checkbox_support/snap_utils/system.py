# Copyright 2019-2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Jonathan Cave <jonathan.cave@canonical.com>

import io
import os
import re
import subprocess as sp
import yaml

import distro

from checkbox_support.parsers.kernel_cmdline import parse_kernel_cmdline
from checkbox_support.snap_utils.snapd import Snapd


def on_ubuntucore():
    return 'ubuntu-core' in distro.id()


def get_series():
    return distro.version()


def in_classic_snap():
    snap = os.getenv("SNAP")
    if snap:
        with open(os.path.join(snap, 'meta/snap.yaml')) as f:
            for l in f.readlines():
                if l == "confinement: classic\n":
                    return False
        return True
    return False


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
            r'bootimg_matrix\s+\[(.*?)\]\[{}\]'.format(snap_kernel),
            snap_boot_selection, re.M)
        if match:
            path = os.path.join('/dev/disk/by-partlabel', match.group(1))
    except (KeyError, AttributeError, FileNotFoundError):
        path = 'unknown'
    return path


def add_hostfs_prefix(path):
    if on_ubuntucore():
        if os.path.isabs(path):
            path = path.split(os.path.sep, 1)[1]
        return os.path.join(os.path.sep, 'var', 'lib', 'snapd', 'hostfs', path)
    return path
