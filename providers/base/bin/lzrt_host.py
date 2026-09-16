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

"""Host Level Zero Raytracing helper for Checkbox."""

import logging
import os
import subprocess
import sys

from checkbox_support.helpers.host_utils import (
    check_host_level_zero_gpu,
    get_arch_triple,
    host_ze_loader_path,
)


def cmd_resource():
    arch_triple = get_arch_triple()
    if check_host_level_zero_gpu(arch_triple):
        print("gpu_available: True")
        return 0

    logging.error("No Level Zero GPU device found using host drivers")
    return 1


def cmd_validate_install():
    arch_triple = get_arch_triple()
    host_ze = host_ze_loader_path(arch_triple)
    if os.path.isfile(host_ze):
        logging.info("Host Level Zero loader found at %s", host_ze)
        print("ze_loader_available: True")
        return 0
    logging.error("Host Level Zero loader not found at %s", host_ze)
    logging.error(
        "Install libze1 or equivalent before running host Level Zero "
        "raytracing tests"
    )
    return 1


def cmd_run_test(test_args):
    snap = "/snap/level-zero-raytracing-tests/current"
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
            "Usage: lzrt_host.py {resource,validate-install,run-test} "
            "[args...]"
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
