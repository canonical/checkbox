#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
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

import subprocess


def check_pmf_loaded():
    """
    This is a simple function to use lsmod to verify
    AMD Platform Management Framework driver is loaded or not
    """
    cmd = ["lsmod"]
    try:
        output = subprocess.check_output(
            cmd,
            universal_newlines=True,
        )
        if "amd_pmf" in output.lower():
            print("AMD Platform Management Framework is loaded")
        else:
            raise SystemExit("AMD Platform Management Framework isn't loaded")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise SystemExit("running cmd:[{}] fail:{}".format(cmd, repr(e)))


if __name__ == "__main__":
    check_pmf_loaded()
