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

import os
import json
import shlex
import subprocess
from checkbox_support.snap_utils.snapd import Snapd


def get_firmware_info_fwupd():

    fwupd_snap = Snapd().list("fwupd")
    if fwupd_snap:
        # Dump firmware info by fwupd snap
        subprocess.run(shlex.split("fwupd.fwupdmgr get-devices --json"))
    else:
        # Dump firmware info by fwupd debian package
        fwupd_vers = subprocess.run(
            shlex.split("fwupdmgr --version --json"),
            capture_output=True)
        fwupd_vers = json.loads(fwupd_vers.stdout)

        runtime_ver = ()
        for ver in fwupd_vers.get("Versions", []):
            if (ver.get("Type") == "runtime" and
                    ver.get("AppstreamId") == "org.freedesktop.fwupd"):
                runtime_ver = tuple(map(int, ver.get("Version").split(".")))
        # Apply workaround to unset the SNAP for the fwupd issue
        # See details from following PR
        # https://github.com/canonical/checkbox/pull/1089

        # SNAP environ is avaialble, so it's running on checkbox snap
        # Unset the environ variable if debian fwupd lower than 1.9.14
        if os.environ["SNAP"] and runtime_ver < (1, 9, 14):
            del os.environ["SNAP"]

        subprocess.run(shlex.split("fwupdmgr get-devices --json"))


if __name__ == "__main__":
    try:
        get_firmware_info_fwupd()
    except Exception as err:
        print(err)
