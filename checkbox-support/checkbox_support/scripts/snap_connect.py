#!/usr/bin/env python3
# Copyright 2017 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>

"""
This program connects snap plugs and lists connections between snaps.

The syntax of program parameters is A:B:C, where :

    A - plug to be connected
    B - target snap (snap the plug will connect to)
    C - target slot (slot to connect to)

    Note that originating snap is implied. $SNAP_NAME is used.

Example:
    $ sudo ./snap_connect.py udisks2:udisks2:service

running
    $ sudo ./snap_connect.py A:B:C
is equivalent to:
    $ snap connect $SNAP_NAME:A B:C

    Note that the program needs sudo if asked to connect plugs.
"""

import argparse
import logging
import os
from collections import namedtuple

from checkbox_support.snap_utils.snapd import Snapd
import requests

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'connections', nargs='+', default=[],
        metavar='plug:target_snap:target_slot')
    args = parser.parse_args()

    for conn in [spec.split(':') for spec in args.connections]:
        if len(conn) != 3:
            raise SystemExit("Bad connection description")
        assert os.environ['SNAP_NAME']
        snap = os.environ['SNAP_NAME']
        existing_connections = get_connections()
        new_connection = Connection(
            target_snap=conn[1], target_slot=conn[2],
            plug_snap=snap, plug_plug=conn[0])
        if new_connection not in existing_connections:
            try:
                # increase timeout to ensure slow devices (caracalla) can
                # complete their snap connect jobs
                Snapd(task_timeout=60).connect(*new_connection)
            except requests.HTTPError as exc:
                logging.warning("Failed to connect %s to %s. %s" % (
                    conn[0], conn[1], exc))


if __name__ == '__main__':
    main()
