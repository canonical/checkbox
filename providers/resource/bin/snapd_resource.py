#!/usr/bin/env python3
# Copyright 2017 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Jonathan Cave <jonathan.cave@canonical.com>

import argparse
import io
import os
import string
import sys

from checkbox_support.snap_utils.snapd import Snapd
from checkbox_support.snap_utils.system import get_kernel_snap

from collections import namedtuple


def slugify(_string):
    """Transform string to one that can be used as the key in a resource job"""
    valid_chars = frozenset(
        "_{}{}".format(string.ascii_letters, string.digits))
    return ''.join(c if c in valid_chars else '_' for c in _string)


def http_to_resource(assertion_stream):
    """ Super naive Assertion parser

    No attempt to handle assertions with a body. Discards signatures based
    on lack of colon characters. Update: need to be less naive about
    gadget and kernel names on UC18
    """
    count = int(assertion_stream.headers['X-Ubuntu-Assertions-Count'])
    if count > 0:
        for line in io.StringIO(assertion_stream.text):
            if line.strip() == "":
                print()
            if line.count(':') == 1:
                key, val = [x.strip() for x in line.split(':')]
                if key in ('gadget', 'kernel'):
                    if '=' in val:
                        snap, track = [x.strip() for x in val.split('=')]
                        print('{}: {}'.format(key, snap))
                        print('{}_track: {}'.format(key, track))
                        continue
                print(line.strip())
    return count


class ModelAssertion():

    def invoked(self):
        count = http_to_resource(Snapd().get_assertions('model'))
        if count == 0:
            # Print a dummy assertion - not nice but really trick to use
            # plainbox resources without some defualt value
            print('type: model')
            print('authority-id: None')
            print('model: None')
            print()


class SerialAssertion():

    def invoked(self):
        count = http_to_resource(Snapd().get_assertions('serial'))
        if count == 0:
            # Print a dummy assertion - not nice but really trick to use
            # plainbox resources without some defualt value
            print('type: serial')
            print('authority-id: None')
            print('serial: None')
            print()


class Assertions():

    def invoked(self):
        actions = {
            'model': ModelAssertion,
            'serial': SerialAssertion,
        }
        parser = argparse.ArgumentParser()
        parser.add_argument('action', type=str, help="The action to test",
                            choices=actions)
        args = parser.parse_args(sys.argv[2:3])
        actions[args.action]().invoked()


class Snaps():

    def invoked(self):
        data = Snapd().list()
        for snap in data:
            def print_field(key):
                try:
                    val = snap[key]
                except KeyError:
                    val = ""
                if val != "":
                    print("{}: {}".format(key, val))
            #  Whitelist of information that is of interest
            keys = ['name', 'type', 'channel', 'version', 'revision',
                    'developer', 'install-date', 'confinement', 'devmode',
                    'status']
            for f in keys:
                print_field(f)
            print()


class Endpoints():

    def invoked(self):
        data = Snapd().interfaces()

        if 'plugs' in data:
            for plug in data['plugs']:
                def print_field(key):
                    val = plug[key]
                    if val != '':
                        print('{}: {}'.format(key, val))
                keys = ['snap', 'interface']
                for f in keys:
                    print_field(f)
                print('type: plug')
                print('name: {}'.format(plug['plug']))
                if 'attrs' in plug:
                    for attr, val in plug['attrs'].items():
                        print('attr_{}: {}'.format(slugify(attr), val))
                print()

        if 'slots' in data:
            for slot in data['slots']:
                def print_field(key):
                    val = slot[key]
                    if val != '':
                        print('{}: {}'.format(key, val))
                keys = ['snap', 'interface']
                for f in keys:
                    print_field(f)
                print('type: slot')
                print('name: {}'.format(slot['slot']))
                if 'attrs' in slot:
                    for attr, val in slot['attrs'].items():
                        print('attr_{}: {}'.format(slugify(attr), val))
                print()


Connection = namedtuple(
    'Connection',
    ['target_snap', 'target_slot', 'plug_snap', 'plug_plug'])


def get_connections():
    data = Snapd().interfaces()
    connections = []
    if 'plugs' in data:
        for plug in data['plugs']:
            if 'connections' in plug:
                for con in plug['connections']:
                    connections.append(Connection(
                        con['snap'], con['slot'],
                        plug['snap'], plug['plug']))
    return connections


class Connections():

    def invoked(self):
        for conn in get_connections():
            print('slot: {}:{}'.format(conn.target_snap, conn.target_slot))
            print('plug: {}:{}'.format(conn.plug_snap, conn.plug_plug))
            print()


class Interfaces():

    def invoked(self):
        actions = {
            'endpoints': Endpoints,
            'connections': Connections
        }
        parser = argparse.ArgumentParser()
        parser.add_argument('action', type=str, help="The action to test",
                            choices=actions)
        args = parser.parse_args(sys.argv[2:3])
        actions[args.action]().invoked()


class Features():

    def invoked(self):
        self._detect_kernel_extraction()
        print()

    def _detect_kernel_extraction(self):
        '''
        Detect if the kernel extraction feature of snapd is enabled.

        This feature is typically enabled when the device is using full disk
        encryption as it ensures that the kernel.img is available to the
        bootloader prior to decrypting the writable partition.
        '''
        snap = get_kernel_snap()
        if snap is not None:
            feature_f = '/snap/{}/current/meta/force-kernel-extraction'.format(
                snap)
            print('force_kernel_extraction: {}'.format(
                os.path.exists(feature_f)))


class SnapdResource():

    def main(self):
        actions = {
            'assertions': Assertions,
            'snaps': Snaps,
            'interfaces': Interfaces,
            'features': Features
        }
        parser = argparse.ArgumentParser()
        parser.add_argument('action', type=str, help="The action to test",
                            choices=actions)
        args = parser.parse_args(sys.argv[1:2])
        actions[args.action]().invoked()


if __name__ == '__main__':
    SnapdResource().main()
