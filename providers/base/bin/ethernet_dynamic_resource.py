#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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
import os
from typing import List


def get_excluded_from_env(env_var: str) -> List[str]:
    """Parses comma-separated strings from environment variables."""
    val = os.environ.get(env_var, "")
    return [item.strip() for item in val.split(",") if item.strip()]


def is_real_hardware(iface_path: str) -> bool:
    """
    Checks if the interface is backed by physical hardware (PCI/USB/etc).
    Virtual interfaces like lo, bridges, and veth lack the 'device' link.
    """
    device_path = os.path.join(iface_path, "device")
    if not os.path.islink(device_path):
        return False

    # Filter out wireless interfaces
    if os.path.exists(os.path.join(iface_path, "wireless")):
        return False

    # Ensure the subsystem is not 'virtual'
    subsystem_path = os.path.join(device_path, "subsystem")
    if os.path.islink(subsystem_path):
        subsystem_name = os.path.basename(os.readlink(subsystem_path))
        if subsystem_name == "virtual":
            return False

    return True


def list_interfaces(
    ignored_ifaces: List[str], ignored_macs: List[str]
) -> None:
    """
    Scans /sys/class/net and filters by hardware subsystem and env vars.
    """
    base_path = "/sys/class/net/"
    if not os.path.exists(base_path):
        return

    # Sort for deterministic output
    for iface in sorted(os.listdir(base_path)):
        iface_path = os.path.join(base_path, iface)

        if not is_real_hardware(iface_path):
            continue

        if iface in ignored_ifaces:
            continue

        try:
            with open(os.path.join(iface_path, "address"), "r") as f:
                mac = f.read().strip()
        except (OSError, IOError):
            continue

        if mac.lower() in ignored_macs:
            continue

        print("interface: {}".format(iface))
        print("mac: {}".format(mac))
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List hardware Ethernet interfaces and MAC addresses."
    )
    parser.add_argument(
        "--env-mac",
        default="EXCLUDE_MACS",
        help="Env var for MACs to filter (default: EXCLUDE_MACS)",
    )
    parser.add_argument(
        "--env-iface",
        default="EXCLUDE_INTERFACES",
        help="Env var for interfaces to filter (default: EXCLUDE_INTERFACES)",
    )

    args = parser.parse_args()

    ignored_macs = [m.lower() for m in get_excluded_from_env(args.env_mac)]
    ignored_ifaces = get_excluded_from_env(args.env_iface)

    list_interfaces(ignored_ifaces, ignored_macs)


if __name__ == "__main__":
    main()
