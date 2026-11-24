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
import json
import os

from collections import OrderedDict
from subprocess import check_output, CalledProcessError

from checkbox_support.parsers.udevadm import UdevadmParser

categories = (
    "ACCELEROMETER",
    "AUDIO",
    "BLUETOOTH",
    "CAPTURE",
    "CARDREADER",
    "CDROM",
    "DISK",
    "KEYBOARD",
    "INFINIBAND",
    "MMAL",
    "MOUSE",
    "NETWORK",
    "TPU",
    "OTHER",
    "PARTITION",
    "TOUCHPAD",
    "TOUCHSCREEN",
    "USB",
    "VIDEO",
    "WATCHDOG",
    "WIRELESS",
    "WWAN",
)

attributes = (
    "path",
    "name",
    "bus",
    "category",
    "driver",
    "product_id",
    "vendor_id",
    "subproduct_id",
    "subvendor_id",
    "product",
    "vendor",
    "interface",
    "mac",
    "product_slug",
    "vendor_slug",
    "symlink_uuid",
)


class IgnoreTestPolicy:
    """Exclusion rule for one device type.

    The environment variable holds ``|``-separated ``property:value``
    selectors, where ``property`` is a field of the device resource and
    ``value`` must match exactly. Every device the policy applies to gets
    ``ignore_test``; other devices are left untouched so they can be
    handled by another policy.
    """

    env_var = None

    def __init__(self):
        self.selectors = []
        for selector in os.environ.get(self.env_var, "").split("|"):
            selector = selector.strip()
            if not selector:
                continue
            prop, _, value = selector.partition(":")
            if prop not in attributes or not value:
                raise ValueError(
                    f"Invalid {self.env_var} selector: {selector}"
                )
            self.selectors.append((prop, value))

    def applies_to(self, device):
        raise NotImplementedError

    def candidates(self, device):
        """Property sets the selectors are matched against."""
        return [device_properties(device)]

    def fields(self, device):
        if not self.applies_to(device):
            return {}
        ignored = any(
            str(properties.get(prop)) == value
            for properties in self.candidates(device)
            for prop, value in self.selectors
        )
        fields = {"ignore_test": ignored}
        if ignored:
            fields["ignore_test_reason"] = f"Excluded by {self.env_var}"
        return fields


class StorageTestPolicy(IgnoreTestPolicy):
    env_var = "CHECKBOX_STORAGE_TEST_EXCLUDE"

    def applies_to(self, device):
        return device.category == "DISK"


class DeviceTestPolicy:
    """Apply the first matching per-device-type exclusion policy."""

    policy_classes = (StorageTestPolicy,)

    def __init__(self):
        self.policies = [policy() for policy in self.policy_classes]

    def fields(self, device):
        for policy in self.policies:
            fields = policy.fields(device)
            if fields:
                return fields
        return {}


def device_properties(device):
    return {attribute: getattr(device, attribute) for attribute in attributes}


def filter_ignore_test(devices, policy):
    """Build enriched device records without mutating parser objects."""
    records = []
    for device in devices:
        record = device_properties(device)
        record.update(policy.fields(device))
        records.append(record)
    return records


def print_device(device):
    for attribute, value in device.items():
        if value is not None:
            print(f"{attribute}: {value}")
    print()


def dump_udev_db(udev):
    policy = DeviceTestPolicy()
    for device in filter_ignore_test(udev.run(), policy):
        # skip interface names like 224/1/3
        # see checkbox issue 2563
        if "/" in (device.get("interface") or ""):
            continue

        print_device(device)


def filter_by_categories(udev, categories):
    count = 0
    policy = DeviceTestPolicy()
    for device in filter_ignore_test(udev.run(), policy):
        c = device.get("category")
        if c in categories:
            count += 1
            print_device(device)
    return count


def display_by_categories(udev, categories, short=False):
    count = 0
    data = OrderedDict()
    policy = DeviceTestPolicy()
    for category in categories:
        data[category] = []
    for device in filter_ignore_test(udev.run(), policy):
        c = device.get("category")
        if c in categories:
            count += 1
            p = device.get("product", "Unknow product")
            v = device.get("vendor", "Unknow vendor")
            vid = device.get("vendor_id") or 0
            pid = device.get("product_id") or 0
            if not p:
                p = device.get("interface", "Unknow product")
            data[c].append(f"{v} {p} [{vid:04x}:{pid:04x}]")
    for c, devices in data.items():
        if short:
            for d in devices:
                print("{}".format(d.replace("None ", "").replace(" None", "")))
        else:
            print(f"{c} ({len(devices)}):")
            for d in devices:
                print(f" - {d}")
            print()
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--command",
        action="store",
        type=str,
        default="udevadm info --export-db",
        help="""Command to execute to get udevadm information.
                              Only change it if you know what you're doing.""",
    )
    parser.add_argument(
        "-d",
        "--lsblkcommand",
        action="store",
        type=str,
        default="lsblk -i -n -J -b -o KNAME,TYPE,MOUNTPOINT,FSTYPE,SIZE,UUID",
        help="""Command to execute to get lsblk information.
                              Only change it if you know what you're doing.""",
    )
    parser.add_argument(
        "-l",
        "--list",
        nargs="+",
        choices=categories,
        metavar=("CATEGORY"),
        default=(),
        help="""List devices found under the requested
                        categories.
                        Acceptable categories to list are:
                        {}""".format(", ".join(categories)),
    )
    parser.add_argument(
        "-f",
        "--filter",
        nargs="+",
        choices=categories,
        metavar=("CATEGORY"),
        default=(),
        help="""Filter devices found under the requested
                        categories.
                        Acceptable categories to list are:
                        {}""".format(", ".join(categories)),
    )
    parser.add_argument("-s", "--short", action="store_true")
    args = parser.parse_args()
    try:
        output = check_output(shlex.split(args.command))
        lsblk = check_output(shlex.split(args.lsblkcommand))
    except CalledProcessError as exc:
        raise SystemExit(exc)
    # Set the error policy to 'ignore' in order to let tests depending on this
    # resource to properly match udev properties
    output = output.decode("UTF-8", errors="ignore")
    lsblk = lsblk.decode("UTF-8", errors="ignore")
    lsblk = json.loads(lsblk)
    list_partitions = False
    if "PARTITION" in args.list or "PARTITION" in args.filter:
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
