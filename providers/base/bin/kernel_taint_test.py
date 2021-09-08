#!/usr/bin/env python3
"""
Test that the kernel is not "tainted" by out-of-tree drivers, etc.

Copyright (C) 2019 Canonical Ltd.

Authors:
  Rod Smith <rod.smith@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

This script examines the /proc/sys/kernel/tainted file (or a user-specified
file, for debugging purposes) and parses the contents to determine if the
kernel is tainted. If so, the script reports the nature of the taint and
returns a value of 1. The script also returns a value of 1 if
# /proc/sys/kernel/tainted cannot be found or opened. If the kernel is NOT
# tainted, the script notes this fact and returns 0.
"""


import sys
import shlex
from argparse import ArgumentParser
from subprocess import check_output

# Note: If max_taints is increased, add descriptions to taint_meanings in
# report_failures()
max_taints = 17


def find_taints(taint_file):
    """Read the kernel-taint file."""
    try:
        f = open(taint_file, "r")
        taints = int(f.read())
    except OSError:
        raise SystemExit(
            "Kernel taint file ({}) not found!".format(taint_file))
    print("Kernel taint value is {}".format(taints))
    return taints


def get_modules():
    lsmod_output = check_output('lsmod', universal_newlines=True).split('\n')
    # get only the module names
    modules = []
    for line in lsmod_output:
        if line and 'Module' not in line:
            modules.append(line.split()[0])
    return modules


def process_out_of_tree_modules(modules):
    mod_list = []
    modules = remove_ignored_modules(modules)
    for mod in modules:
        cmd = 'modinfo -F intree %s' % mod
        if not check_output(shlex.split(cmd),
                            universal_newlines=True):
            mod_list.append(mod)
    return mod_list


def process_GPL_incompatible_modules(modules):
    mod_list = []
    modules = remove_ignored_modules(modules)
    for mod in modules:
        cmd = 'modinfo -F license %s' % mod
        license = check_output(shlex.split(cmd),
                               universal_newlines=True).strip()
        if "GPL" not in license and "MIT" not in license:
            mod_list.append((mod, license))
    return mod_list


def remove_ignored_modules(modules):
    # Remove modules we know will fail, but accept
    ignored_modules = ['icp',
                       'spl',
                       'zavl',
                       'zcommon',
                       'zfs',
                       'zlua',
                       'znvpair',
                       'zunicode',
                       'zzstd']
    for ignore_mod in ignored_modules:
        try:
            modules.remove(ignore_mod)
        except ValueError:
            pass
    return modules


def main():
    """Print out the tainted state code and its meaning(s)."""
    parser = ArgumentParser()
    parser.add_argument('--taint-file',
                        default="/proc/sys/kernel/tainted",
                        help='The file that holds the taint information')
    args = parser.parse_args()
    taints = find_taints(args.taint_file)

    # Below meaning strings are taken from
    # https://www.kernel.org/doc/html/latest/admin-guide/tainted-kernels.html
    taint_meanings = ["proprietary module was loaded",
                      "module was force loaded",
                      "SMP kernel oops on an officially SMP incapable CPU",
                      "module was force unloaded",
                      "processor reported a Machine Check Exception (MCE)",
                      "bad page referenced or some unexpected page flags",
                      "taint requested by userspace application",
                      "kernel died recently, i.e. there was an OOPS or BUG",
                      "ACPI table overridden by user",
                      "kernel issued warning",
                      "staging driver was loaded",
                      "workaround for bug in platform firmware applied",
                      "externally-built ('out-of-tree') module was loaded",
                      "unsigned module was loaded",
                      "soft lockup occurred",
                      "kernel has been live patched",
                      "auxiliary taint, defined for and used by distros",
                      "kernel was built with the struct randomization plugin"]
    count = 0
    for i in range(max_taints+1):
        if (taints & (2 ** i)):
            modules = get_modules()
            print("Taint bit value: {} ({})".format(i, taint_meanings[i]))
            if i == 0:  # List GPL incompatible modules and licenses
                proprietary_modules = process_GPL_incompatible_modules(modules)
                if proprietary_modules:
                    print("*   Modules with GPL Incompatible Licenses:")
                    for mod in proprietary_modules:
                        print("     %s: %s" % (mod[0], mod[1]))
                    count += 1
                else:
                    print("*   Proprietary modules found, "
                          "but they are expected and OK")
            elif i == 11:
                print("*   Firmware workarounds are expected and OK")
            elif i == 12:  # List out-of-tree modules
                out_of_tree_modules = process_out_of_tree_modules(modules)
                if len(out_of_tree_modules) > 0:
                    print("*   Modules not in-tree:")
                    for mod in out_of_tree_modules:
                        print("     %s" % mod)
                    count += 1
                else:
                    print("*   Out of Tree modules found, "
                          "but they are expected and OK")
            else:
                count += 1

    if count == 0:
        # else case below contains expected issue in case 0 / 11 / 12
        if not taints:
            print("No kernel taints detected.")
        return 0
    else:
        return 1


if __name__ == '__main__':
    sys.exit(main())
