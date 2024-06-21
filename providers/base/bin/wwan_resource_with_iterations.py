#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Stanley Huang <stanley.huang@canonical.com>
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.

import argparse

from wwan_tests import MMCLI
from wwan_tests import MMDbus


def dump_wwan_resource(iterations, use_cli):

    if use_cli:
        mm = MMCLI()
    else:
        mm = MMDbus()

    for i in range(1, iterations + 1):
        for m in mm.get_modem_ids():
            print("iteration: {}".format(i))
            print("mm_id: {}".format(m))
            print("hw_id: {}".format(mm.get_equipment_id(m)))
            print("manufacturer: {}".format(mm.get_manufacturer(m)))
            print("model: {}".format(mm.get_model_name(m)))
            print("firmware_revision: {}".format(mm.get_firmware_revision(m)))
            print("hardware_revision: {}".format(mm.get_hardware_revision(m)))
            print()


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Generate wwan resource for "
            "establishing WWAN connection multiple times"
        ),
    )

    parser.add_argument("-i", "--iteration", type=int, default=3)
    parser.add_argument(
        "--use-cli",
        action="store_true",
        help="Use mmcli for all calls rather than dbus",
    )
    args = parser.parse_args()
    return args


if __name__ == "__main__":

    args = register_arguments()
    dump_wwan_resource(args.iteration, args.use_cli)
