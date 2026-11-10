#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of Checkbox.
#
# Copyright 2012-2025 Canonical Ltd.
#
# Authors:
#   Isaac Yang <isaac.yang@canonical.com>
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

"""
Backlight panel resource enumeration and brightness ramp test.

Subcommands
-----------
resource  -- enumerate /sys/class/backlight devices and print checkbox
             resource records (device / panel_alias).
test      -- ramp brightness across five levels on a single device and
             verify each level was applied.
"""

import argparse
import math
import os
import re
import sys
import time

from typing import Dict, List, Optional, Tuple

SYSFS_BACKLIGHT = "/sys/class/backlight"
BRIGHTNESS_LEVELS = [0, 0.25, 0.5, 0.75, 1]
SETTLE_SECONDS = 2


# ---------------------------------------------------------------------------
# BacklightPanelResource
# ---------------------------------------------------------------------------


class BacklightPanelResource:
    """
    Enumerate backlight devices and produce checkbox resource records.

    Reads a ``BACKLIGHT_PANEL_MAP`` string to map sysfs device basenames
    to human-friendly aliases (e.g. ``dsi``, ``edp``).  When no mapping
    is supplied the device basename itself is used as the alias.
    """

    def __init__(
        self,
        panel_mapping: str = "",
        sysfs_path: str = SYSFS_BACKLIGHT,
    ) -> None:
        """Initialise with an optional mapping string and sysfs root."""
        self.sysfs_path = sysfs_path
        self.mapping_pairs = self._parse_mapping(panel_mapping)
        self.devices = self._enumerate_devices()

    # -- static helpers -----------------------------------------------------

    @staticmethod
    def normalize_alias(raw: str) -> str:
        """
        Lowercase *raw*, replace non-alphanumeric chars with ``-``.
        Collapses repeated separators and strips leading/trailing ``-``.
        """
        lowered = raw.lower()
        cleaned = re.sub(r"[^a-z0-9]+", "-", lowered)
        return cleaned.strip("-")

    @staticmethod
    def deduplicate_alias(alias: str, seen: Dict[str, int]) -> str:
        """
        Return *alias* with a numeric suffix if it already exists.

        Updates *seen* in-place.  First occurrence stays as-is; second
        becomes ``alias-2``, third ``alias-3``, etc.
        """
        if alias not in seen:
            seen[alias] = 1
            return alias
        seen[alias] += 1
        return "{}-{}".format(alias, seen[alias])

    # -- internal -----------------------------------------------------------

    @staticmethod
    def _parse_mapping(
        raw: str,
    ) -> List[Tuple[str, str]]:
        """
        Parse ``alias:device[,alias:device ...]`` into pairs.

        Malformed tokens are warned on *stderr* and skipped.
        """
        pairs: List[Tuple[str, str]] = []
        if not raw or not raw.strip():
            return pairs
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            parts = token.split(":", 1)
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                msg = "WARNING: malformed mapping" " token '{}', skipping"
                print(msg.format(token), file=sys.stderr)
                continue
            pairs.append((parts[0].strip(), parts[1].strip()))
        return pairs

    def _enumerate_devices(self) -> List[str]:
        """Return sorted basenames of dirs under *sysfs_path*."""
        if not os.path.isdir(self.sysfs_path):
            return []
        entries: List[str] = []
        for name in sorted(os.listdir(self.sysfs_path)):
            full = os.path.join(self.sysfs_path, name)
            if os.path.isdir(full):
                entries.append(name)
        return entries

    # -- public API ---------------------------------------------------------

    def build_records(self) -> List[Tuple[str, str]]:
        """
        Return ``(device, panel_alias)`` pairs.

        Mapped devices get the corresponding alias (normalized).
        Remaining devices fall back to their normalized basename.
        Aliases are de-duplicated with numeric suffixes.
        """
        device_to_alias: Dict[str, str] = {}
        device_set = set(self.devices)
        for alias_raw, dev in self.mapping_pairs:
            if dev not in device_set:
                print(
                    "WARNING: mapped device '{}'"
                    " not found under {},"
                    " skipping".format(dev, self.sysfs_path),
                    file=sys.stderr,
                )
                continue
            device_to_alias[dev] = self.normalize_alias(alias_raw)

        seen: Dict[str, int] = {}
        records: List[Tuple[str, str]] = []
        for dev in self.devices:
            raw_alias = device_to_alias.get(dev, dev)
            normalized = self.normalize_alias(raw_alias)
            alias = self.deduplicate_alias(normalized, seen)
            records.append((dev, alias))
        return records

    def print_records(self) -> int:
        """
        Print checkbox resource records to stdout.

        Returns 0 always (zero devices simply means no output).
        """
        if not self.devices:
            return 0
        for dev, alias in self.build_records():
            print("device: {}".format(dev))
            print("panel_alias: {}".format(alias))
            print()
        return 0


# ---------------------------------------------------------------------------
# BrightnessTest
# ---------------------------------------------------------------------------


class BrightnessTest:
    """
    Run a brightness ramp test on a single backlight device.

    Ramps brightness through five levels (0 / 25 / 50 / 75 / 100 %),
    verifying each level, and always restores the original value.
    """

    def __init__(
        self,
        device: str,
        sysfs_path: str = SYSFS_BACKLIGHT,
        settle: int = SETTLE_SECONDS,
    ) -> None:
        """Initialise with device basename and optional tunables."""
        self.device = device
        self.interface = os.path.join(sysfs_path, device)
        self.settle = settle

    # -- sysfs I/O ----------------------------------------------------------

    @staticmethod
    def read_value(path: str) -> int:
        """Read an integer from *path*."""
        with open(path, "r") as fh:
            return int(fh.read().strip())

    @staticmethod
    def write_value(value: int, path: str) -> None:
        """Write an integer *value* to *path*."""
        with open(path, "w") as fh:
            fh.write("{}".format(value))

    # -- verification -------------------------------------------------------

    def was_brightness_applied(self) -> bool:
        """
        Check that actual brightness matches last written value.

        Allows a tolerance of 1 unit.
        """
        actual_path = os.path.join(self.interface, "actual_brightness")
        set_path = os.path.join(self.interface, "brightness")
        actual = self.read_value(actual_path)
        last_set = self.read_value(set_path)
        return abs(actual - last_set) <= 1

    # -- public API ---------------------------------------------------------

    def run(self) -> int:
        """
        Execute the ramp cycle.

        Returns the number of levels that failed verification.
        Original brightness is always restored via ``finally``.
        """
        actual_path = os.path.join(self.interface, "actual_brightness")
        max_path = os.path.join(self.interface, "max_brightness")
        original = self.read_value(actual_path)
        max_br = self.read_value(max_path)
        print("Current brightness: {}".format(original))
        print("Maximum brightness: {}\n".format(max_br))

        failures = 0
        try:
            for mult in BRIGHTNESS_LEVELS:
                target = int(math.ceil(max_br * mult))
                print("Set the brightness as {}".format(target))
                self.write_value(
                    target,
                    os.path.join(self.interface, "brightness"),
                )
                time.sleep(self.settle)
                if not self.was_brightness_applied():
                    failures += 1
        finally:
            self.write_value(
                original,
                os.path.join(self.interface, "brightness"),
            )
            _msg = "Set brightness back to original value: {}"
            print(_msg.format(original))
        return failures


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_resource(args: argparse.Namespace) -> int:
    """Handle the ``resource`` subcommand."""
    resource = BacklightPanelResource(
        panel_mapping=args.panel_mapping or "",
    )
    return resource.print_records()


def cmd_test(args: argparse.Namespace) -> int:
    """Handle the ``test`` subcommand."""
    if os.geteuid() != 0:
        print(
            "Error: please run this program as root",
            file=sys.stderr,
        )
        return 1

    interface = os.path.join(SYSFS_BACKLIGHT, args.device)
    if not os.path.isdir(interface):
        print(
            "ERROR: {} not found".format(interface),
            file=sys.stderr,
        )
        return 1

    print("Test the brightness of '{}'\n".format(args.device))
    print("Interface: {}\n".format(interface))

    bt = BrightnessTest(device=args.device, settle=args.settle)
    return bt.run()


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args(
    argv: Optional[List[str]] = None,
) -> argparse.Namespace:
    """Build the CLI parser with ``resource`` and ``test`` subcommands."""
    parser = argparse.ArgumentParser(
        description=(
            "Backlight panel resource enumeration" " and brightness ramp test."
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    _res_help = "List backlight devices as checkbox" " resource records."
    res_parser = subparsers.add_parser(
        "resource",
        help=_res_help,
    )
    res_parser.add_argument(
        "--panel-mapping",
        default="",
        help=(
            "Comma-separated alias:device pairs"
            " (e.g. dsi:backlight-lcd0,"
            "edp:backlight-lcd1)."
            " Typically sourced from"
            " $BACKLIGHT_PANEL_MAP."
        ),
    )

    test_parser = subparsers.add_parser(
        "test",
        help=("Run brightness ramp test on a" " single backlight device."),
    )
    test_parser.add_argument(
        "-d",
        "--device",
        required=True,
        help=("Backlight device basename" " (e.g. backlight-lcd0)."),
    )
    test_parser.add_argument(
        "--settle",
        type=int,
        default=SETTLE_SECONDS,
        help=(
            "Seconds to wait between brightness"
            " steps (default: {}).".format(SETTLE_SECONDS)
        ),
    )

    return parser.parse_args(argv)


def main() -> int:
    """Program entry point."""
    args = parse_args()
    if args.command == "resource":
        return cmd_resource(args)
    elif args.command == "test":
        return cmd_test(args)
    else:
        print("ERROR: specify a subcommand" " (resource | test)")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
