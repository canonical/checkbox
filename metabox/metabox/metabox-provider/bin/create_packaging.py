#!/usr/bin/env python3
# Copyright (C) 2023 Canonical Ltd.
#
# Authors:
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from pathlib import Path
import subprocess

provider_dir = Path("/home/ubuntu/checkbox/metabox/metabox/metabox-provider")

# Run the script
subprocess.run(["./manage.py", "packaging"], cwd=provider_dir)

# Read the file
substvars_path = provider_dir / "debian/metabox-provider.substvars"
with open(substvars_path, "r") as myfile:
    data = myfile.read()
    print(data)

# Delete the file
os.remove(substvars_path)

SystemExit(0)
