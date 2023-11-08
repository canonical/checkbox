#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
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

import datetime
import os

from launchpadlib.credentials import Credentials
from launchpadlib.launchpad import Launchpad

# Authenticate with Launchpad
credentials = Credentials.from_string(os.getenv("LP_CREDENTIALS"))
lp = Launchpad(
    credentials, None, None, service_root="production", version="devel")

# Define the source and destination PPAs
source_ppa_name = "testing"
source_owner_name = "checkbox-dev"
dest_ppa_name = "public"
dest_owner_name = "hardware-certification"

# Load the source and destination PPA owners
source_owner = lp.people[source_owner_name]
dest_owner = lp.people[dest_owner_name]

# Get the source and destination PPAs
source_ppa = source_owner.getPPAByName(name=source_ppa_name)
dest_ppa = dest_owner.getPPAByName(name=dest_ppa_name)

# Define the time period for package publication
one_week_ago = datetime.datetime.utcnow().replace(
    tzinfo=datetime.timezone.utc
) - datetime.timedelta(weeks=4)

# Get the packages in the source PPA that were published within the last week
# and start with "checkbox"
packages = [
    p
    for p in source_ppa.getPublishedSources(created_since_date=one_week_ago)
    if p.source_package_name.startswith("checkbox")
]

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
        f"from {source_ppa_name} to {dest_ppa_name} (without rebuilding)"
    )
