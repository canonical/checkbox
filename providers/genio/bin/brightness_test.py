#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  brightness_test.py
#
# This file is part of Checkbox.
#
# Copyright 2012-2018 Canonical Ltd.
#
# Authors:
#   Alberto Milone <alberto.milone@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
#
#
# Patrick Chang modified this script for specific platform and display purpose.
#   - I keep the origianl logic of Brightness Class and just modified the main
#     function in order to get test the specific display. In addition, I divide
#     the brightness into five parts to have better test coverage.
#
#

import sys
import os
import time
import math

from argparse import ArgumentParser, RawTextHelpFormatter
from glob import glob


class Brightness(object):
    def __init__(self, path='/sys/class/backlight'):
        self.sysfs_path = path
        self.interfaces = self._get_interfaces_from_path()

    def read_value(self, path):
        '''Read the value from a file'''
        # See if the source is a file or a file object
        # and act accordingly
        file = path
        if file is None:
            lines_list = []
        else:
            # It's a file
            if not hasattr(file, 'write'):
                myfile = open(file, 'r')
                lines_list = myfile.readlines()
                myfile.close()
            # It's a file object
            else:
                lines_list = file.readlines()

        return int(''.join(lines_list).strip())

    def write_value(self, value, path, test=None):
        '''Write a value to a file'''
        value = '%d' % value
        # It's a file
        if not hasattr(path, 'write'):
            if test:
                path = open(path, 'a')
            else:
                path = open(path, 'w')
            path.write(value)
            path.close()
        # It's a file object
        else:
            path.write(value)

    def get_max_brightness(self, path):
        full_path = os.path.join(path, 'max_brightness')

        return self.read_value(full_path)

    def get_actual_brightness(self, path):
        full_path = os.path.join(path, 'actual_brightness')

        return self.read_value(full_path)

    def get_last_set_brightness(self, path):
        full_path = os.path.join(path, 'brightness')

        return self.read_value(full_path)

    def _get_interfaces_from_path(self):
        '''check all the files in a directory looking for quirks'''
        interfaces = []
        if os.path.isdir(self.sysfs_path):
            for d in glob(os.path.join(self.sysfs_path, '*')):
                if os.path.isdir(d):
                    interfaces.append(d)

        return interfaces

    def was_brightness_applied(self, interface):
        '''See if the selected brightness was applied

        Note: this doesn't guarantee that screen brightness
              changed.
        '''
        if (
            abs(self.get_actual_brightness(interface) -
                self.get_last_set_brightness(interface)) > 1
        ):
            return 1
        else:
            return 0


def main():
    parser = ArgumentParser(formatter_class=RawTextHelpFormatter)
    parser.add_argument(
        "-p", "--platform",
        help="Genio device platform type.",
        choices=["G1200-evk", "G700", "G350"]
    )
    parser.add_argument(
        "-d", "--display",
        choices=["dsi", "edp", "lvds"],
        help="The type of built-in display"
    )

    args = parser.parse_args()

    tables = {
        "G1200-evk": {
            "dsi": "backlight-lcd0",
            "edp": "backlight-lcd1",
            "lvds": "backlight-lcd1",
        },
        "G700": {
            "dsi": "1c008000.dsi0.0",
            "edp": "backlight-lcd0",
        },
        "G350": {
            "dsi": "14014000.dsi0.0",
        },
    }

    # Make sure that we have root privileges
    if os.geteuid() != 0:
        print('Error: please run this program as root',
              file=sys.stderr)
        exit(1)

    print(f"Test the brightness of '{args.display}' display")

    target_interface = ''
    try:
        target_interface = tables[args.platform][args.display]
        print(f"Interface: {target_interface}\n")
    except KeyError:
        raise SystemExit(
            f"ERROR: no suitable interface of {args.display} display")

    brightness = Brightness()

    # If no backlight interface can be found
    if len(brightness.interfaces) == 0:
        raise SystemExit("ERROR: no brightness interfaces found")

    exit_status = 0
    find_target_display = False
    print(f'Available Interfaces: {brightness.interfaces}')
    for interface in brightness.interfaces:
        if target_interface in interface:
            find_target_display = True
            # Get the current brightness which we can restore later
            original_brightness = brightness.get_actual_brightness(interface)
            print(f'Current brightness: {original_brightness}')

            # Get the maximum value for brightness
            max_brightness = brightness.get_max_brightness(interface)
            print(f'Maximum brightness: {max_brightness}\n')

            for m in [0, 0.25, 0.5, 0.75, 1]:
                # Set the brightness to half the max value
                current_brightness = math.ceil(max_brightness * m)
                print(f'Set the brightness as {current_brightness}')
                brightness.write_value(
                    current_brightness,
                    os.path.join(interface, 'brightness'))

                # Check that "actual_brightness" reports the same value we
                # set "brightness" to
                exit_status += brightness.was_brightness_applied(interface)

                # Wait a little bit before going back to the original value
                time.sleep(2)

            # Set the brightness back to its original value
            brightness.write_value(
                original_brightness,
                os.path.join(interface, 'brightness'))
            print(
                f'Set brightness back to original value: {original_brightness}'
            )
            # Close the loop since the target display has been tested
            break

    if not find_target_display:
        raise SystemExit(f"ERROR: no {target_interface} interface be found")
    raise SystemExit(exit_status)


if __name__ == '__main__':
    main()
