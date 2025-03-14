#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2009-2025 Canonical Ltd.
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
import sys
from contextlib import suppress


def get_release_file_content():
    with suppress(FileNotFoundError):
        with open("/var/lib/snapd/hostfs/etc/os-release", "r") as fp:
            return fp.read()
    with open("/etc/os-release", "r") as fp:
        return fp.read()


def get_release_info(release_file_content: str):
    os_release_map = {
        "NAME": "distributor_id",
        "PRETTY_NAME": "description",
        "VERSION_ID": "release",
        "VERSION_CODENAME": "codename",
    }
    os_release = {}
    lines = filter(bool, release_file_content.strip().splitlines())
    for line in lines:
        (key, value) = line.split("=", 1)
        if key in os_release_map:
            k = os_release_map[key]
            # Strip out quotes and newlines
            os_release[k] = re.sub('["\n]', "", value)
    # this is needed by C3, on core there is no VERSION_CODENAME, lets put
    # description here by default which will yield
    os_release["codename"] = os_release.get(
        "codename", os_release.get("description", "unknown")
    )
    return os_release


def main():
    release_file_content = get_release_file_content()
    release_info = get_release_info(release_file_content)
    for key, value in release_info.items():
        print("%s: %s" % (key, value))


if __name__ == "__main__":
    sys.exit(main())
