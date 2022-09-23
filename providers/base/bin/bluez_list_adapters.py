#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2018 Canonical Ltd.
#
# Authors:
# Jonathan Cave <jonathan.cave@canonical.com>
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

import checkbox_support.bt_helper as bt_helper

import sys


def main():
    manager = bt_helper.BtManager()
    bt_adapter_not_found = True
    for dev in manager.get_bt_adapters():
        bt_adapter_not_found = False
        print(dev._if.object_path.split('/')[-1])
    return bt_adapter_not_found


if __name__ == "__main__":
    sys.exit(main())
