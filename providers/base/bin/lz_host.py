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
Host Level Zero helper for Checkbox.

Subcommands:
  resource          Emit a resource record if a GPU is available via host
                    Level Zero drivers (used by depends:
                    graphics/lz_classic_gpu_avail).
  validate-install  Emit a resource record if the host Level Zero ICD loader
                    is installed (used by depends:
                    graphics/lz_classic_lz_avail).
  run-test ARGS...  Run a level-zero-tests test binary with --no-confinement,
                    forwarding all remaining arguments to the test.
"""

import glob
import logging
import os
import subprocess
import sys

from checkbox_support.helpers.host_utils import (
    VulkanDetectionError,
    find_plz_run,
    get_arch_triple,
)


def check_host_gpu(plz_run, arch_triple):
    """Check for a Level Zero GPU by probing render device nodes.

    plz-run is used to escape snap confinement so that the host device
    nodes and libraries are visible.
    """
    render_nodes = glob.glob("/dev/dri/renderD*")
    if not render_nodes:
        logging.error("No render device nodes found in /dev/dri")
        return False
    loader = "/usr/lib/{}/libze_loader.so.1".format(arch_triple)
    if not os.path.isfile(loader):
        logging.error("Host Level Zero loader not found at %s", loader)
        return False
    logging.info("Found render device(s) and Level Zero loader at %s", loader)
    return True


def cmd_resource():
    arch_triple = get_arch_triple()

    try:
        plz_run = find_plz_run()
    except VulkanDetectionError as exc:
        logging.error("%s", exc)
        return 1

    if check_host_gpu(plz_run, arch_triple):
        print("gpu_available: True")
        return 0

    logging.error("No Level Zero GPU device found using host drivers")
    return 1


def cmd_validate_install():
    arch_triple = get_arch_triple()
    host_ze = "/usr/lib/{}/libze_loader.so.1".format(arch_triple)
    if os.path.isfile(host_ze):
        logging.info("Host Level Zero loader found at %s", host_ze)
        print("ze_loader_available: True")
        return 0
    logging.error("Host Level Zero loader not found at %s", host_ze)
    logging.error(
        "Install libze1 or equivalent before running host Level Zero tests"
    )
    return 1


def cmd_run_test(test_args):
    snap = "/snap/level-zero-tests/current"
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
            "Usage: lz_host.py {resource,validate-install,run-test} [args...]"
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
    except (RuntimeError, VulkanDetectionError) as exc:
        logging.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
