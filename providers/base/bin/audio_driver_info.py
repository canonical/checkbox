#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
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

import sys
import re

from argparse import ArgumentParser
from subprocess import check_output, STDOUT, CalledProcessError
from checkbox_support.parsers.modinfo import ModinfoParser

TYPES = ("source", "sink")

entries_regex = re.compile(r"index.*?(?=device.icon_name)", re.DOTALL)
driver_regex = re.compile(r"(?<=driver_name = )\"(.*)\"")
name_regex = re.compile(r"(?<=name:).*")


class PacmdAudioDevice:
    """
    Class representing an audio device with information gathered from pacmd
    """

    def __init__(self, name, driver):
        self._name = name
        self._driver = driver
        self._modinfo = self._modinfo_parser(driver)
        self._driver_version = self._find_driver_ver()

    def __str__(self):
        retstr = "Device: %s\n" % self._name
        if self._driver:
            retstr += "Driver: %s (%s)" % (self._driver, self._driver_version)
        else:
            retstr += "Driver: Unknown"
        return retstr

    def _modinfo_parser(self, driver):
        cmd = ["/sbin/modinfo", driver]
        try:
            stream = check_output(cmd, stderr=STDOUT, universal_newlines=True)
        except CalledProcessError as err:
            print("Error running %s:" % cmd, file=sys.stderr)
            print(err.output, file=sys.stderr)
            return None
        if not stream:
            print("Error: modinfo returned nothing", file=sys.stderr)
            return None
        else:
            parser = ModinfoParser(stream)
            modinfo = parser.get_all()

        return modinfo

    def _find_driver_ver(self):
        # try the version field first, then vermagic second, some audio
        # drivers don't report version if the driver is in-tree
        if self._modinfo["version"]:
            return self._modinfo["version"]
        else:
            # vermagic will look like this (below) and we only care about the
            # first part:
            # "3.2.0-29-generic SMP mod_unload modversions"
            return self._modinfo["vermagic"].split()[0]


def list_device_info():
    """
    Lists information on audio devices including device driver and version
    """

    retval = 0
    for vtype in TYPES:
        try:
            pacmd_entries = check_output(
                ["pacmd", "list-%ss" % vtype], universal_newlines=True
            )
        except Exception as e:
            print(
                "Error when running pacmd list-%ss: %s" % (vtype, e),
                file=sys.stderr,
            )
            return 1

        entries = entries_regex.findall(pacmd_entries)
        for entry in entries:
            name_match = name_regex.search(entry)
            if name_match:
                name = name_match.group().strip()
            else:
                print(
                    "Unable to determine device bus information from the"
                    " pacmd list-%ss output\npacmd output was: %s"
                    % (vtype, pacmd_entries),
                    file=sys.stderr,
                )
                return 1

            driver_name = driver_regex.findall(entry)
            if driver_name:
                driver = driver_name[0]
            else:
                driver = None

            print("%s\n" % PacmdAudioDevice(name, driver))

    return retval


def main():
    parser = ArgumentParser("List audio device and driver information")
    parser.parse_args()
    return list_device_info()


if __name__ == "__main__":
    sys.exit(main())
