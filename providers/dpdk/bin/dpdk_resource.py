#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
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

import socket

from collections import defaultdict
from pathlib import Path
from typing import List, Dict

# Dictionary with supported DPDK drivers per vendor
DPDK_SUPPORTED_DRIVERS = {
    "Nvidia": ["mlx4_core", "mlx5_core"],
    "Intel": [
        "cpfl",
        "e1000",
        "fm10k",
        "i40e",
        "ice",
        "idpf",
        "ifc",
        "igc",
        "ipn3ke",
        "ixgbe",
    ],
    "Broadcom": ["bnxt"],
}


def get_dpdk_supported_drivers() -> Dict[str, List[str]]:
    """Get a list of DPDK supported drivers available from network adapters.

    :return: dpdk supported drivers and interfaces using them
    """
    dpdk_drivers = defaultdict(list)

    # Get all network interfaces
    interfaces = socket.if_nameindex()

    # Iterate over interfaces to get dpdk supported drivers if any
    for _, iface in interfaces:
        device_path = Path("/sys/class/net/{}/device/driver".format(iface))
        if device_path.exists() and device_path.is_symlink():
            driver_name = device_path.resolve().name
            if any(
                driver_name in drivers
                for drivers in DPDK_SUPPORTED_DRIVERS.values()
            ):
                dpdk_drivers[driver_name].append(iface)

    return dpdk_drivers


def print_drivers(drivers: Dict[str, List[str]]):
    """Display DPDK supported drivers information

    :param drivers: DPDK supported drivers and interfaces using them
    """
    for driver, interfaces in drivers.items():
        print("name: {}".format(driver))
        print("interfaces: {}".format(" ".join(iface for iface in interfaces)))
        print()


def main():
    supported_drivers = get_dpdk_supported_drivers()
    if supported_drivers:
        print("dpdk-supported: yes\n")
        print_drivers(supported_drivers)
    else:
        print("dpdk-supported: no\n")


if __name__ == "__main__":
    main()
