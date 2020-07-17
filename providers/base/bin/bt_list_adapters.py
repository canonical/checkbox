#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2018 Canonical Ltd.
#
# Authors:
#    Jonathan Cave <jonathan.cave@canonical.com>
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

import os


def main():
    rfkill = '/sys/class/rfkill'
    found_adatper = False
    for rfdev in os.listdir(rfkill):
        typef = os.path.join(rfkill, rfdev, 'type')
        type = ''
        with open(typef, 'r') as f:
            type = f.read().strip()
        if type != 'bluetooth':
            continue
        found_adatper = True
        namef = os.path.join(rfkill, rfdev, 'name')
        name = ''
        with open(namef, 'r') as f:
            name = f.read().strip()
        print(rfdev, name)
    if found_adatper is False:
        raise SystemExit('No bluetooth adatpers registered with rfkill')


if __name__ == "__main__":
    main()
