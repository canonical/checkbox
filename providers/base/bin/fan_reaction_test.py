#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#
# This is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this file.  If not, see <http://www.gnu.org/licenses/>.
"""
This program checks if the system's fans react to the CPU load applied.
"""

import glob
import hashlib
import multiprocessing
import os
import random
import time


class FanMonitor:
    """Device that reports fan RPM or something correlating to that."""
    def __init__(self):
        """Use heuristics to find something that we can read."""
        self.hwmons = []
        self._fan_paths = glob.glob('/sys/class/hwmon/hwmon*/fan*_input')
        # All entries (except name) under /sys/class/hwmon/hwmon/* are optional
        # and should only be created in a given driver if the chip has
        # the feature.
        # Use fan*_input is because the "thinkpad_hwmon" driver is report
        # fan_input only. If there is any driver has different implementation
        # then may need to check other entries in the future.
        for i in self._fan_paths:
            device = os.path.join(os.path.dirname(i), 'device')
            device_path = os.path.realpath(device)
            # Get the class of pci device of hwmon whether is GPU.
            if "pci" in device_path:
                pci_class_path = os.path.join(device, 'class')
                try:
                    with open(pci_class_path, 'r') as _file:
                        pci_class = _file.read().splitlines()
                        pci_device_class = (
                            int(pci_class[0], base=16) >> 16) & 0xff
                        """Make sure the fan is not on graphic card"""
                        if pci_device_class == 3:
                            continue
                except OSError:
                    print('Not able to access {}'.format(pci_class_path))
                    continue
            self.hwmons.append(i)
        if not self.hwmons:
            print('Fan monitoring interface not found in SysFS')
            raise SystemExit(0)

    def get_rpm(self):
        result = {}
        for p in self.hwmons:
            try:
                with open(p, 'rt') as f:
                    fan_mon_name = os.path.relpath(p, '/sys/class/hwmon')
                    result[fan_mon_name] = int(f.read())
            except OSError:
                print('Fan SysFS node disappeared ({})'.format(p))
        return result

    def get_average_rpm(self, period):
        acc = self.get_rpm()
        for i in range(period):
            time.sleep(1)
            rpms = self.get_rpm()
            for k, v in acc.items():
                acc[k] += rpms[k]
        for k, v in acc.items():
            acc[k] /= period + 1
        return acc


class Stressor:
    def __init__(self, thread_count=None):
        """Prepare the stressor."""
        if thread_count is None:
            thread_count = multiprocessing.cpu_count()
            print("Found {} CPU(s) in the system".format(thread_count))
        print("Will use #{} thread(s)".format(thread_count))
        self._thread_count = thread_count
        self._procs = []

    def start(self):
        """Start stress processes in the background."""
        for n in range(self._thread_count):
            self._procs.append(
                multiprocessing.Process(target=self._stress_fun))
            self._procs[-1].start()

    def stop(self):
        """Stop all running stress processes."""
        for proc in self._procs:
            proc.terminate()
            proc.join()
        self._procs = []

    def _stress_fun(self):
        """Actual stress function."""
        # generate some random data
        data = bytes(random.getrandbits(8) for _ in range(1024))
        hasher = hashlib.sha256()
        hasher.update(data)
        while True:
            new_digest = hasher.digest()
            # use the newly obtained digest as the new data to the hasher
            hasher.update(new_digest)


def main():
    """Entry point."""

    fan_mon = FanMonitor()
    stressor = Stressor()

    print("Precooling for 10s - no stress load")
    time.sleep(10)
    print("Measuring baseline fan speed")
    baseline_rpm = fan_mon.get_average_rpm(5)
    print("Launching stressor for 120s")
    stressor.start()
    for cycle in range(120):
        print("Cycle #{}, RPM={}".format(cycle, fan_mon.get_rpm()))
        time.sleep(1)
    print("Measuring an average fan speed over 5s")
    stress_rpm = fan_mon.get_average_rpm(5)
    print("Stopping stressor, waiting for 60s for system to cool off")
    stressor.stop()
    for cycle in range(60):
        print("Cycle #{}, RPM={}".format(cycle, fan_mon.get_rpm()))
        time.sleep(1)
    print("Measuring an average fan speed over 5s")
    end_rpm = fan_mon.get_average_rpm(5)

    had_a_fan_spinning = any((rpm > 0 for rpm in stress_rpm.values()))
    rpm_rose_during_stress = False
    rpm_dropped_during_cooling = False
    for fan_mon in sorted(baseline_rpm.keys()):
        if baseline_rpm[fan_mon]:
            stress_delta = (stress_rpm[fan_mon] / baseline_rpm[fan_mon])
        else:
            stress_delta = 999 if stress_rpm[fan_mon] > 0 else 0
        # if any of the fans raised rpms - similar to any()
        if not rpm_rose_during_stress:
            # XXX: this checks only if the rpms rose, not by how much
            #      we may want to introduce a threshold later on
            rpm_rose_during_stress = stress_delta > 0
        if not rpm_dropped_during_cooling:
            rpm_dropped_during_cooling = (
                end_rpm[fan_mon] < stress_rpm[fan_mon])

        print("{} RPM:".format(fan_mon))
        print("    baseline      : {:.2f}".format(baseline_rpm[fan_mon]))
        print("    during stress : {:.2f} ({:.2f}% of baseline)".format(
            stress_rpm[fan_mon], stress_delta * 100))
        print("    after stress  : {:.2f}".format(end_rpm[fan_mon]))
    if not had_a_fan_spinning:
        print("The system had no fans spinning during the test")
        return 0
    if rpm_rose_during_stress:
        print("RPM rose during the stress.")
    else:
        print("RPM did not rise during the stress!")
    if rpm_dropped_during_cooling:
        print("RPM dropped after the stress.")
    else:
        print("RPM did not drop after the stress!")
    # inverse logic, returning True would mean return code of 1
    if not (rpm_rose_during_stress and rpm_dropped_during_cooling):
        raise SystemExit("Fans did not react to stress expectedly")


if __name__ == '__main__':
    main()
