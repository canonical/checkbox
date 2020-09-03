#!/usr/bin/env python3
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
#
import sys
import posixpath
import os

from checkbox_support.parsers.cpuinfo import CpuinfoParser

# Filename where cpuinfo is stored.
CPUINFO_FILENAME = "/proc/cpuinfo"

# Filename where maximum frequency is stored.
FREQUENCY_FILENAME = "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"

# Filename where available frequency governors are stored.
GOVERNORS_FILENAME = (
    "/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors")

# Files for indicating system lpi(low power idle) residency
SYSLPICHECK_FILENAMES = (
    "/sys/devices/system/cpu/cpuidle/low_power_idle_system_residency_us",
    "/sys/kernel/debug/pmc_core/slp_s0_residency_usec")

# Files for indicating Intel CPU lpi(low power idle) residency
CPULPICHECK_FILENAMES = (
    "/sys/devices/system/cpu/cpuidle/low_power_idle_cpu_residency_us",
    "/sys/kernel/debug/pmc_core/package_cstate_show")


class CpuinfoResult:

    def setProcessor(self, processor):
        for key, value in sorted(processor.items()):
            if key == "speed":
                # Check for frequency scaling
                if posixpath.exists(FREQUENCY_FILENAME):
                    value = open(FREQUENCY_FILENAME).read().strip()
                    value = int(value) // 1000
            if value:
                print("%s: %s" % (key, value))
        try:
            print("governors: %s" % open(GOVERNORS_FILENAME).read().strip())
        except FileNotFoundError:
            print("governors: GOVERNORS NOT FOUND")

        for fname in CPULPICHECK_FILENAMES:
            if posixpath.exists(fname):
                print("cpu_lpi_file: %s" % os.path.basename(fname))
                break

        for fname in SYSLPICHECK_FILENAMES:
            if posixpath.exists(fname):
                print("sys_lpi_file: %s" % os.path.basename(fname))
                break


def main():
    stream = open(CPUINFO_FILENAME)
    parser = CpuinfoParser(stream)

    result = CpuinfoResult()
    parser.run(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
