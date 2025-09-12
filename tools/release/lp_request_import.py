#!/usr/bin/python3
# This file is part of Checkbox.
#
# Copyright 2022-2025 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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
Script that forces a code import from Github in Launchpad.
It's a blocking call, usually code is imported in less than a minute.
Timeout set to 2 minutes

References:
- https://help.launchpad.net/Code/Imports
- https://launchpad.net/+apidoc/devel.html#code_import
"""

import sys
import time

from argparse import ArgumentParser, Namespace
from datetime import datetime, timedelta

from utils import get_launchpad_client

IMPORT_MAX_TIME_WAIT_S = 120


def parse_args(argv: list[str]) -> Namespace:
    parser = ArgumentParser("A script to force code import in Launchpad.")
    parser.add_argument("repo", help="Unique name of the repository")
    return parser.parse_args(argv)


def main(argv: list[str] = []):
    args = parse_args(argv)
    lp = get_launchpad_client()
    repo = lp.git_repositories.getByPath(path=args.repo)
    if not repo:
        raise SystemExit(f"{args.repo} repo was not found in Launchpad.")

    start = datetime.utcnow()
    try:
        repo.code_import.requestImport()
    except Exception as e:
        err_str = str(e)
        if "This code import is already running" not in err_str:
            raise SystemExit(err_str)

    max_wait_timedelta = timedelta(seconds=IMPORT_MAX_TIME_WAIT_S)
    while repo.code_import.date_last_successful.replace(tzinfo=None) < start:
        if datetime.utcnow() - start > max_wait_timedelta:
            raise SystemExit(
                "Launchpad failed to import, "
                f"timed out after {IMPORT_MAX_TIME_WAIT_S}s"
            )
        print("Code import not yet completed, waiting...")
        time.sleep(5)
    print(f"Code import completed ({repo.web_link})")


if __name__ == "__main__":
    main(sys.argv[1:])
