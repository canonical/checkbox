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

import logging
import os
import shutil
import subprocess
import sys
import sysconfig


def get_arch_triple():
    """Return the Debian multiarch triple for the current architecture."""
    triple = sysconfig.get_config_var("MULTIARCH")
    if triple is None:
        raise RuntimeError("could not determine multiarch triple")
    return triple


def find_plz_run():
    """Return the path to plz-run from the running checkbox snap."""
    return shutil.which("plz-run")


def check_host_gpu(plz_run, arch_triple):
    """Run vulkaninfo via plz-run with host libraries and detect a GPU.

    vulkaninfo is executed inside a new mount/user namespace (via plz-run)
    so that it can load the host ICD stack instead of snap-bundled libraries.
    """
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
        logging.error("plz-run not found in any checkbox snap")
        return 1

    if check_host_gpu(plz_run, arch_triple):
        logging.info("Found a Vulkan-capable GPU using host drivers")
        return 0

    logging.error(
        "No GPU device found in vulkaninfo output using host drivers"
    )
    return 1


def cmd_validate_install():
    arch_triple = get_arch_triple()
    host_vk = "/usr/lib/{}/libvulkan.so.1".format(arch_triple)
    if os.path.isfile(host_vk):
        logging.info("Host Vulkan ICD loader found at %s", host_vk)
        return 0
    logging.error("Host Vulkan ICD loader not found at %s", host_vk)
    logging.error(
        "Install libvulkan1 or equivalent before running host Vulkan tests"
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
    logging.basicConfig(
        format="%(levelname)s: %(message)s", level=logging.INFO
    )
    if len(sys.argv) < 2:
        logging.error(
            "Usage: vk_host.py {resource,validate-install,run-test} [args...]"
        )
        return 1
    command = sys.argv[1]
    try:
        if command == "resource":
            return cmd_resource()
        elif command == "validate-install":
            return cmd_validate_install()
        elif command == "run-test":
            return cmd_run_test(sys.argv[2:])
        else:
            logging.error("Unknown command: %s", command)
            return 1
    except RuntimeError as exc:
        logging.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
