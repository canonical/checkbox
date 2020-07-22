#!/usr/bin/env python3
# Copyright 2017-2018 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
#   Taihsiang Ho <taihsiang.ho@canonical.com>
#
# Print info about drivers we can identify automatically and also those we
# identify in the special interest list!

from pathlib import Path
import subprocess as sp
import sys

# Store pairs of (interface, driver)
driver_list = []

# Find drivers in sysfs
for interface in Path("/sys/class/net").iterdir():
    mod_path = Path("{}/device/driver/module".format(interface))
    if mod_path.is_symlink():
        driver_list.append((interface.name, mod_path.resolve().name))

# Add user requested modules to the list. Create "unknown" interfaces if none
# of the identified interfaces above are using it
for user_driver in sys.argv[1:]:
    if user_driver:
        if Path("/sys/module/{}".format(user_driver)).exists():
            if not any(x[1] == user_driver for x in driver_list):
                driver_list.append(("unknown", user_driver))
        else:
            print("Requested driver {} not loaded\n".format(user_driver))

# Produce the output
for interface, driver in driver_list:
    print("Interface {} using module {}".format(interface, driver))
    sysfs_path = Path("/sys/module/{}/parameters".format(driver))
    if sysfs_path.is_dir():
        print("  Parameters:")
        for path in Path(sysfs_path).iterdir():
            if path.is_file():
                # Path.read_text is new in python 3.5 but we want to support
                # trusty as well, which uses python 3.4 by default.
                with open(str(path), 'r') as f:
                    print("    {}: {}".format(path.name, f.read().strip()))
    print()
    print('Checking kernel ring buffer for {} messages:'.format(driver))
    cmd = "dmesg -T -x | grep {} || true".format(driver)
    output = sp.check_output(cmd, shell=True)
    print(output.decode(sys.stdout.encoding))
    print()
