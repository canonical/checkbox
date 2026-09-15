#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
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

"""OpenGL eglinfo helper for CE OEM graphics jobs.

Subcommands:
  resource  Emit EGL platform records (gbm, wayland, x11, surfaceless) for
            Checkbox resource jobs. Reads the EGLINFO_IGNORED_PLATFORM
            environment variable (a comma-separated list of platform
            names, e.g. "x11,surfaceless") to mark platforms that should
            be skipped. Platform support is not auto-detected; every
            platform in PLATFORMS is emitted unless explicitly ignored.
  test      Validate a single EGL platform using 'eglinfo -p <platform>'.
"""

import argparse
import logging
import os
import subprocess
import sys
from typing import TypedDict

from general_utils import resolve_configured_commands

EXECUTABLE_CMD = "eglinfo"

# Platforms this suite cares about, in a stable, deterministic order.
# Android (and any other eglinfo-supported platform) is intentionally
# excluded from resource generation.
PLATFORMS = ("gbm", "wayland", "x11", "surfaceless")

EGL_INITIALIZE_FAILED = "eglInitialize failed"

# Comma-separated list of platform names (e.g. "x11,surfaceless") that
# should be marked ignored in the resource output.
EGLINFO_IGNORED_PLATFORM = "EGLINFO_IGNORED_PLATFORM"

# Default set of software renderer keywords that indicate the GPU is not
# actually being used, e.g. Mesa's llvmpipe/softpipe or Gallium's swrast.
DEFAULT_SOFTWARE_RENDERERS = ("llvmpipe", "softpipe", "swrast")

logger = logging.getLogger(__name__)


class EglinfoRecord(TypedDict):
    platform: str
    platform_name: str


def _resolve_eglinfo_command(enable_logger: bool = False) -> str:
    """Resolve eglinfo command from JSON config or system PATH.

    Returns:
        Command string if successful, empty string if failed.
    """
    resolved_commands = resolve_configured_commands(
        default_commands=[EXECUTABLE_CMD],
        enable_logger=enable_logger,
    )
    return resolved_commands.get(EXECUTABLE_CMD, "")


def parse_ignored_set() -> "set[str]":
    """Read ignored platform names from the EGLINFO_IGNORED_PLATFORM
    environment variable, a comma-separated list, e.g. "x11,surfaceless".
    """
    raw_value = os.environ.get(EGLINFO_IGNORED_PLATFORM, "")
    logger.debug(f"{EGLINFO_IGNORED_PLATFORM}={raw_value!r}")

    return {
        platform_name.strip().lower()
        for platform_name in raw_value.split(",")
        if platform_name.strip()
    }


def cmd_resource() -> int:
    """Emit one resource record per platform in PLATFORMS, marking
    platforms listed in EGLINFO_IGNORED_PLATFORM with ignore: true.
    """
    ignored_platforms = parse_ignored_set()

    for platform_name in PLATFORMS:
        is_ignored = platform_name in ignored_platforms
        print("platform_name: {}".format(platform_name))
        print("ignore: {}".format(is_ignored))
        print("")

    return 0


def cmd_test(platform_name: str) -> int:
    """Validate a single EGL platform using 'eglinfo -p <platform_name>'.

    Judgement criteria:
      1. No output at all -> fail.
      2. 'eglInitialize failed' found in the output -> fail.
      3. A software renderer (llvmpipe, softpipe, swrast) is observed ->
         fail.
      Otherwise -> pass.
    """
    command = _resolve_eglinfo_command()
    if not command:
        logger.error("eglinfo command not found")
        return 1

    full_command = " ".join([command, "-B", "-p", platform_name])
    logger.info(f"Running command: '{full_command}'")
    # stdout and stderr are combined because 'eglinfo' prints error
    # messages such as 'eglInitialize failed' without a reliable,
    # consistent stream.
    result = subprocess.run(
        full_command,
        shell=True,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = result.stdout

    if output:
        logger.info(f"eglinfo output:\n{output.rstrip()}")

    if not output.strip():
        logger.error(
            f"FAIL: no output from '{full_command}' "
            f"for platform '{platform_name}'"
        )
        return 1

    if EGL_INITIALIZE_FAILED in output:
        logger.error(
            f"FAIL: found '{EGL_INITIALIZE_FAILED}' error message "
            f"for platform '{platform_name}'"
        )
        return 1

    software_renderer_keywords = DEFAULT_SOFTWARE_RENDERERS
    found_keywords = [
        keyword
        for keyword in software_renderer_keywords
        if keyword.lower() in output.lower()
    ]
    if found_keywords:
        logger.error(
            f"FAIL: software renderer detected for platform "
            f"'{platform_name}': {', '.join(sorted(set(found_keywords)))}"
        )
        return 1

    logger.info(
        f"PASS: eglinfo validation passed for platform '{platform_name}'"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)

    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--debug",
        action="store_true",
        help="enable debug logging",
    )

    subparsers.add_parser("resource", parents=[common_parser])

    test_parser = subparsers.add_parser("test", parents=[common_parser])
    test_parser.add_argument(
        "-p",
        "--platform",
        required=True,
        help="EGL platform name, e.g. gbm, wayland, x11, surfaceless",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.action == "resource":
        return cmd_resource()
    if args.action == "test":
        return cmd_test(args.platform)

    parser.print_help()
    return 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-8s - %(module)-10s: %(funcName)s "
        + "%(lineno)-4d - %(message)s",
    )
    sys.exit(main())
