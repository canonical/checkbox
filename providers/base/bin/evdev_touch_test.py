#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2019-2022 Canonical Ltd.
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

import evdev
from evdev.ecodes import ABS_MT_SLOT  # press event
from evdev.ecodes import BTN_TOUCH  # finger touches the screen
from evdev.ecodes import EV_ABS  # touch event on touchscreen
from evdev.ecodes import EV_KEY


def get_device(name):
    for d in [evdev.InputDevice(path) for path in evdev.list_devices()]:
        if d.name == name:
            return d
    else:
        raise SystemExit("Touch device not found!")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name", help="Touch device product name")
    parser.add_argument(
        "--xfingers", "-x", type=int, default=1, help="X-fingers tap event"
    )
    args = parser.parse_args()

    device = get_device(args.name)
    tap = args.xfingers
    while True:
        for e in device.read_loop():
            if tap == 1:
                if e.type == EV_ABS and e.code == ABS_MT_SLOT and e.value > 0:
                    raise SystemExit(
                        "Multitouch Event detected but Single was expected"
                    )
                # value is a boolean, 1 means a PRESS, 0 a RELEASED event
                if e.type == EV_KEY and e.code == BTN_TOUCH and e.value == 1:
                    print("SUCCESS:", e)
                    raise SystemExit
            else:
                # value is the 0-indexed amount of simultaneous detected
                # fingers
                if (
                    e.type == EV_ABS
                    and e.code == ABS_MT_SLOT
                    and e.value == tap - 1
                ):
                    print("SUCCESS:", e)
                    raise SystemExit


if __name__ == "__main__":
    main()
