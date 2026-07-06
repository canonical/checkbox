#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2020 Canonical Ltd.
#
# Authors:
#    Sylvain Pineau <sylvain.pineau@canonical.com>
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

import codecs
import os
import re
import subprocess
import sys

p = "/usr/share/{}".format(codecs.decode("kyak-svezjner", "rot-13"))
dtb = os.path.join(p, sys.argv[1], "{}_system.dtb".format(sys.argv[1]))
dt_lookup_list = []
exit_status = 0

dt_compatible_patterns = subprocess.check_output(
    "find /proc/device-tree/ -name compatible -exec "
    'bash -c "cat {} && echo" \\; | sort -u',
    shell=True,
    universal_newlines=True,
).splitlines()
for line in dt_compatible_patterns:
    line = line.replace("\0", ", ")
    dt_lookup_list.append(re.split(", ", line)[:-1])

compatible_patterns = subprocess.check_output(
    'fdtdump {} 2>/dev/null | grep -oP "(?<= compatible = ).*"'
    " | sort -u".format(dtb),
    shell=True,
    universal_newlines=True,
).splitlines()
for l in compatible_patterns:
    item = re.split(", ", l.replace('"', "").replace(";", ""))
    if item in dt_lookup_list:
        print("Found in /proc/device-tree/:", l)
    else:
        print("ERROR: Not found:", l, file=sys.stderr)
        exit_status = 1

raise SystemExit(exit_status)
