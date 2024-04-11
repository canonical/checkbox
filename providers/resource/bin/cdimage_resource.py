#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2009 Canonical Ltd.
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


# Filename containing casper logs
CASPER_FILENAME = "/var/log/installer/casper.log"

# Filename containing media info
MEDIA_FILENAME = "/var/log/installer/media-info"


def get_disk_from_string(string):
    # Ubuntu 8.04.1 "Hardy Heron" - Release amd64 (20080702.1)
    # Ubuntu 10.04.2 LTS "Lucid Lynx" - Release amd64 (20110227.2)
    distributor_regex = r"(?P<distributor>[\w\-]+)"
    release_regex = r"(?P<release>[\d\.]+( LTS)?)"
    codename_regex = r"(?P<codename>[^_\"]+)"
    official_regex = r"(?P<official>[\w ]+)"
    architecture_regex = r"(?P<architecture>[\w\+]+)"
    type_regex = r"(?P<type>Binary-\d+)"
    date_regex = r"(?P<date>[^\)]+)"

    string_regex = r"%s %s [_\"]%s[_\"] - %s %s (%s )?\(%s\)" % (
        distributor_regex,
        release_regex,
        codename_regex,
        official_regex,
        architecture_regex,
        type_regex,
        date_regex,
    )

    disk = {}
    match = re.match(string_regex, string)
    if match:
        disk = match.groupdict()
        del disk["type"]

    return disk


def get_disk_from_casper(filename):
    disk = {}

    # Try to open the disk info file logged by the installer
    try:
        file = open(filename)
    except IOError:
        return disk

    line_regex = r"Found label '(?P<string>[^']+)'"
    line_pattern = re.compile(line_regex)

    for line in file.readlines():
        match = line_pattern.match(line)
        if match:
            string = match.group("string")
            disk = get_disk_from_string(string)
            break

    return disk


def get_disk_from_media(filename):
    try:
        file = open(filename)
    except IOError:
        return {}

    string = file.readline()
    return get_disk_from_string(string)


def main():
    disk = get_disk_from_media(MEDIA_FILENAME)
    if not disk:
        disk = get_disk_from_casper(CASPER_FILENAME)

    for key, value in disk.items():
        print("%s: %s" % (key, value))

    return 0


if __name__ == "__main__":
    sys.exit(main())
