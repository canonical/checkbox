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
Host Vulkan helper for Checkbox.

Subcommands:
  resource          Emit a resource record if a GPU is available via host
                    Vulkan drivers (used by depends:
                    graphics/vk_classic_gpu_avail).
  validate-install  Emit a resource record if the host Vulkan ICD loader is
                    installed (used by depends: graphics/vk_classic_vk_avail).
  run-test ARGS...  Run a vulkan-cts test binary with --no-confinement,
                    forwarding all remaining arguments to the test.
"""

import os
import shutil
import subprocess
import sys
import sysconfig


def get_arch_triple():
    """Return the Debian multiarch triple for the current architecture."""
    return sysconfig.get_config_var("MULTIARCH")


def find_plz_run():
    """Return the path to plz-run from the running checkbox snap."""
    return shutil.which("plz-run")


def check_host_gpu(plz_run, arch_triple):
    """Run vulkaninfo via plz-run with host libraries and detect a GPU.

    vulkaninfo is executed inside a new mount/user namespace (via plz-run)
    so that it can load the host ICD stack instead of snap-bundled libraries.
    """
    if not os.path.isfile("/usr/bin/vulkaninfo"):
        print("FAIL: /usr/bin/vulkaninfo not found", file=sys.stderr)
        return False
    ld_library_path = "/usr/lib/{arch}:/usr/lib".format(arch=arch_triple)
    try:
        output = subprocess.check_output(
            [
                plz_run,
                "-u",
                "root",
                "-g",
                "root",
                "-E",
                "LD_LIBRARY_PATH={}".format(ld_library_path),
                "--",
                "/usr/bin/vulkaninfo",
                "--summary",
            ],
            universal_newlines=True,
            stderr=subprocess.STDOUT,
        )
        return any(
            t in output
            for t in (
                "PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU",
                "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU",
                "PHYSICAL_DEVICE_TYPE_VIRTUAL_GPU",
            )
        )
    except subprocess.CalledProcessError:
        return False


def cmd_resource():
    arch_triple = get_arch_triple()

    plz_run = find_plz_run()
    if plz_run is None:
        print("FAIL: plz-run not found in any checkbox snap", file=sys.stderr)
        return 1

    if check_host_gpu(plz_run, arch_triple):
        print("gpu_available: True")
        return 0

    print(
        "FAIL: No GPU device found in vulkaninfo output using host drivers",
        file=sys.stderr,
    )
    return 1


def cmd_validate_install():
    arch_triple = get_arch_triple()
    host_vk = "/usr/lib/{}/libvulkan.so.1".format(arch_triple)
    if os.path.isfile(host_vk):
        print("vk_icd_available: True")
        return 0
    print(
        "FAIL: Host Vulkan ICD loader not found at {}".format(host_vk),
        file=sys.stderr,
    )
    print(
        "Install libvulkan1 or equivalent" " before running host Vulkan tests",
        file=sys.stderr,
    )
    return 1


def cmd_run_test(test_args):
    snap = "/snap/vulkan-cts/current"
    result = subprocess.run(
        ["{}/test".format(snap), "--no-confinement"] + test_args,
        env=dict(os.environ, SNAP=snap),
    )
    return result.returncode


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: vk_host.py {resource,validate-install,run-test} [args...]",
            file=sys.stderr,
        )
        return 1
    command = sys.argv[1]
    if command == "resource":
        return cmd_resource()
    elif command == "validate-install":
        return cmd_validate_install()
    elif command == "run-test":
        return cmd_run_test(sys.argv[2:])
    else:
        print("Unknown command: {}".format(command), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
