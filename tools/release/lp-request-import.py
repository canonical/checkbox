#!/usr/bin/python3
# This file is part of Checkbox.
#
# Copyright 2022 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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

import os
import sys
import time

from argparse import ArgumentParser
from datetime import datetime, timedelta

from launchpadlib.credentials import Credentials
from launchpadlib.launchpad import Launchpad


def main():
    parser = ArgumentParser("A script to force code import in Launchpad.")
    parser.add_argument('repo',
                        help="Unique name of the repository")
    args = parser.parse_args()
    credentials = Credentials.from_string(os.getenv("LP_CREDENTIALS"))
    lp = Launchpad(
        credentials, None, None, service_root='production', version='devel')
    repo = lp.git_repositories.getByPath(path=args.repo)
    if not repo:
        parser.error("{} repo was not found in Launchpad.".format(args.repo))
    start = datetime.utcnow()
    try:
        repo.code_import.requestImport()
    except Exception as e:
        if 'This code import is already running' not in e:
            return 1
    while (repo.code_import.date_last_successful.replace(tzinfo=None) < start):
        if datetime.utcnow() - start > timedelta(seconds=120):
            return 1
        time.sleep(5)
    print("Code import completed ({})".format(repo.web_link))
    return 0


if __name__ == "__main__":
    sys.exit(main())
