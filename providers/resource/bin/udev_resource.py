#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2011-2016 Canonical Ltd.
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
import argparse
import shlex

from collections import OrderedDict
from subprocess import check_output, CalledProcessError

from checkbox_support.parsers.udevadm import UdevadmParser

categories = ("ACCELEROMETER", "AUDIO", "BLUETOOTH", "CAPTURE", "CARDREADER",
              "CDROM", "DISK", "KEYBOARD", "INFINIBAND", "MMAL", "MOUSE",
              "NETWORK", "TPU", "OTHER", "PARTITION", "TOUCHPAD",
              "TOUCHSCREEN", "USB", "VIDEO", "WATCHDOG", "WIRELESS", "WWAN")

attributes = ("path", "name", "bus", "category", "driver", "product_id",
              "vendor_id", "subproduct_id", "subvendor_id", "product",
              "vendor", "interface", "mac", "product_slug", "vendor_slug",
              "symlink_uuid")


def dump_udev_db(udev):
    for device in udev.run():
        for attribute in attributes:
            value = getattr(device, attribute)
            if value is not None:
                print("%s: %s" % (attribute, value))
        print()


def filter_by_categories(udev, categories):
    count = 0
    for device in udev.run():
        c = getattr(device, "category", None)
        if c in categories:
            count += 1
            for attribute in attributes:
                value = getattr(device, attribute)
                if value is not None:
                    print("%s: %s" % (attribute, value))
            print()
    return count


def display_by_categories(udev, categories, short=False):
    count = 0
    data = OrderedDict()
    for category in categories:
        data[category] = []
    for device in udev.run():
        c = getattr(device, "category", None)
        if c in categories:
            count += 1
            p = getattr(device, "product", "Unknow product")
            v = getattr(device, "vendor", "Unknow vendor")
            vid = device.vendor_id if device.vendor_id else 0
            pid = device.product_id if device.product_id else 0
            if not p:
                p = getattr(device, "interface", "Unknow product")
            data[c].append(
                "{} {} [{:04x}:{:04x}]".format(v, p, vid, pid))
    for c, devices in data.items():
        if short:
            for d in devices:
                print("{}".format(
                    d.replace('None ', '').replace(' None', '')))
        else:
            print("{} ({}):".format(c, len(devices)))
            for d in devices:
                print(" - {}".format(d))
            print()
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--command", action='store', type=str,
                        default="udevadm info --export-db",
                        help="""Command to execute to get udevadm information.
                              Only change it if you know what you're doing.""")
    parser.add_argument("-d", "--lsblkcommand", action='store', type=str,
                        default="lsblk -i -n -P -o KNAME,TYPE,MOUNTPOINT",
                        help="""Command to execute to get lsblk information.
                              Only change it if you know what you're doing.""")
    parser.add_argument('-l', '--list', nargs='+', choices=categories,
                        metavar=("CATEGORY"), default=(),
                        help="""List devices found under the requested
                        categories.
                        Acceptable categories to list are:
                        {}""".format(', '.join(categories)))
    parser.add_argument('-f', '--filter', nargs='+', choices=categories,
                        metavar=("CATEGORY"), default=(),
                        help="""Filter devices found under the requested
                        categories.
                        Acceptable categories to list are:
                        {}""".format(', '.join(categories)))
    parser.add_argument('-s', '--short', action='store_true')
    args = parser.parse_args()
    try:
        output = check_output(shlex.split(args.command))
        lsblk = check_output(shlex.split(args.lsblkcommand))
    except CalledProcessError as exc:
        raise SystemExit(exc)
    # Set the error policy to 'ignore' in order to let tests depending on this
    # resource to properly match udev properties
    output = output.decode("UTF-8", errors='ignore')
    lsblk = lsblk.decode("UTF-8", errors='ignore')
    list_partitions = False
    if 'PARTITION' in args.list or 'PARTITION' in args.filter:
        list_partitions = True
    udev = UdevadmParser(output, lsblk=lsblk, list_partitions=list_partitions)
    if args.list:
        if display_by_categories(udev, args.list, args.short) == 0:
            raise SystemExit("No devices found")
    elif args.filter:
        if filter_by_categories(udev, args.filter) == 0:
            raise SystemExit("No devices found")
    else:
        dump_udev_db(udev)


if __name__ == "__main__":
    main()
