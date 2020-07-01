#!/usr/bin/env python3
# Copyright 2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>

import io
import sys

from checkbox_support.snap_utils.snapd import Snapd


class SnapInfo():

    def __init__(self):
        self.kernel = None
        self.gadget = None
        data = Snapd().list()
        for snap in data:
            if snap['type'] == 'kernel':
                self.kernel = snap
            if snap['type'] == 'gadget':
                self.gadget = snap

    def test_kernel_publisher(self):
        if not self.kernel:
            raise SystemExit('ERROR: failed to get kernel snap info')
        if self.kernel['publisher']['id'] != 'canonical':
            raise SystemExit('ERROR: kernel snap publisher must be canonical')
        if self.kernel['publisher']['validation'] != 'verified':
            raise SystemExit('ERROR: kernel snap publisher must be verified')
        print('PASS')

    def test_kernel_tracking(self):
        if not self.kernel:
            raise SystemExit('ERROR: failed to get kernel snap info')
        if not self.kernel.get('tracking-channel'):
            raise SystemExit('ERROR: kernel must be tracking a store channel')
        if 'stable' not in self.kernel['tracking-channel']:
            raise SystemExit('ERROR: kernel must be on a stable channel')
        print('PASS')

    def test_gadget_publisher(self):
        if not self.gadget:
            raise SystemExit('ERROR: failed to get gadget snap info')
        if self.gadget['publisher']['id'] != 'canonical':
            raise SystemExit('ERROR: gadget snap publisher must be canonical')
        if self.gadget['publisher']['validation'] != 'verified':
            raise SystemExit('ERROR: gadget snap publisher must be verified')
        print('PASS')

    def test_gadget_tracking(self):
        if not self.gadget:
            raise SystemExit('ERROR: failed to get gadget snap info')
        if not self.gadget.get('tracking-channel'):
            raise SystemExit('ERROR: gadget must be tracking a store channel')
        if 'stable' not in self.gadget['tracking-channel']:
            raise SystemExit('ERROR: gadget must be on a stable channel')
        print('PASS')


class ModelInfo():

    def __init__(self):
        self.authority = None
        self.brand = None
        for line in io.StringIO(Snapd().get_assertions('model').text):
            if ':' in line:
                entry = line.split(':', maxsplit=1)
                if entry[0] == 'authority-id':
                    self.authority = entry[1].strip()
                if entry[0] == 'brand-id':
                    self.brand = entry[1].strip()

    def test_model_authority(self):
        if not self.authority:
            raise SystemExit('ERROR: failed to get model authority info')
        if self.authority != 'canonical':
            raise SystemExit('ERROR: model authority must be canonical')
        print('PASS')

    def test_model_brand(self):
        if not self.brand:
            raise SystemExit('ERROR: failed to get model brand info')
        if self.brand != 'canonical':
            raise SystemExit('ERROR: model brand must be canonical')
        print('PASS')


def main():
    if len(sys.argv) != 2:
        raise SystemExit('USAGE: ubuntucore_image_checks.py [action]')
    action = sys.argv[1]

    snapinfo = SnapInfo()
    modelinfo = ModelInfo()

    if action == 'kernel-publisher':
        snapinfo.test_kernel_publisher()
    elif action == 'kernel-tracking':
        snapinfo.test_kernel_tracking()
    elif action == 'gadget-publisher':
        snapinfo.test_gadget_publisher()
    elif action == 'gadget-tracking':
        snapinfo.test_gadget_tracking()
    elif action == 'model-authority':
        modelinfo.test_model_authority()
    elif action == 'model-brand':
        modelinfo.test_model_authority()
    else:
        raise SystemExit('ERROR: unrecognised action')


if __name__ == '__main__':
    main()
