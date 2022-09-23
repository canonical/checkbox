# Copyright 2019-2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Jonathan Cave <jonathan.cave@canonical.com>

import os
import re
import subprocess as sp
import yaml

import distro

from checkbox_support.parsers.kernel_cmdline import parse_kernel_cmdline
from checkbox_support.snap_utils.asserts import decode
from checkbox_support.snap_utils.asserts import model_to_resource
from checkbox_support.snap_utils.snapd import Snapd


def on_ubuntucore():
    return 'ubuntu-core' in distro.id()


def get_series():
    return distro.version()


def in_classic_snap():
    snap = os.getenv("SNAP")
    if snap:
        with open(os.path.join(snap, 'meta/snap.yaml')) as f:
            for line in f.readlines():
                if line == "confinement: classic\n":
                    return True
    return False


def get_kernel_snap():
    model = next(decode(Snapd().get_assertions('model')), None)
    if model:
        # convert to resource to handle presence of track info
        resource = model_to_resource(model)
        return resource.get('kernel')
    return None


def get_gadget_snap():
    model = next(decode(Snapd().get_assertions('model')), None)
    if model:
        # convert to resource to handle presence of track info
        resource = model_to_resource(model)
        return resource.get('gadget')
    return None


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
