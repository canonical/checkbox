#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# hdd_parking
#
# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
#
# Authors: Brendan Donegan <brendan.donegan@canonical.com>
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

"""
This script verifies that a systems HDD protection capabilities
are triggered when appropriate. There are many implementations
of HDD protection from different OEMs, each implemented in a
different way, so this script can only support implementations
which are known to work and are testable. Currently the list
of supported implementations is:

- HDAPS (Lenovo)
"""


import sys
import time

from argparse import ArgumentParser
from subprocess import Popen, PIPE

TIMEOUT = 15.0


def hdaps_test(run_time):
    try:
        hdapsd = Popen(
            ["/usr/sbin/hdapsd"],
            stdout=PIPE,
            stderr=PIPE,
            universal_newlines=True,
        )
    except OSError as err:
        print("Unable to start hdapsd: {}".format(err))
        return 1
    time.sleep(float(run_time))
    hdapsd.terminate()
    # Look for parking message in hdapsd output.
    stdout = hdapsd.communicate()[0]
    print(stdout)
    for line in stdout.split("\n"):
        if line.endswith("parking"):
            return 0
    return 1


def main():
    # First establish the driver used
    parser = ArgumentParser(
        "Tests a systems HDD protection capabilities. "
        "Requires the system to be moved by the tester."
    )
    parser.add_argument(
        "-t",
        "--timeout",
        default=TIMEOUT,
        help="The time allowed before the test fails.",
    )
    print(
        "Starting HDD protection test - move the system around on "
        "all axis. No particular force should be required."
    )
    return hdaps_test(parser.parse_args().timeout)


if __name__ == "__main__":
    sys.exit(main())
