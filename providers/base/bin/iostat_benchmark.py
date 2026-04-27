#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Jeff Lane <jeff@ubuntu.com>
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
import re
import subprocess
import sys


def parse_iostat_column(output, column):
    values = [float(n) for n in re.findall(rf"{column}\n.*?(\S+)\n", output)]
    if not values:
        print(
            f"ERROR: No '{column}' values found in iostat output",
            file=sys.stderr,
        )
        return 1
    print(f"{sum(values) / len(values):.2f}%")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Measure average CPU or disk utilization from iostat."
    )
    parser.add_argument(
        "metric",
        choices=["cpu", "disk"],
        help="Which metric to report: 'cpu' (idle %%) or 'disk' (util %%)",
    )
    parser.add_argument(
        "-t",
        "--time",
        action="store",
        default=10,
        help="Time in seconds to run iostat. (default: %(default)s)",
    )
    args = parser.parse_args()

    column = "idle" if args.metric == "cpu" else "util"

    try:
        result = subprocess.run(
            ["iostat", "-x", "-m", "1", str(args.time)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"ERROR: iostat failed: {e}", file=sys.stderr)
        return 1

    return parse_iostat_column(result.stdout, column)


if __name__ == "__main__":
    sys.exit(main())
