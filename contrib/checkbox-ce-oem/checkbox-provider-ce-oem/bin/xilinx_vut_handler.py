#!/usr/bin/env python3
"""
This file is part of Checkbox.

Copyright 2022 Canonical Ltd.
Written by:
  Talha Can Havadar <talha.can.havadar@canonical.com>

Checkbox is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

Checkbox is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
"""

import subprocess
import argparse
import sys


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vut", help="Package version under test", dest="vut")
    ns, args = parser.parse_known_args()

    return ns, sys.argv[:1] + args


def compare_versions(operator, version_a, version_b):
    cmd = ["dpkg", "--compare-versions", version_a, operator, version_b]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


args, argv = parse_args()
sys.argv[:] = argv
__vut__ = args.vut or ""
