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
import os
import shutil
import subprocess
import sys
from typing import TypedDict

# deviceType values that represent an actual hardware GPU. Anything else
# (e.g. PHYSICAL_DEVICE_TYPE_CPU used by Mesa's llvmpipe/lavapipe software
# rasterizer) is intentionally excluded from resource generation.
HARDWARE_DEVICE_TYPES = (
    "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU",
    "PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU",
)

# Renderer/driver keywords that indicate a software (non-GPU) Vulkan
# implementation is being used instead of real hardware.
SOFTWARE_RENDERERS = ("llvmpipe", "softpipe", "swrast")

logger = logging.getLogger(__name__)


class VulkaninfoRecord(TypedDict):
    device_number: str
    device_name: str
    device_type: str


def vulkaninfo_environ() -> "dict[str, str]":
    """Return the environment to run vulkaninfo with.

    The LD_LIBRARY_PATH inherited from a Checkbox snap points at the
    Checkbox runtime libraries, which a host vulkaninfo must not load.
    Checkbox also refuses to override an existing LD_LIBRARY_PATH from the
    launcher, so it is replaced here by VULKANINFO_LD_LIBRARY_PATH (or
    dropped when unset).
    """
    env = dict(os.environ)
    env.pop("LD_LIBRARY_PATH", None)
    ld_library_path = os.environ.get("VULKANINFO_LD_LIBRARY_PATH")
    if ld_library_path:
        env["LD_LIBRARY_PATH"] = ld_library_path
    return env


def run_vulkaninfo_summary() -> str:
    """Run 'vulkaninfo --summary' and return its combined output.

    Raises SystemExit if the command is missing, exits non-zero or is
    killed by a signal (e.g. a driver segfault); the output is logged.
    """
    executable = os.environ.get("CUSTOM_VULKAN_COMMAND_PATH") or "vulkaninfo"
    command = [executable, "--summary"]
    env = vulkaninfo_environ()
    logger.info(f"Running command: {command} ({shutil.which(executable)})")
    for name in ("VK_ICD_FILENAMES", "LD_LIBRARY_PATH"):
        logger.info(f"{name}={env.get(name, '')}")
    try:
        return subprocess.check_output(
            command,
            env=env,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
    except FileNotFoundError as err:
        raise SystemExit(f"vulkaninfo command not found: {err}")
    except subprocess.CalledProcessError as err:
        # A negative returncode means the process was killed by a signal,
        # e.g. -11 for a segfault inside the GPU driver.
        logger.error(f"vulkaninfo output:\n{err.output}")
        raise SystemExit(
            f"FAIL: {command} exited with returncode {err.returncode}"
        )


def _iter_gpu_blocks(output: str) -> "list[tuple[str, list[str]]]":
    """Split 'vulkaninfo --summary' output into per-device blocks of raw
    'key = value' lines, keyed by the device number found in 'GPUn:'.
    """
    blocks: "list[tuple[str, list[str]]]" = []

    for line in output.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("GPU") and stripped_line.endswith(":"):
            candidate = stripped_line[len("GPU") : -1].strip()
            if candidate.isdigit():
                blocks.append((candidate, []))
                continue

        if blocks:
            blocks[-1][1].append(line)

    return blocks


def _build_record(
    device_number: str, field_lines: "list[str]"
) -> VulkaninfoRecord:
    fields = {}
    for line in field_lines:
        if not line.startswith("\t") or "=" not in line:
            continue
        key, _, value = line.strip().partition("=")
        fields[key.strip()] = value.strip()
    return {
        "device_number": device_number,
        "device_name": fields.get("deviceName", ""),
        "device_type": fields.get("deviceType", ""),
    }


def parse_vulkaninfo_summary(output: str) -> "list[VulkaninfoRecord]":
    """Parse the 'Devices:' section of 'vulkaninfo --summary' output
    (flat 'GPUn:' blocks with tab-indented 'key = value' fields) into a
    list of device records.
    """
    return [
        _build_record(device_number, field_lines)
        for device_number, field_lines in _iter_gpu_blocks(output)
    ]


def cmd_resource() -> int:
    """Emit one resource record per hardware GPU device found by
    'vulkaninfo --summary'. Software-only devices are skipped entirely.
    """
    output = run_vulkaninfo_summary()
    hardware_records = [
        record
        for record in parse_vulkaninfo_summary(output)
        if record["device_type"] in HARDWARE_DEVICE_TYPES
    ]

    if not hardware_records:
        logger.error(f"vulkaninfo output:\n{output}")
        raise SystemExit("No hardware GPU device found in vulkaninfo output")

    for record in hardware_records:
        print(f"device_number: {record['device_number']}")
        print(f"device_name: {record['device_name']}")
        print("")

    return 0


def cmd_test(device_number: str = "", device_name: str = "") -> int:
    """Validate the Vulkan stack using 'vulkaninfo --summary'.

    Fails when vulkaninfo crashes or exits non-zero, produces no output,
    or reports a software renderer (llvmpipe, softpipe, swrast).

    When device_number is given, the software-renderer check is scoped to
    that device's 'GPUn:' block, so an unrelated software fallback device
    listed in the same output doesn't fail this device's job.
    """
    if device_number or device_name:
        logger.info(
            f"Validating Vulkan device number: '{device_number}', "
            f"name: '{device_name}'"
        )

    output = run_vulkaninfo_summary()
    logger.info(f"vulkaninfo output:\n{output.rstrip()}")

    if not output.strip():
        raise SystemExit("FAIL: no output from vulkaninfo")

    if device_number:
        blocks = dict(_iter_gpu_blocks(output))
        if device_number not in blocks:
            raise SystemExit(
                f"FAIL: device number '{device_number}' not found in "
                "vulkaninfo output"
            )
        renderer_scope = "\n".join(blocks[device_number])
    else:
        renderer_scope = output

    found = [
        keyword
        for keyword in SOFTWARE_RENDERERS
        if keyword in renderer_scope.lower()
    ]
    if found:
        raise SystemExit(
            f"FAIL: software renderer detected: {', '.join(found)}"
        )

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
    logging.basicConfig(
        level=logging.INFO,
        format="{levelname:<8} - {module:<10}: {funcName} "
        "{lineno:<4} - {message}",
        style="{",
    )

    args = build_parser().parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.action == "resource":
        return cmd_resource()
    return cmd_test(args.device_number, args.device_name)


if __name__ == "__main__":
    sys.exit(main())
