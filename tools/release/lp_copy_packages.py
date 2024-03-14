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
import sys
import datetime
import argparse
import itertools

from utils import get_launchpad_client


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_owner", help="Name of source the ppa owner")
    parser.add_argument("source_ppa", help="Source ppa to copy from")
    parser.add_argument("dest_owner", help="Name of destination the ppa owner")
    parser.add_argument("dest_ppa", help="Destination ppa to copy to")

    return parser.parse_args(argv)


def get_ppa(lp, ppa_name: str, ppa_owner: str):
    ppa_owner = lp.people[ppa_owner]
    return ppa_owner.getPPAByName(name=ppa_name)


def get_checkbox_packages(ppa):
    """
    Get all the most recent checkbox packages on the PPA that are still current

    A source package is still current when it has not been superseeded by
    another. The filtering here is done to avoid copying over outdated
    packages to the target PPA
    """
    # Note: this is not the same as ppa.getPublishedSources(status="Published")
    #       the reason is that if a package is Published but for a not
    #       supported distribution, say Lunar, copying it over will trigger an
    #       error. When a distribution support is dropped, Launchpad will
    #       automatically stop building for it and start a grace period for
    #       updates. This ensures there will always be a pocket of Superseeded
    #       packages between Published packages for unsupported distro and
    #       current ones
    all_published_sources = ppa.getPublishedSources(
        source_name="checkbox", order_by_date=True
    )
    # this filters out superseeded packages AND Published packages that are no
    # longer current (as they are not being built anymore by Launchpad)
    return itertools.takewhile(
        lambda x: x.date_superseded is None, all_published_sources
    )


def copy_checkbox_packages(source_owner, source_ppa, dest_owner, dest_ppa):
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
    args = parse_args(argv)
    copy_checkbox_packages(
        args.source_owner,
        args.source_ppa,
        args.dest_owner,
        args.dest_ppa,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
