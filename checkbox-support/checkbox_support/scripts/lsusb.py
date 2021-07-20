# This file is part of Checkbox.
#
# Copyright 2020 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
from checkbox_support.parsers import sysfs_usb

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-s', '--short', action='store_true',
        help="Print output in a short form")
    parser.add_argument(
        '-l', '--long', action='store_true',
        help="Use the new output format")
    parser.add_argument('-f', '--file', help="Path to the usb.ids file")
    args = parser.parse_args()

    usb_ids = sysfs_usb.UsbIds(args.file)
    for dev in sysfs_usb.get_root_devices(usb_ids):
        if args.short:
            print(dev.to_short_str())
        elif args.long:
            print(dev.to_str())
        else:
            print(dev.to_legacy_str())

if __name__ == '__main__':
    main()
