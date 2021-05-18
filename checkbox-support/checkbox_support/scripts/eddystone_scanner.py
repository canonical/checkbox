#!/usr/bin/env python3
# encoding: UTF-8
# Copyright (c) 2021 Canonical Ltd.
#
# Authors:
#     Sylvain Pineau <sylvain.pineau@canonical.com>
#     Paul Larson <paul.larson@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import time

from checkbox_support.vendor.beacontools import (
    BeaconScanner, EddystoneURLFrame)
from checkbox_support.interactive_cmd import InteractiveCommand


def init_bluetooth():
    # Power on the bluetooth controller
    with InteractiveCommand('bluetoothctl') as btctl:
        btctl.writeline('power on')
        time.sleep(3)
        btctl.writeline('scan on')
        time.sleep(3)
        btctl.writeline('exit')
        btctl.kill()


def beacon_scan(hci_device):
    TIMEOUT = 10

    beacon_mac = beacon_rssi = beacon_packet = ''

    def callback(bt_addr, rssi, packet, additional_info):
        nonlocal beacon_mac, beacon_rssi, beacon_packet
        beacon_mac, beacon_rssi, beacon_packet = bt_addr, rssi, packet

    scanner = BeaconScanner(
        callback,
        bt_device_id=hci_device,
        packet_filter=EddystoneURLFrame
    )

    scanner.start()
    start = time.time()
    while not beacon_packet and time.time() - start < TIMEOUT:
        time.sleep(1)
    scanner.stop()
    if beacon_packet:
        print('Eddystone beacon detected: URL: {} <mac: {}> '
              '<rssi: {}>'.format(beacon_packet.url, beacon_mac, beacon_rssi))
        return 0
    print('No EddyStone URL advertisement detected!')
    return 1


def main():
    init_bluetooth()

    parser = argparse.ArgumentParser(
        description="Track BLE advertised packets")
    parser.add_argument("-D", "--device", default='hci0',
                        help="Select the hciX device to use "
                             "(default hci0).")
    args = parser.parse_args()

    try:
        hci_device = int(args.device.replace('hci', ''))
    except ValueError:
        print('Bad device argument, defaulting to hci0')
        hci_device = 0

    # Newer bluetooth controllers and bluez versions allow extended commands
    # supported by newer versions of beacontools. But with older controllers,
    # especially when running on bionic, core18, bluez < 5.51, etc. they
    # only work correctly with legacy commands, and need an older version
    # of beacontools to work properly.
    # Try the newest one first, then the older one if that doesn't work
    rc = beacon_scan(hci_device)
    if rc:
        print('Trying again with older beacontools version...')
        global BeaconScanner, EddystoneURLFrame
        from checkbox_support.vendor.beacontools_2_0_2 import (
            BeaconScanner, EddystoneURLFrame)
        rc = beacon_scan(hci_device)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
