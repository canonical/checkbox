#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Shane McKee <shane.mckee@canonical.com>
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
Check whether clinfo reports a GPU when run against host OpenCL drivers.

The check must break out of snap confinement (using plz-run) so that
/usr/bin/clinfo loads the host ICD loader rather than the snap-bundled one.
On success this script emits a resource record that can be referenced with
depends: graphics/cl_host_gpu_avail.
"""

import glob
import os
import subprocess
import sys
import tempfile


def get_arch_triple(snap_arch=None):
    """Return the Debian multiarch triple for the current architecture."""
    if snap_arch is None:
        snap_arch = os.environ.get("SNAP_ARCH")
    if not snap_arch:
        snap_arch = subprocess.check_output(
            ["dpkg", "--print-architecture"], universal_newlines=True
        ).strip()
    arch_map = {
        "amd64": "x86_64-linux-gnu",
        "arm64": "aarch64-linux-gnu",
    }
    return arch_map.get(snap_arch, "{}-linux-gnu".format(snap_arch))


def find_plz_run():
    """Return the path to the first plz-run binary found in checkbox snaps."""
    matches = glob.glob("/snap/checkbox*/current/bin/plz-run")
    if not matches:
        return None
    return matches[0]


def check_host_gpu(plz_run, arch_triple):
    """Run clinfo via plz-run with host libraries and detect a GPU.

    clinfo is executed inside a new mount/user namespace (via plz-run) so that
    it can load the host ICD stack instead of any snap-bundled libraries.
    """
    ld_library_path = "/usr/lib/{arch}:/usr/lib".format(arch=arch_triple)
    with tempfile.NamedTemporaryFile(dir="/var/tmp", delete=False) as tmp:
        tmpfile = tmp.name
    try:
        subprocess.run(
            [
                plz_run,
                "-u",
                "root",
                "-g",
                "root",
                "bash",
                "-c",
                "LD_LIBRARY_PATH={ld} /usr/bin/clinfo > {out} 2>&1".format(
                    ld=ld_library_path, out=tmpfile
                ),
            ],
            check=False,
        )
        with open(tmpfile) as fh:
            output = fh.read()
    finally:
        os.unlink(tmpfile)
    return "CL_DEVICE_TYPE_GPU" in output


def main():
    arch_triple = get_arch_triple()

    plz_run = find_plz_run()
    if plz_run is None:
        print("FAIL: plz-run not found in any checkbox snap", file=sys.stderr)
        return 1

    if check_host_gpu(plz_run, arch_triple):
        print("gpu_available: True")
        return 0

    print(
        "FAIL: No GPU device found in clinfo output using host drivers",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
