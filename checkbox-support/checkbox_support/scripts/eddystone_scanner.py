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

import sys
import time
import argparse

from checkbox_support.vendor.beacontools import (
    BeaconScanner,
    EddystoneURLFrame,
)
from checkbox_support.helpers.timeout import timeout
from checkbox_support.interactive_cmd import InteractiveCommand


def init_bluetooth():
    # Power on the bluetooth controller
    with InteractiveCommand("bluetoothctl") as btctl:
        btctl.writeline("power on")
        time.sleep(3)
        btctl.writeline("scan on")
        time.sleep(3)
        btctl.writeline("exit")
        btctl.kill()


def beacon_scan(hci_device, debug=False):
    TIMEOUT = 10
    report_type = None
    beacon_mac = beacon_rssi = beacon_packet = ""

    def callback(sub_event, bt_addr, rssi, packet, additional_info):
        nonlocal beacon_mac, beacon_rssi, beacon_packet, report_type
        report_type, beacon_mac, beacon_rssi, beacon_packet = (
            sub_event,
            bt_addr,
            rssi,
            packet,
        )

    scanner = BeaconScanner(
        callback,
        bt_device_id=hci_device,
        packet_filter=EddystoneURLFrame,
        debug=debug,
    )

    scanner.start()
    start = time.time()
    while not beacon_packet and time.time() - start < TIMEOUT:
        time.sleep(0.5)
    scanner.stop()
    if beacon_packet:
        print(
            "Eddystone beacon detected: [Adv Report Type: {}({})] "
            "URL: {} <mac: {}> <rssi: {}>".format(
                report_type.name,
                report_type.value,
                beacon_packet.url,
                beacon_mac,
                beacon_rssi,
            )
        )
        return 0
    print("No EddyStone URL advertisement detected!")
    return 1


@timeout(60 * 10)  # 10 minutes timeout
def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    init_bluetooth()

    parser = argparse.ArgumentParser(
        description="Track BLE advertised packets"
    )
    parser.add_argument(
        "-D",
        "--device",
        default="hci0",
        help="Select the hciX device to use " "(default hci0).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
    )
    args = parser.parse_args(argv)

    try:
        hci_device = int(args.device.replace("hci", ""))
    except ValueError:
        print("Bad device argument, defaulting to hci0")
        hci_device = 0

    return beacon_scan(hci_device, args.debug)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
