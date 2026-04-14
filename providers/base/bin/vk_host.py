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
import subprocess
import sys

from host_utils import (  # noqa: F401
    _active_vendor_prefixes,
    check_host_gpu,
    find_host_icd_filenames,
    find_plz_run,
    get_arch_triple,
)


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
    # NODEVICE_SELECT disables VK_LAYER_MESA_device_select — the layer
    # requires GLIBC_ABI_GNU2_TLS, which the snap's core24 glibc lacks.
    env = dict(os.environ, SNAP=snap, NODEVICE_SELECT="1")
    if not env.get("VK_ICD_FILENAMES"):
        icd_filenames = find_host_icd_filenames(_active_vendor_prefixes())
        if icd_filenames:
            env["VK_ICD_FILENAMES"] = icd_filenames
    result = subprocess.run(
        ["{}/test".format(snap), "--no-confinement"] + test_args,
        env=env,
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
