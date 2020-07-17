#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2019 Canonical Ltd.
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import selectors
import time

import evdev

parser = argparse.ArgumentParser()
parser.add_argument("name", help='Touch device product name')
parser.add_argument("--timeout", type=int, default=10, help='timeout')
parser.add_argument(
    "--xfingers", "-x", type=int, default=1, help="X-fingers tap event")
args = parser.parse_args()
start = time.time()


def check_timeout():
    if time.time() > start + args.timeout:
        raise SystemExit("Event not detected")


selector = selectors.DefaultSelector()
for d in [evdev.InputDevice(path) for path in evdev.list_devices()]:
    if d.name == args.name:
        device = d
        break
else:
    raise SystemExit("Touch device not found!")
selector.register(device, selectors.EVENT_READ)


while True:
    time.sleep(0.25)  # sleep for 250 milliseconds
    check_timeout()
    for key, mask in selector.select(1):
        dev = key.fileobj
        for e in dev.read():
            tap = args.xfingers
            if tap == 1:
                if (e.type == 3 and e.code == 47 and e.value > 0):
                    raise SystemExit(
                        "Multitouch Event detected but Single was expected")
                # type 1 is evdev.ecodes.EV_KEY
                # code 330 is a BTN_TOUCH event
                # value is a boolean, 1 means a PRESS, 0 a RELEASED event
                if (e.type == 1 and e.code == 330 and e.value == 1):
                    print("SUCCESS:", e)
                    raise SystemExit
            else:
                # type 3 is evdev.ecodes.EV_ABS
                # code 47 is a PRESS event
                # value is the 0-indexed amount of simultaneous detected
                # fingers
                if (e.type == 3 and e.code == 47 and e.value == tap - 1):
                    print("SUCCESS:", e)
                    raise SystemExit
            check_timeout()
    else:
        check_timeout()
