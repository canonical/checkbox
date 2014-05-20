#
# This file is part of Checkbox.
#
# Copyright 2011 Canonical Ltd.
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from os import uname
import re

from checkbox_support.lib.conversion import string_to_type


class CpuinfoParser(object):
    """Parser for the /proc/cpuinfo file."""

    def __init__(self, stream, machine=None):
        self.stream = stream
        self.machine = machine or uname()[4].lower()

    def getAttributes(self):
        count = 0
        attributes = {}
        cpuinfo = self.stream.read()
        for block in re.split(r"\n{2,}", cpuinfo):
            block = block.strip()
            if not block:
                continue

            for line in block.split("\n"):
                if not line:
                    continue
                key, value = line.split(":", 1)
                key, value = key.strip(), value.strip()

                if key == 'processor':
                    count += 1

                # Handle bogomips on sparc
                if key.endswith("Bogo"):
                    key = "bogomips"

                # Handle version on ppc
                if self.machine[:3] == "ppc" and key == 'revision':
                    value, version_value = value.split("(", 1)
                    attributes["version"] = version_value[:-1]

                attributes[key] = value

        if attributes:
            attributes["count"] = count

        return attributes

    def run(self, result):
        attributes = self.getAttributes()
        if not attributes:
            return

        # Default values
        machine = self.machine
        processor = {
            "platform": machine,
            "count": 1,
            "type": machine,
            "model": machine,
            "model_number": "",
            "model_version": "",
            "model_revision": "",
            "cache": 0,
            "bogomips": 0,
            "speed": -1,
            "other": ""}

        # Conversion table
        platform_to_conversion = {
            ("i386", "i486", "i586", "i686", "x86_64",): {
                "type": "vendor_id",
                "model": "model name",
                "model_number": "cpu family",
                "model_version": "model",
                "model_revision": "stepping",
                "cache": "cache size",
                "other": "flags",
                "speed": "cpu MHz"},
            ("alpha", "alphaev6",): {
                "count": "cpus detected",
                "type": "cpu",
                "model": "cpu model",
                "model_number": "cpu variation",
                "model_version": ("system type", "system variation",),
                "model_revision": "cpu revision",
                "other": "platform string",
                "speed": "cycle frequency [Hz]"},
            ("armv7l",): {
                "type": "Hardware",
                "model": "Processor",
                "model_number": "CPU variant",
                "model_version": "CPU architecture",
                "model_revision": "CPU revision",
                "other": "Features",
                "bogomips": "BogoMIPS"},
            ("ia64",): {
                "type": "vendor",
                "model": "family",
                "model_version": "archrev",
                "model_revision": "revision",
                "other": "features",
                "speed": "cpu mhz"},
            ("ppc64", "ppc64le", "ppc",): {
                "type": "platform",
                "model": "cpu",
                "model_number": "model",
                "model_version": "version",
                "model_revision": "revision",
                "other": "firmware",
                "speed": "clock"},
            ("sparc64", "sparc",): {
                "count": "ncpus probed",
                "type": "type",
                "model": "cpu",
                "model_version": "type",
                "speed": "bogomips"}}

        for key in processor:
            if attributes.get(key):
                processor[key] = attributes.get(key)

        for platform, conversion in platform_to_conversion.items():
            if machine in platform:
                for pkey, ckey in conversion.items():
                    if isinstance(ckey, (list, tuple)):
                        processor[pkey] = "/".join([attributes[k]
                                                    for k in ckey])
                    elif ckey in attributes:
                        processor[pkey] = attributes[ckey]

        # Adjust platform
        if machine[0] == "i" and machine[-2:] == "86":
            processor["platform"] = "i386"
        elif machine[:5] == "alpha":
            processor["platform"] = "alpha"

        # Adjust cache
        if processor["cache"]:
            processor["cache"] = string_to_type(processor["cache"])

        # Adjust speed
        try:
            if machine[:5] == "alpha":
                speed = processor["speed"].split()[0]
                processor["speed"] = int(round(float(speed))) / 1000000
            elif machine[:5] == "sparc":
                speed = processor["speed"]
                processor["speed"] = int(round(float(speed))) / 2
            elif machine[:3] == "ppc":
                # String is appended with "mhz"
                processor["speed"] = processor["speed"][:-3]
        except ValueError:
            processor["speed"] = -1

        # Make sure speed and bogomips are integers
        processor["speed"] = int(round(float(processor["speed"])) - 1)
        processor["bogomips"] = int(round(float(processor["bogomips"])))

        # Adjust other for ppc.  Firmware is empty for VM.
        if machine[:3] == "ppc" and processor["model_number"][13:-1] == \
                "emulated by qemu":
            processor["other"] = processor["model_number"][13:-1]

        # Adjust count
        try:
            processor["count"] = int(processor["count"])
        except ValueError:
            processor["count"] = 1
        else:
            # There is at least one processor
            if processor["count"] == 0:
                processor["count"] = 1

        result.setProcessor(processor)
