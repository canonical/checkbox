#!/usr/bin/env python3
"""
cpu_topology.py
Written by Jeffrey Lane <jeffrey.lane@canonical.com>
"""
import sys
import os
import re


class proc_cpuinfo:
    """
    Class to get and handle information from /proc/cpuinfo
    Creates a dictionary of data gleaned from that file.
    """

    def __init__(self):
        self.cpuinfo = {}
        cpu_fh = open("/proc/cpuinfo", "r")
        try:
            temp = cpu_fh.readlines()
        finally:
            cpu_fh.close()

        r_s390 = re.compile(r"processor [0-9]")
        r_x86 = re.compile(r"processor\s+:")
        for i in temp:
            # Handle s390 first
            if r_s390.match(i):
                cpu_num = i.split(":")[0].split()[1].strip()
                key = "cpu" + cpu_num
                self.cpuinfo[key] = {
                    "core_id": cpu_num,
                    "physical_package_id": cpu_num,
                }
            elif r_x86.match(i):
                key = "cpu" + (i.split(":")[1].strip())
                self.cpuinfo[key] = {"core_id": "", "physical_package_id": ""}
            elif i.startswith("core id"):
                self.cpuinfo[key].update({"core_id": i.split(":")[1].strip()})
            elif i.startswith("physical id"):
                self.cpuinfo[key].update(
                    {"physical_package_id": i.split(":")[1].strip()}
                )
            else:
                continue


class sysfs_cpu:
    """
    Class to get and handle information from sysfs as relates to CPU topology
    Creates an informational class to present information on various CPUs
    """

    def __init__(self, proc):
        self.syscpu = {}
        self.path = "/sys/devices/system/cpu/" + proc + "/topology"
        items = ["core_id", "physical_package_id"]
        for i in items:
            try:
                syscpu_fh = open(os.path.join(self.path, i), "r")
            except OSError as e:
                print("ERROR: %s" % e)
                sys.exit(1)
            else:
                self.syscpu[i] = syscpu_fh.readline().strip()
                syscpu_fh.close()


def compare(proc_cpu, sys_cpu):
    cpu_map = {}
    """
    If there is only 1 CPU the test don't look for core_id
    and physical_package_id because those information are absent in
    /proc/cpuinfo on singlecore system
    """
    for key in proc_cpu.keys():
        if "cpu1" not in proc_cpu:
            cpu_map[key] = True
        else:
            for subkey in proc_cpu[key].keys():
                if proc_cpu[key][subkey] == sys_cpu[key][subkey]:
                    cpu_map[key] = True
                else:
                    cpu_map[key] = False
    return cpu_map


def main():
    cpuinfo = proc_cpuinfo()
    sys_cpu = {}
    keys = cpuinfo.cpuinfo.keys()
    for k in keys:
        sys_cpu[k] = sysfs_cpu(k).syscpu
    cpu_map = compare(cpuinfo.cpuinfo, sys_cpu)
    if False in cpu_map.values() or len(cpu_map) < 1:
        print("FAIL: CPU Topology is incorrect", file=sys.stderr)
        print("-" * 52, file=sys.stderr)
        print(
            "{0}{1}".format("/proc/cpuinfo".center(30), "sysfs".center(25)),
            file=sys.stderr,
        )
        print(
            "{0}{1}{2}{3}{1}{2}".format(
                "CPU".center(6),
                "Physical ID".center(13),
                "Core ID".center(9),
                "|".center(3),
            ),
            file=sys.stderr,
        )
        for key in sorted(sys_cpu.keys()):
            print(
                "{0}{1}{2}{3}{4}{5}".format(
                    key.center(6),
                    cpuinfo.cpuinfo[key]["physical_package_id"].center(13),
                    cpuinfo.cpuinfo[key]["core_id"].center(9),
                    "|".center(3),
                    sys_cpu[key]["physical_package_id"].center(13),
                    sys_cpu[key]["core_id"].center(9),
                ),
                file=sys.stderr,
            )
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
