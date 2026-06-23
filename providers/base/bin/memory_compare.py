#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
#
# Authors:
#    Brendan Donegan <brendan.donegan@canonical.com>
#    Jeff Lane <jeff.lane@canonical.com>
#    Sylvain Pineau <sylvain.pineau@canonical.com>
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

import os
import re
import sys
from subprocess import check_output, CalledProcessError, PIPE

from checkbox_support.helpers.human_readable_bytes import HumanReadableBytes
from checkbox_support.parsers.lshwjson import LshwJsonParser
from checkbox_support.parsers.meminfo import MeminfoParser


class LshwJsonResult:
    memory_reported = 0
    banks_reported = 0

    # jlane LP:1525009
    # Discovered the case can change, my x86 systems used "System Memory"
    # Failing ARM system used "System memory"
    desc_regex = re.compile("System Memory", re.IGNORECASE)

    def addHardware(self, hardware):
        if self.desc_regex.match(str(hardware.get("description", 0))):
            self.memory_reported += int(hardware.get("size", 0))
        elif "bank" in hardware["id"]:
            self.banks_reported += int(hardware.get("size", 0))


def get_installed_memory_size():
    try:
        output = check_output(
            ["lshw", "-json"],
            universal_newlines=True,
            stderr=PIPE,
        )
    except CalledProcessError:
        return 0
    lshw = LshwJsonParser(output)
    result = LshwJsonResult()
    lshw.run(result)

    if result.memory_reported:
        return result.memory_reported
    else:
        return result.banks_reported


def get_visible_memory_size():
    parser = MeminfoParser()
    meminfo = parser.run()

    return meminfo["total"]


def _memory_size_to_bytes(size, unit):
    unit = unit.upper()
    multipliers = {
        "K": 1024,
        "M": 1024**2,
        "G": 1024**3,
        "T": 1024**4,
    }
    return int(size) * multipliers[unit]


def get_igpu_vram_size_from_kernel_log(kernel_log):

    # Example:
    #   amdgpu ... VRAM: 4096M ... (4096M used)
    # Captured groups:
    #   group 1: "4096" (size), group 2: "M" (unit)
    VRAM_USED_RE = re.compile(r"\((\d+)\s*([KMGT])\s+used\)")
    used_vram_sizes = [
        _memory_size_to_bytes(match.group(1), match.group(2))
        for match in VRAM_USED_RE.finditer(kernel_log)
    ]
    return max(used_vram_sizes, default=0)


def get_igpu_vram_size():
    JOURNALCTL_COMMAND = "journalctl -k -b --no-pager | grep -C10 VRAM"

    try:
        vram_output = check_output(
            JOURNALCTL_COMMAND,
            universal_newlines=True,
            stderr=PIPE,
            shell=True,
        )

    except (CalledProcessError, FileNotFoundError, PermissionError) as e:
        print("Failed to get kernel log output: {}".format(e), file=sys.stderr)
        return 0

    if vram_output:
        print("Kernel VRAM log output:\n{}".format(vram_output))
    return get_igpu_vram_size_from_kernel_log(vram_output)


def get_adjusted_memory_difference(
    installed_memory,
    visible_memory,
    igpu_vram,
):
    difference = installed_memory - visible_memory
    if difference <= 0:
        return 0
    return difference - min(igpu_vram, difference)


def get_threshold(installed_memory):
    GB = 1024**3
    if installed_memory <= 2 * GB:
        return 25
    elif installed_memory <= 6 * GB:
        return 20
    elif installed_memory <= 8 * GB:
        return 15
    elif installed_memory <= 16 * GB:
        return 12
    else:
        return 10


def main():
    if os.geteuid() != 0:
        print("This script must be run as root.", file=sys.stderr)
        return 1

    installed_memory = HumanReadableBytes(get_installed_memory_size())
    visible_memory = HumanReadableBytes(get_visible_memory_size())
    igpu_vram = HumanReadableBytes(get_igpu_vram_size())
    threshold = get_threshold(installed_memory)

    difference = HumanReadableBytes(
        get_adjusted_memory_difference(
            installed_memory,
            visible_memory,
            igpu_vram,
        )
    )
    try:
        percentage = difference / installed_memory * 100
    except ZeroDivisionError:
        print("Results:")
        print(
            "\t/proc/meminfo reports:\t{}".format(visible_memory),
            file=sys.stderr,
        )
        print("\tlshw reports:\t{}".format(installed_memory), file=sys.stderr)
        print(
            "\nFAIL: Either lshw or /proc/meminfo returned a size of 0 kB",
            file=sys.stderr,
        )
        return 1

    if percentage <= threshold:
        print("Results:")
        print("\t/proc/meminfo reports:\t{}".format(visible_memory))
        print("\tlshw reports:\t{}".format(installed_memory))
        if igpu_vram:
            print("\tiGPU VRAM compensation:\t{}".format(igpu_vram))
        print(
            "\nPASS: Meminfo reports %s less than lshw, a "
            "difference of %.2f%%. This is less than the "
            "%d%% variance allowed." % (difference, percentage, threshold)
        )
        return 0
    else:
        print("Results:", file=sys.stderr)
        print(
            "\t/proc/meminfo reports:\t{}".format(visible_memory),
            file=sys.stderr,
        )
        print("\tlshw reports:\t{}".format(installed_memory), file=sys.stderr)
        if igpu_vram:
            print(
                "\tiGPU VRAM compensation:\t{}".format(igpu_vram),
                file=sys.stderr,
            )
        print(
            "\nFAIL: Meminfo reports %d less than lshw, "
            "a difference of %.2f%%. Only a variance of %d%% in reported "
            "memory is allowed." % (difference, percentage, threshold),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
