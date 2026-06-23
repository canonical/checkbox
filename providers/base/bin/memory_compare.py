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
            ["lshw", "-json"], universal_newlines=True, stderr=PIPE
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


VRAM_REPORTED_RE = re.compile(r"\bVRAM:\s*(\d+)\s*([KMGT])\b")
VRAM_USED_RE = re.compile(r"\((\d+)\s*([KMGT])\s+used\)")
VRAM_RAM_RE = re.compile(r"\bVRAM RAM=(\d+)\s*([KMGT])\b")


def _memory_size_to_bytes(size, unit):
    unit = unit.upper()
    multipliers = {
        "K": 1024,
        "M": 1024**2,
        "G": 1024**3,
        "T": 1024**4,
    }
    return int(size) * multipliers[unit]


def get_igpu_vram_size_from_dmesg(dmesg_output):
    used_vram_sizes = []
    vram_sizes = []
    for line in dmesg_output.splitlines():
        used_match = VRAM_USED_RE.search(line)
        if used_match:
            used_vram_sizes.append(
                _memory_size_to_bytes(
                    used_match.group(1), used_match.group(2)
                )
            )
            continue

        for regex in (VRAM_RAM_RE, VRAM_REPORTED_RE):
            match = regex.search(line)
            if match:
                vram_sizes.append(
                    _memory_size_to_bytes(match.group(1), match.group(2))
                )
                break

    if used_vram_sizes:
        return max(used_vram_sizes)
    if vram_sizes:
        return max(vram_sizes)
    return 0


def get_igpu_vram_size():
    commands = (
        ["dmesg"],
        ["journalctl", "-k", "-b", "--no-pager"],
    )
    for command in commands:
        output = get_kernel_log(command)
        vram_size = get_igpu_vram_size_from_dmesg(output)
        if vram_size:
            return vram_size
    return 0


def get_kernel_log(command):
    try:
        return check_output(command, universal_newlines=True, stderr=PIPE)
    except (CalledProcessError, FileNotFoundError, PermissionError):
        return ""


def get_adjusted_memory_difference(
    installed_memory, visible_memory, igpu_vram
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
            installed_memory, visible_memory, igpu_vram
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
            "\nFAIL: Either lshw or /proc/meminfo returned a memory size "
            "of 0 kB",
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
            "a difference of %.2f%%. Only a variance of %d%% in "
            "reported memory is allowed."
            % (difference, percentage, threshold),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
