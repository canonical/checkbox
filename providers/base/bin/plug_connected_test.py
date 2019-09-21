#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Jonathan Cave <jonathan.cave@canonical.com>

import sys

from checkbox_support.snap_utils.snapd import Snapd


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit('Usage: plug_connected_test.py SNAP PLUG')
    snap_name = sys.argv[1]
    plug_name = sys.argv[2]

    data = Snapd().interfaces()
    for plug in data.get('plugs', []):
        if plug['snap'] == snap_name and plug['plug'] == plug_name:
            if 'connections' in plug:
                print('{}:{} is connected to:'.format(
                    plug['snap'], plug['plug']))
                for slot in plug['connections']:
                    print('{}:{}'.format(slot['snap'], slot['slot']))
            else:
                raise SystemExit('ERROR: {}:{} is not connected'.format(
                    plug['snap'], plug['plug']))
