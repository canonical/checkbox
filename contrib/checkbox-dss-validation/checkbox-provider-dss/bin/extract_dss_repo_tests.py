#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
#
# Authors:
#     Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
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
"""Extract test cases and names from DSS repo"""

import argparse
import subprocess
import typing as t

TOX_PATH_IN_REPO = ".venv/bin/tox"
MATCHING_PREFIX = "tests/integration"


def main(args: t.List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Extract test cases and names from DSS repo"
    )
    parser.add_argument(
        "dss_repo", help="Path to the local clone of the DSS repository"
    )
    parser.add_argument("tox_env", help="Tox environment to collect tests from")

    given = parser.parse_args(args)
    dss_repo = given.dss_repo
    tox_env = given.tox_env

    cmd = [TOX_PATH_IN_REPO, "-e", tox_env, "--", "--collect-only", "-qq"]
    output = subprocess.check_output(
        cmd, cwd=dss_repo, text=True, stderr=subprocess.STDOUT
    )

    found_matches = False
    for line in output.splitlines():
        if not line:
            continue

        if line.startswith(MATCHING_PREFIX):
            found_matches = True
            parts = line.split("::")
            test_case = parts[0]
            print(f"test_case: {test_case}")
            test_name = parts[1]
            print(f"test_name: {test_name}")
            print()

    if not found_matches:
        raise ValueError(f"Did not find expected '{MATCHING_PREFIX}' in:\n{output}")


if __name__ == "__main__":  # pragma: no cover
    main()
