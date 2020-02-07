#!/usr/bin/env python3
# Copyright 2015-2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Jonathan Cave <jonathan.cave@canonical.com>

"""
Script to test if a module is loaded in the running kernel. If not the
module will be loaded. This can be disabled using a flag.
"""

import argparse
import subprocess


class ModuleLoadedTest():
    """Check if a kernel module is loaded. If not load it."""

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("module", help="Specify the module to test for.")
        parser.add_argument("-n", "--no-load", action="store_true", help=(
            "Don't try and load the module just test."))
        args = parser.parse_args()

        if self.is_module_loaded(args.module):
            return

        # module not loaded
        if args.no_load:
            raise SystemExit("ERROR: module {} not loaded in running"
                             " kernel".format(args.module))

        # attempt a load of the module
        if not self.load_module(args.module):
            raise SystemExit(
                "ERROR: attempt to load module {} failed".format(args.module))

    def is_module_loaded(self, module):
        with open('/proc/modules', 'r') as modules:
            for line in modules:
                if line.split(' ')[0] == module:
                    print("Found kernel module {}".format(module))
                    return True
        print("Couldn't find kernel module {}".format(module))
        return False

    def load_module(self, module):
        if subprocess.call(['modprobe', module]) == 0:
            print("Module {} was loaded".format(module))
            return True
        print("Module {} failed to load".format(module))
        return False


if __name__ == "__main__":
    ModuleLoadedTest().main()
