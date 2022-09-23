#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2009-2021 Canonical Ltd.
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
import re
import subprocess
import sys


def get_info():
    lsb_release = {}

    try:
        import distro
        lsb_release = {
            "distributor_id": distro.name(pretty=False) or "unknown",
            "description": distro.name(pretty=True) or "unknown",
            "release": distro.version() or "unknown",
            "codename": distro.codename() or "unknown"
        }
    except (ImportError, subprocess.CalledProcessError):
        lsb_release_map = {
            "DISTRIB_ID": "distributor_id",
            "DISTRIB_DESCRIPTION": "description",
            "DISTRIB_RELEASE": "release",
            "DISTRIB_CODENAME": "codename"}

        # Create a default lsb_release() dict in case something goes wrong
        lsb_release = dict((k, 'unknown') for k in lsb_release_map.values())

        try:
            with open('/etc/lsb-release', 'r') as lsb:
                for line in lsb.readlines():
                    (key, value) = line.split("=", 1)
                    if key in lsb_release_map:
                        key = lsb_release_map[key]
                        # Strip out quotes and newlines
                        lsb_release[key] = re.sub('["\n]', '', value)
        except OSError:
            # Missing file or permissions? Return the default lsb_release
            pass

    return lsb_release


def main():
    release_info = get_info()
    for key, value in release_info.items():
        print("%s: %s" % (key, value))

    return 0


if __name__ == "__main__":
    sys.exit(main())
