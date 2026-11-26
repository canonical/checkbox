#!/usr/bin/env python3
#
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.

import argparse
from pathlib import Path
from typing import Dict

from checkbox_support.helpers import display_info
from checkbox_support.parsers.xrandr import MonitorConfigX11


def get_resolutions() -> Dict[str, str]:
    """Get the current resolutions of all connected monitors.

    This will use the appropriate `MonitorConfig` based on the current
    XDG_SESSION_TYPE and XDG_CURRENT_DESKTOP environment variables,
    falling back to using xrandr via `MonitorConfigX11` if none matches.

    :returns: dict of connector name to resolution string
    """
    try:
        monitor_config = display_info.get_monitor_config()
    except ValueError:
        monitor_config = MonitorConfigX11()
    print(f"Using {type(monitor_config).__name__}")
    return monitor_config.get_current_resolutions()


def format_resolutions(resolutions: Dict[str, str]) -> str:
    """Format resolutions dict into a string for printing.

    :param resolutions: dict of connector name to resolution string
    :returns: formatted string in the form "connector: resolution"
    """
    return "".join(
        f"{connector}: {resolution}\n"
        for connector, resolution in sorted(resolutions.items())
    )


def load_resolutions(path: Path) -> Dict[str, str]:
    """Load resolutions previously saved to a file.

    :param path: path to the file containing saved resolutions
    :returns: dict of connector name to resolution string
    """
    return dict(
        line.split(": ", 1) for line in path.read_text().splitlines() if line
    )


def record(path: Path) -> None:
    """Record the current resolutions to a file.

    :param path: path to the file where resolutions will be saved
    """
    output = format_resolutions(get_resolutions())
    path.write_text(output)
    print(output, end="")


def compare(path: Path) -> None:
    """Compare the current resolutions with those saved in a file.

    :param path: path to the file containing saved resolutions
    :raises SystemExit: on any encountered errors
    """
    before = load_resolutions(path)
    after = get_resolutions()
    print("Recorded resolutions:")
    print(format_resolutions(before), end="")
    print("Current resolutions:")
    print(format_resolutions(after), end="")

    errors = []
    for connector in sorted(set(before) | set(after)):
        old = before.get(connector)
        new = after.get(connector)
        if old == new:
            continue
        if new is None:
            errors.append(f"{connector}: was {old}, now missing or inactive")
        elif old is None:
            errors.append(
                f"{connector}: new monitor, not recorded before ({new})"
            )
        else:
            errors.append(
                f"{connector}: resolution changed from {old} to {new}"
            )

    if errors:
        raise SystemExit("\n".join(errors))
    print("Resolutions match.")


def parse_args(argv):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action")
    subparsers.required = True
    record_parser = subparsers.add_parser(
        "record", help="Save the current resolutions to a file"
    )
    record_parser.add_argument("file", type=Path)
    compare_parser = subparsers.add_parser(
        "compare", help="Compare the current resolutions with a saved file"
    )
    compare_parser.add_argument("file", type=Path)
    return parser.parse_args(argv)


def main(argv=None):
    """Main entry point for the script."""
    args = parse_args(argv)
    if args.action == "record":
        record(args.file)
    else:
        compare(args.file)


if __name__ == "__main__":
    main()
