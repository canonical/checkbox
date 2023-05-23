#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Maciej Kisielewski <maciej.kisielewski@canonical.com>
"""
This program checks if the host can connect to a Zapper using Bluetooth.
"""
import sys
import time

from contextlib import contextmanager

import bluetooth

from checkbox_support.scripts.zapper_proxy import zapper_run  # noqa: E402


@contextmanager
def zapper_as_a_speaker(host):
    """Ensure that the service is turned off after using it."""
    addr = zapper_run(host, "bluetooth_start", "a2dp")
    try:
        yield addr
    finally:
        zapper_run(host, "bluetooth_stop")


def main():
    """Entry point to the test."""
    if len(sys.argv) != 2:
        raise SystemExit("Usage: {} ZAPPER_HOST".format(sys.argv[0]))
    print("Asking Zapper to become a Bluetooth speaker")
    with zapper_as_a_speaker(sys.argv[1]) as zapper_addr:
        print("Zapper Bluetooth address is {}".format(zapper_addr))
        retry_count = 5
        for i in range(1, retry_count + 1):
            print("Discovering Bluetooth devices (try {}/{})".format(
                i, retry_count))
            devices = bluetooth.discover_devices()
            print("Devices found: {}".format(devices))
            if zapper_addr in devices:
                break
            print("Zapper not found in the device list... Retrying")
        else:
            raise SystemExit("Zapper not found")

        for i in range(1, retry_count + 1):
            print("Trying to connect to Zapper (try {}/{})".format(
                i, retry_count))
            socket = bluetooth.BluetoothSocket(bluetooth.L2CAP)
            try:
                socket.connect((zapper_addr, 25))  # 25 - A2DP port
                # the sleep below is there to be able to see the icon change
                # when observing the test with human eyes
                # change it to a longer delay to enable easy debugging
                time.sleep(1)
                socket.close()
                break
            except bluetooth.btcommon.BluetoothError as exc:
                print("Failed to connect. {}".format(exc))
                time.sleep(10)
        else:
            raise SystemExit("Failed to connect to Zapper via BT")


if __name__ == "__main__":
    raise SystemExit(main())
