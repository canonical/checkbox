#!/usr/bin/env python3
# encoding: UTF-8
# Copyright (c) 2018 Canonical Ltd.
#
# Authors:
#     Sylvain Pineau <sylvain.pineau@canonical.com>
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
import asyncio
import logging
import sys
import time

from checkbox_support.interactive_cmd import InteractiveCommand
from checkbox_support.vendor.aioblescan import create_bt_socket
from checkbox_support.vendor.aioblescan import BLEScanRequester
from checkbox_support.vendor.aioblescan import HCI_Cmd_LE_Advertise
from checkbox_support.vendor.aioblescan import HCI_Event
from checkbox_support.vendor.aioblescan.eddystone import EddyStone


def main():
    logger = logging.getLogger(__file__)
    logger.setLevel(logging.DEBUG)
    h1 = logging.StreamHandler(sys.stdout)
    h1.setLevel(logging.DEBUG)
    h1.addFilter(lambda record: record.levelno <= logging.INFO)
    h2 = logging.StreamHandler()
    h2.setLevel(logging.WARNING)
    logger.addHandler(h1)
    logger.addHandler(h2)
    parser = argparse.ArgumentParser(
        description="Track BLE advertised packets")
    parser.add_argument("-D", "--device", default='hci0',
                        help="Select the hciX device to use "
                             "(default hci0).")

    @asyncio.coroutine
    def timeout():
        yield from asyncio.sleep(10)

    def ble_process(data):
        ev = HCI_Event()
        ev.decode(data)
        advertisement = EddyStone().decode(ev)
        if advertisement:
            logger.info("EddyStone URL: %s" % advertisement['url'])
            for task in asyncio.Task.all_tasks():
                task.cancel()

    try:
        opts = parser.parse_args()
    except Exception as e:
        parser.error("Error: " + str(e))
        return 1
    with InteractiveCommand('bluetoothctl') as btctl:
        btctl.writeline('power on')
        time.sleep(3)
        btctl.writeline('exit')
        btctl.kill()
    event_loop = asyncio.get_event_loop()
    # First create and configure a STREAM socket
    try:
        mysocket = create_bt_socket(int(opts.device.replace('hci', '')))
    except OSError as e:
        logger.error('%s' % e)
        return 1
    # Create a connection with the STREAM socket
    fac = event_loop._create_connection_transport(
        mysocket, BLEScanRequester, None, None)
    # Start it
    conn, btctrl = event_loop.run_until_complete(fac)
    # Attach processing
    btctrl.process = ble_process
    # Probe
    btctrl.send_scan_request()
    try:
        event_loop.run_until_complete(timeout())
        logger.error('No EddyStone URL advertisement detected!')
        return 1
    except asyncio.CancelledError:
        return 0
    except KeyboardInterrupt:
        return 1
    finally:
        btctrl.stop_scan_request()
        command = HCI_Cmd_LE_Advertise(enable=False)
        btctrl.send_command(command)
        conn.close()
        event_loop.close()


if __name__ == '__main__':
    raise SystemExit(main())
