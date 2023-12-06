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

from pathlib import Path


def get_node_content(path):
    """Retrieve the content from a sysfs path.

    :param path: path to the sysfs node
    :type path: str or Path
    :return: content of the sysfs node
    :rtype: str
    """
    content = None
    with open(path, "r") as f:
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
    :raises SystemExit: If no bluetooth adapters are found
    :return: List of tuples containing the sysfs basename and the device name
        (e.g.: [("rfkill3", "dell-bluetooth"),])
    :rtype: list
    """
    rf_devices = []
    for rfdev in paths_list:
        if is_bluetooth_adapter(rfdev):
            device_name = get_node_content(rfdev / "name")
            rf_devices.append((rfdev.name, device_name))
    if rf_devices:
        return rf_devices
    else:
        raise SystemExit("No bluetooth adapters registered with rfkill")


if __name__ == "__main__":
    rfkill_path = Path("/sys/class/rfkill")
    rf_devices_paths = []
    if rfkill_path.is_dir():
        rf_devices_paths = list(rfkill_path.iterdir())
    rf_devices = get_bluetooth_devices(rf_devices_paths)
    for rf_device in rf_devices:
        print(" ".join(rf_device))
