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
import sys
import re
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
    desc_regex = re.compile('System Memory', re.IGNORECASE)

    def addHardware(self, hardware):
        if self.desc_regex.match(str(hardware.get('description', 0))):
            self.memory_reported += int(hardware.get('size', 0))
        elif 'bank' in hardware['id']:
            self.banks_reported += int(hardware.get('size', 0))


def get_installed_memory_size():
    try:
        output = check_output(['lshw', '-json'],
                              universal_newlines=True,
                              stderr=PIPE)
    except CalledProcessError:
        return 0
    lshw = LshwJsonParser(output)
    result = LshwJsonResult()
    lshw.run(result)

    if result.memory_reported:
        return result.memory_reported
    else:
        return result.banks_reported

# Return 0, if not found the memory for amdgpu
# Return >0, reserved vram for amdgpu
def get_amdgpu_gpu_vram(addr=None):
    size = 0
    if addr is None:
        return size
    path = "/sys/module/amdgpu/drivers/pci:amdgpu/%s" % addr
    if not os.path.isfile("%s/mem_info_vram_total" % path):
        return size
    with open('%s/mem_info_vram_total' % path) as vram:
        size = int(vram.read())
        size = int(size / (1024 * 1024))
    return size

# Return 0, if not found the memory for the pci device
# Return >0, reserved memory for the pci device
def get_allocated_pci_memory(addr=None):
    if addr is None:
        return 0
    try:
        lspci = check_output(['lspci', '-v', '-s', addr], universal_newlines=True)
    except CalledProcessError as exc:
        return exc.returncode

    size = 0

    for line in lspci.split('\n'):
        # Skip G, K and lower than K, if lspci changes the format and
        # this needs to be adjusted. So far, in 4G allocation, it shows
        # in M (mega-bytes).
        match = re.search('(.*)prefetchable\)(.*)\[size=(.*)M\](.*)', line)
        if match is not None:
            size += int(match.group(3))
        match = re.search('(.*)prefetchable\)(.*)\[size=(.*)G\](.*)', line)
        if match is not None:
            size += int(match.group(3)) * 1024

    return size

# Get the FW allocated memory for PCI based GPU
# Returns >= 0 allocated RAM size for PCI based gpu in mega-bytes
# Returns -1 if failed, either ARM or related utilities not found
def get_allocated_memory_for_each_pci_gpu():
    try:
        arch = check_output(['arch'], universal_newlines=True).strip()
    except CalledProcessError as exc:
        return exc.returncode

    # If ARM, then exit
    if arch != 'x86_64':
        return 1

    try:
        lspci = check_output(['lspci', '-v'], universal_newlines=True)
    except CalledProcessError as exc:
        return exc.returncode

    size = 0

    pci_bus = "/sys/bus/pci/devices/"
    drivers = ['nvidia', 'amdgpu', 'i915', 'radeon']
    for driver in drivers:
        path = "/sys/module/%s/drivers/pci:%s/" % (driver, driver)
        if not os.path.exists(path):
            continue
        for f in os.scandir(path):
            if not f.is_dir():
                continue
            if not re.match(r'\d{4}:\d{2}:\d{2}.\d{1}', f.name):
                continue
            if driver == 'amdgpu':
                val = get_amdgpu_gpu_vram(f.name)
            else:
                val = get_allocated_pci_memory(f.name)
            print("INFO: Found %s MB memory for %s gpu" % (val, driver))
            size += val

    return size

class MeminfoResult:

    memtotal = 0

    def setMemory(self, memory):
        self.memtotal = memory['total']

def get_visible_memory_size():
    parser = MeminfoParser(open('/proc/meminfo'))
    result = MeminfoResult()
    parser.run(result)

    return result.memtotal

def get_threshold(installed_memory):
    GB = 1024**3
    if installed_memory <= 2 * GB:
        return 25
    elif installed_memory <= 6 * GB:
        return 20
    else:
        return 10


def main():
    if os.geteuid() != 0:
        print("This script must be run as root.", file=sys.stderr)
        return 1

    installed_memory = HumanReadableBytes(get_installed_memory_size())
    fw_allocated_memory_for_pci = get_allocated_memory_for_each_pci_gpu();
    visible_memory = HumanReadableBytes(get_visible_memory_size())
    threshold = get_threshold(installed_memory)

    if fw_allocated_memory_for_pci >= 0:
        difference = HumanReadableBytes(installed_memory - visible_memory -
                fw_allocated_memory_for_pci * 1024 * 1024)
    else:
        difference = HumanReadableBytes(installed_memory - visible_memory)
    try:
        percentage = difference / installed_memory * 100
    except ZeroDivisionError:
        print("Results:")
        print("\t/proc/meminfo reports:\t{}".format(visible_memory),
              file=sys.stderr)
        print("\tlshw reports:\t{}".format(installed_memory),
              file=sys.stderr)
        print("\nFAIL: Either lshw or /proc/meminfo returned a memory size "
              "of 0 kB", file=sys.stderr)
        return 1

    if percentage <= threshold:
        print("Results:")
        print("\t/proc/meminfo reports:\t{}".format(visible_memory))
        print("\tlshw reports:\t{}".format(installed_memory))
        print("\tFound FW allocated %d MB for PCI GPUs" %
                fw_allocated_memory_for_pci)
        print("\nPASS: Meminfo reports %s less than lshw, a "
              "difference of %.2f%%. This is less than the "
              "%d%% variance allowed." % (difference, percentage, threshold))
        return 0
    else:
        print("Results:", file=sys.stderr)
        print("\t/proc/meminfo reports:\t{}".format(visible_memory),
              file=sys.stderr)
        print("\tlshw reports:\t{}".format(installed_memory), file=sys.stderr)
        print("\tFound FW allocated %d MB for PCI GPUs" %
                fw_allocated_memory_for_pci)
        print("\nFAIL: Meminfo reports %d less than lshw, "
              "a difference of %.2f%%. Only a variance of %d%% in "
              "reported memory is allowed." %
              (difference, percentage, threshold), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
