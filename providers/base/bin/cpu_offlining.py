#!/usr/bin/env python3

from glob import glob
from os.path import basename
from math import ceil
from time import sleep
import sys


def offline_cpu(cpu_name):
    with open('/sys/devices/system/cpu/{}/online'.format(cpu_name), 'wt') as f:
        f.write('0\n')


def online_cpu(cpu_name):
    with open('/sys/devices/system/cpu/{}/online'.format(cpu_name), 'wt') as f:
        f.write('1\n')


def is_cpu_online(cpu_name):
    # use the same heuristic as original `cpu_offlining` test used which is to
    # check if cpu is mentioned in /proc/interrupts
    with open('/proc/interrupts', 'rt') as f:
        header = f.readline().lower().split()
        return cpu_name in header


def main():
    cpus = [basename(x) for x in glob('/sys/devices/system/cpu/cpu[0-9]*')]
    # sort *numerically* cpus by their number, ignoring first 3 characters
    # so ['cpu1', 'cpu11', 'cpu2'] is sorted to ['cpu1', 'cpu2', 'cpu11']
    cpus.sort(key=lambda x: int(x[3:]))
    with open('/proc/interrupts', 'rt') as f:
        interrupts_count = len(f.readlines()) - 1  # first line is a header

    # there is an arch limit on how many interrupts one cpu can handle
    # according to LP: 1682328 it's 224. So we have to reserve some CPUs for
    # handling them
    max_ints_per_cpu = 224
    reserved_cpus_count = ceil(interrupts_count / max_ints_per_cpu)

    failed_offlines = []

    for cpu in cpus[reserved_cpus_count:]:
        offline_cpu(cpu)
        sleep(0.5)
        if is_cpu_online(cpu):
            print("ERROR: Failed to offline {}".format(cpu), file=sys.stderr)
            failed_offlines.append(cpu)

    failed_onlines = []

    for cpu in cpus[reserved_cpus_count:]:
        online_cpu(cpu)
        sleep(0.5)
        if not is_cpu_online(cpu):
            print("ERROR: Failed to online {}".format(cpu), file=sys.stderr)
            failed_onlines.append(cpu)

    if not failed_offlines and not failed_onlines:
        print("Successfully turned {} cores off and back on".format(
            len(cpus) - reserved_cpus_count))
        return 0
    else:
        print("Error with offlining one or more cores.  CPU offline may not "
              "work if this is an ARM system.", file=sys.stderr)
        print(' '.join(failed_offlines))
        print(' '.join(failed_onlines))
        return 1


if __name__ == '__main__':
    main()
