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

"""Vulkan vulkaninfo helper for CE OEM graphics jobs.

Subcommands:
  resource  Emit one record per hardware GPU device (deviceType
            DISCRETE_GPU/INTEGRATED_GPU) reported by 'vulkaninfo --summary'.
            Software-only devices (e.g. Mesa's llvmpipe/lavapipe CPU
            device) are never emitted.
  test      Validate the Vulkan stack by running 'vulkaninfo --summary'.
"""

import argparse
import logging
import subprocess
import sys
from typing import TypedDict

from general_utils import resolve_configured_commands

EXECUTABLE_CMD = "vulkaninfo"

# deviceType values that represent an actual hardware GPU. Anything else
# (e.g. PHYSICAL_DEVICE_TYPE_CPU used by Mesa's llvmpipe/lavapipe software
# rasterizer) is intentionally excluded from resource generation.
HARDWARE_DEVICE_TYPES = (
    "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU",
    "PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU",
)

# Text fragments that indicate the process terminated abnormally instead of
# producing a normal report, e.g. a crash reported by the invoking shell.
CRASH_INDICATORS = (
    "segmentation fault",
    "core dumped",
    "aborted",
    "illegal instruction",
    "bus error",
)

# Renderer/driver keywords that indicate a software (non-GPU) Vulkan
# implementation is being used instead of real hardware.
DEFAULT_SOFTWARE_RENDERERS = ("llvmpipe", "softpipe", "swrast")

logger = logging.getLogger(__name__)


class VulkaninfoRecord(TypedDict):
    device_number: str
    device_name: str
    device_type: str


def _resolve_vulkaninfo_command(enable_logger: bool = False) -> str:
    """Resolve vulkaninfo command from JSON config or system PATH.

    Returns:
        Command string if successful, empty string if failed.
    """
    resolved_commands = resolve_configured_commands(
        default_commands=[EXECUTABLE_CMD],
        enable_logger=enable_logger,
    )
    return resolved_commands.get(EXECUTABLE_CMD, "")


def parse_vulkaninfo_summary(output: str) -> "list[VulkaninfoRecord]":
    """Parse 'vulkaninfo --summary' output into a list of device records.

    Only the 'Devices:' section (flat 'GPUn:' blocks with tab-indented
    'key = value' fields) is parsed; the more verbose extension/format
    listing produced by plain 'vulkaninfo' is not handled here. Plain
    string operations are used instead of regexes to keep the parser
    simple and easy to follow.
    """
    records: "list[VulkaninfoRecord]" = []
    current_number = None
    current_fields = {}

    def flush():
        if current_number is not None:
            records.append(
                {
                    "device_number": current_number,
                    "device_name": current_fields.get("deviceName", ""),
                    "device_type": current_fields.get("deviceType", ""),
                }
            )

    for line in output.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("GPU") and stripped_line.endswith(":"):
            device_number = stripped_line[len("GPU") : -1].strip()
            if device_number.isdigit():
                flush()
                current_number = device_number
                current_fields = {}
                continue

        if current_number is None:
            continue

        if not line.startswith("\t") or "=" not in line:
            continue

        key, _, value = line.strip().partition("=")
        current_fields[key.strip()] = value.strip()

    flush()
    return records


def extract_device_block(output: str, device_number: str) -> str:
    """Return the raw 'GPU<device_number>:' block from a
    'vulkaninfo --summary' output, or '' if that device isn't present.

    Used to scope the software-renderer check (see cmd_test) to a single
    device on multi-GPU systems, where one device may be the real GPU and
    another a software fallback (e.g. Mesa's llvmpipe) both listed in the
    same output.
    """
    lines: "list[str]" = []
    collecting = False

    for line in output.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("GPU") and stripped_line.endswith(":"):
            if collecting:
                break
            if stripped_line[len("GPU") : -1].strip() == device_number:
                collecting = True
                lines.append(line)
            continue

        if collecting:
            lines.append(line)

    return "\n".join(lines)


def cmd_resource() -> int:
    """Emit one resource record per hardware GPU device found by
    'vulkaninfo --summary'. Software-only devices are skipped entirely.
    """
    command = _resolve_vulkaninfo_command()
    if not command:
        logger.error("vulkaninfo command not found")
        return 1

    full_command = " ".join([command, "--summary"])
    logger.info("Running command: '%s'", full_command)
    # stdout and stderr are combined because a crashing driver's error
    # (e.g. 'Segmentation fault (core dumped)') is reported by the
    # invoking shell on stderr/stdout without a reliable, consistent
    # stream.
    result = subprocess.run(
        full_command,
        shell=True,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = result.stdout

    records = parse_vulkaninfo_summary(output)
    hardware_records = [
        record
        for record in records
        if record["device_type"] in HARDWARE_DEVICE_TYPES
    ]

    if not hardware_records:
        logger.error(
            "No hardware GPU device found in '%s' output\n\n%s",
            full_command,
            output,
        )
        return 1

    for record in hardware_records:
        print("device_number: {}".format(record["device_number"]))
        print("device_name: {}".format(record["device_name"]))
        print("")

    return 0


def cmd_test(device_number: str = "", device_name: str = "") -> int:
    """Validate the Vulkan stack using 'vulkaninfo --summary'.

    Judgement criteria:
      1. No output at all -> fail.
      2. Unexpected/crash output observed (e.g. 'Segmentation fault') ->
         fail.
      3. A software renderer (llvmpipe, softpipe, swrast) is observed for
         the target device -> fail.
      Otherwise -> pass.

    On multi-GPU systems, 'vulkaninfo --summary' lists every device in one
    combined output (e.g. a real GPU alongside Mesa's software llvmpipe
    fallback). When device_number is provided, the software-renderer check
    (criterion 3) is scoped to that device's own block so an unrelated
    software-only device listed elsewhere in the output doesn't fail this
    device's job. Criteria 1 and 2 always apply to the whole output, since
    a crash or empty output means no device-specific block exists at all.
    """
    command = _resolve_vulkaninfo_command()
    if not command:
        logger.error("vulkaninfo command not found")
        return 1

    if device_number or device_name:
        logger.info(
            "Validating Vulkan device number: '%s', name: '%s'",
            device_number,
            device_name,
        )

    full_command = " ".join([command, "--summary"])
    logger.info("Running command: '%s'", full_command)
    # stdout and stderr are combined because a crashing driver's error
    # (e.g. 'Segmentation fault (core dumped)') is reported by the
    # invoking shell on stderr/stdout without a reliable, consistent
    # stream.
    result = subprocess.run(
        full_command,
        shell=True,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    returncode = result.returncode
    output = result.stdout

    if output:
        logger.info("vulkaninfo output:\n%s", output.rstrip())

    if not output.strip():
        logger.error("FAIL: no output from '%s'", full_command)
        return 1

    found_crash_indicators = [
        indicator
        for indicator in CRASH_INDICATORS
        if indicator in output.lower()
    ]
    if found_crash_indicators or returncode != 0:
        logger.error(
            "FAIL: unexpected/crash output detected from '%s' "
            "(returncode=%s, indicators=%s)",
            full_command,
            returncode,
            ", ".join(sorted(set(found_crash_indicators))) or "n/a",
        )
        return 1

    if device_number:
        renderer_scope = extract_device_block(output, device_number)
        if not renderer_scope:
            logger.error(
                "FAIL: device number '%s' not found in '%s' output",
                device_number,
                full_command,
            )
            return 1
    else:
        renderer_scope = output

    found_software_renderers = [
        keyword
        for keyword in DEFAULT_SOFTWARE_RENDERERS
        if keyword.lower() in renderer_scope.lower()
    ]
    if found_software_renderers:
        logger.error(
            "FAIL: software renderer detected: %s",
            ", ".join(sorted(set(found_software_renderers))),
        )
        return 1

    logger.info("PASS: vulkaninfo validation passed")
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
        "-dn",
        "--device-number",
        default="",
        help=(
            "Vulkan GPU device number, e.g. 0; scopes the software-"
            "renderer check to this device's block in 'vulkaninfo "
            "--summary' output"
        ),
    )
    test_parser.add_argument(
        "-n",
        "--device-name",
        default="",
        help="Vulkan GPU device name (informational only)",
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
        return cmd_test(args.device_number, args.device_name)

    parser.print_help()
    return 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-8s - %(module)-10s: %(funcName)s "
        + "%(lineno)-4d - %(message)s",
    )

    sys.exit(main())
