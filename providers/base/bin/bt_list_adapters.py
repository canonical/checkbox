#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2018-2023 Canonical Ltd.
#
# Authors:
#    Jonathan Cave <jonathan.cave@canonical.com>
#    Pierre Equoy <pierre.equoy@canonical.com>
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

import sys
from collections import namedtuple
from pathlib import Path


BTDevice = namedtuple("BTDevice", ["sysfs_name", "device_name"])


def get_node_content(path: Path):
    """Retrieve the content from a sysfs path.

    :param path: path to the sysfs node
    :type path: str or Path
    :return: content of the sysfs node
    :rtype: str
    """
    with path.open("r") as f:
        content = f.read().strip()
    return content


def is_bluetooth_adapter(path):
    """Check if a given sysfs node is a bluetooth adapter.

    :param path: Path to the sysfs node
    :type path: Path
    :return: `True` if it is a bluetooth adapter, `False` otherwise
    :rtype: bool
    """
    type = get_node_content(path / "type")
    if type == "bluetooth":
        return True
    return False


def get_bluetooth_devices(paths_list):
    """Retrieve information about bluetooth devices from a list of sysfs paths.

    :param paths_list: List of sysfs paths to check
    :type paths_list: list
    :return: List of named tuples containing the sysfs basename and the device
        name, for example:
        [BTDevice(sysfs_name='rfkill3', device_name='dell-bluetooth'),]
    :rtype: list
    """
    rf_devices = []
    for rfdev in paths_list:
        if is_bluetooth_adapter(rfdev):
            device_name = get_node_content(rfdev / "name")
            btdev = BTDevice(rfdev.name, device_name)
            rf_devices.append(btdev)
    return rf_devices


def main():
    try:
        rf_devices_paths = list(Path("/sys/class/rfkill").iterdir())
    except FileNotFoundError:
        rf_devices_paths = []
    rf_devices = get_bluetooth_devices(rf_devices_paths)
    if rf_devices:
        for rf_device in rf_devices:
            print(" ".join(rf_device))
    else:
        raise SystemExit("No bluetooth adapters registered with rfkill")


if __name__ == "__main__":
    sys.exit(main())
