#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
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
This script facilitates the copying of packages from one Launchpad
Personal Package Archive (PPA) to another. It is designed for copying
every Checkbox package from a source PPA to a destination PPA
without the need for rebuilding.

Note: This script uses the LP_CREDENTIALS environment variable
"""
import os
import sys
import datetime
import argparse

from launchpadlib.credentials import Credentials
from launchpadlib.launchpad import Launchpad

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_owner", help="Name of source the ppa owner")
    parser.add_argument("source_ppa", help="Source ppa to copy from")
    parser.add_argument("dest_owner", help="Name of destination the ppa owner")
    parser.add_argument("dest_ppa", help="Destination ppa to copy to")

    return parser.parse_args(argv)


def get_launchpad_client() -> Launchpad:
    credentials = os.getenv("LP_CREDENTIALS")
    if not credentials:
        raise SystemExit("LP_CREDENTIALS environment variable missing")

    credentials = Credentials.from_string(credentials)
    return Launchpad(
        credentials, None, None, service_root="production", version="devel"
    )


def get_ppa(lp, ppa_name: str, ppa_owner: str):
    ppa_owner = lp.people[ppa_owner]
    return ppa_owner.getPPAByName(name=ppa_name)


def get_checkbox_packages(ppa):
    time_ago = datetime.datetime.now() - datetime.timedelta(weeks=4)
    # The time ago is needed because else LP api will choke trying to
    # return the full history including any published source in the ppa
    return ppa.getPublishedSource(
        created_since_date=time_ago, source_name="checkbox"
    )


def copy_checkbox_packages(source_ppa, source_owner, dest_ppa, dest_owner):
    """
    Copy Checkbox packages from a source PPA to a destination PPA without
    rebuilding.
    """
    lp = get_launchpad_client()

    source_ppa = get_ppa(lp, source_ppa, source_owner)
    dest_ppa = get_ppa(lp, dest_ppa, dest_owner)

    packages = get_checkbox_packages(source_ppa)

    # Copy each package from the source PPA to the destination PPA,
    # without rebuilding them
    for package in packages:
        dest_ppa.copyPackage(
            from_archive=source_ppa,
            include_binaries=True,
            to_pocket=package.pocket,
            source_name=package.source_package_name,
            version=package.source_package_version,
        )
        print(
            f"Copied {package.source_package_name} "
            f"version {package.source_package_version} "
            f"from {source_ppa} to {dest_ppa} "
            "(without rebuilding)"
        )


def main(argv):
    parsed = parse_args(argv)
    copy_checkbox_packages(
        parsed.source_ppa,
        parsed.source_owner,
        parsed.dest_ppa,
        parsed.dest_owner,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
