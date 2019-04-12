# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Jonathan Cave <jonathan.cave@canonical.com>

import io
import yaml

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
