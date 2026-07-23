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

"""OpenCL clinfo helper for CE OEM graphics jobs.

Subcommands:
  detect    Verify clinfo exists and that at least one platform/device pair
            is listed. Use -cejp to point to a JSON file describing a custom
            clinfo executable (e.g. a snap build); omit for system clinfo.
  resource  Emit platform/device records for Checkbox resource jobs.
            Use -vjp to point to a JSON file whose 'ignored_set' lists
            platform/device pairs that should be skipped.
  test      Validate OpenCL device properties against a baseline set.
            Use -vjp to point to a JSON file whose 'customized_validation_set'
            extends the default properties for specific platform/device pairs.
"""

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Set, Tuple, TypedDict

from general_utils import build_command, load_json_file

PLATFORM_PATTERN = re.compile(r"^\s*Platform\s+#(\d+):\s*(.+?)\s*$")
DEVICE_PATTERN = re.compile(r"^\s*[`|]--\s*Device\s+#(\d+):\s*(.+?)\s*$")
PROP_PATTERN_TEMPLATE = r"\b{}\b\s+(.+?)\s*$"

# Default validation set for OpenCL device properties. This can be extended
# or overridden by a JSON file with 'customized_validation_set' for specific
# platform/device pairs.
DEFAULT_VALIDATION_SET = {
    "CL_DEVICE_AVAILABLE": "CL_TRUE",
    "CL_DEVICE_COMPILER_AVAILABLE": "CL_TRUE",
    "CL_DEVICE_EXECUTION_CAPABILITIES": "CL_EXEC_KERNEL",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s - %(module)-10s: %(funcName)s "
    + "%(lineno)-4d - %(message)s",
)

logger = logging.getLogger(__name__)


class ClinfoRecord(TypedDict):
    platform: str
    platform_number: int
    device: str
    device_number: int


ValidationSet = Dict[str, str]


def _resolve_clinfo_command(
    clinfo_executable_json_path: str,
    enable_logger: bool = False
) -> Optional[str]:
    """Resolve clinfo command from JSON config or system PATH.
    
    Returns:
        Command string if successful, None if failed.
    """
    if clinfo_executable_json_path:
        data = load_json_file(clinfo_executable_json_path, enable_logger=enable_logger)
        executable_config = data.get("executable")
        if not isinstance(executable_config, dict):
            logger.error(
                "No valid 'executable' key in: %s",
                clinfo_executable_json_path,
            )
            return None
        try:
            command = build_command(executable_config, enable_logger=enable_logger)
            return command
        except (TypeError, ValueError) as exc:
            logger.error("Failed to build clinfo command: %s", exc)
            return None
    else:
        binary = shutil.which("clinfo")
        if binary is None:
            logger.error("clinfo binary not found in PATH")
            return None
        return binary


def _run_clinfo_command(
    command: str,
    capture_output: bool = True,
) -> subprocess.CompletedProcess:
    """Run a clinfo command with common subprocess options.
    
    Args:
        command: Shell command string to execute.
        capture_output: Whether to capture stdout and stderr.
    
    Returns:
        CompletedProcess with return code and captured output.
    """
    logger.debug("Running command: %s", command)
    return subprocess.run(
        command,
        shell=True,
        check=False,
        text=True,
        capture_output=capture_output,
    )


def parse_clinfo_list_output(output: str) -> List[ClinfoRecord]:
    """Parse clinfo -l output into a list of platform/device records."""
    records: List[ClinfoRecord] = []
    current_platform: Optional[str] = None
    current_platform_number: Optional[int] = None

    for line in output.splitlines():
        platform_match = PLATFORM_PATTERN.match(line)
        if platform_match:
            current_platform_number = int(platform_match.group(1))
            current_platform = platform_match.group(2)
            continue

        device_match = DEVICE_PATTERN.match(line)
        if (
            device_match
            and current_platform is not None
            and current_platform_number is not None
        ):
            records.append(
                {
                    "platform": current_platform,
                    "platform_number": current_platform_number,
                    "device": device_match.group(2),
                    "device_number": int(device_match.group(1)),
                }
            )

    return records


def parse_ignored_set(
    validation_json_path: str,
) -> Set[Tuple[str, str]]:
    """Load ignored platform/device pairs from 'ignored_set' in a JSON file."""
    if not validation_json_path:
        return set()

    data = load_json_file(validation_json_path)
    ignored_set_data = data.get("ignored_set", {})
    logger.debug("Loaded ignored_set data: %s", ignored_set_data)
    pairs: Set[Tuple[str, str]] = set()
    if isinstance(ignored_set_data, dict):
        for platform, devices in ignored_set_data.items():
            if isinstance(devices, list):
                for device in devices:
                    if isinstance(device, str):
                        pairs.add((platform, device))
    return pairs


def parse_property_value(output: str, property_name: str) -> Optional[str]:
    """Extract a property value from clinfo --prop output.
    https://registry.khronos.org/OpenCL/specs/unified/refpages/man/html/clGetDeviceInfo.html
    """
    pattern = re.compile(PROP_PATTERN_TEMPLATE.format(re.escape(property_name)))
    for line in output.splitlines():
        match = pattern.search(line)
        if match:
            return match.group(1).strip()
    return None


def load_validation_set(
    validation_json_path: str,
    platform: str,
    device: str,
) -> ValidationSet:
    """Load validation set; extends defaults with customized_validation_set."""
    validation_set: ValidationSet = dict(DEFAULT_VALIDATION_SET)

    if not validation_json_path:
        logger.info(
            "No validation JSON path provided, using default validation set"
        )
        return validation_set

    data = load_json_file(validation_json_path, enable_logger=True)
    customized = data.get("customized_validation_set", {})

    if not isinstance(customized, dict):
        return validation_set

    platform_data = customized.get(platform)
    if not isinstance(platform_data, dict):
        logger.info(
            "No customized validation set for platform: '%s', using defaults",
            platform,
        )
        return validation_set

    device_data = platform_data.get(device)
    if not isinstance(device_data, dict):
        logger.info(
            "No customized validation set for device: '%s', using defaults",
            device,
        )
        return validation_set

    for key, value in device_data.items():
        if isinstance(key, str):
            validation_set[key] = (
                value if isinstance(value, str) else str(value)
            )

    return validation_set


def cmd_detect(clinfo_executable_json_path: str) -> int:
    command = _resolve_clinfo_command(clinfo_executable_json_path)
    if command is None:
        return 1

    version_result = _run_clinfo_command(command + " -v", capture_output=False)
    if version_result.returncode != 0:
        logger.error("Unable to query clinfo version")
        return version_result.returncode

    list_result = _run_clinfo_command(command + " -l")
    if list_result.returncode != 0:
        if list_result.stderr:
            logger.error(list_result.stderr.rstrip())
        return list_result.returncode

    logger.info(
        "OpenCL platform/device list:\n%s",
        list_result.stdout.rstrip(),
    )

    has_platform = any(
        PLATFORM_PATTERN.match(line)
        for line in list_result.stdout.splitlines()
    )
    if not has_platform:
        logger.error(
            "No OpenCL platform found! "
            "(OpenCL runtime may not be installed)"
        )
        return 1

    records = parse_clinfo_list_output(list_result.stdout)
    if not records:
        logger.error(
            "OpenCL platform detected but no device found! "
            "(runtime installed but no usable device)"
        )
        return 1

    return 0


def cmd_resource(
    clinfo_executable_json_path: str,
    validation_json_path: str,
) -> int:
    command = _resolve_clinfo_command(clinfo_executable_json_path)
    if command is None:
        return 1

    list_result = _run_clinfo_command(command + " -l")
    if list_result.returncode != 0:
        if list_result.stderr:
            logger.error(list_result.stderr.rstrip())
        return list_result.returncode

    records = parse_clinfo_list_output(list_result.stdout)
    ignored_pairs = parse_ignored_set(validation_json_path)

    for record in records:
        is_ignored = (record["platform"], record["device"]) in ignored_pairs
        print("platform: {}".format(record["platform"]))
        print("platform_number: {}".format(record["platform_number"]))
        print("device: {}".format(record["device"]))
        print("device_number: {}".format(record["device_number"]))
        print("ignore: {}".format("true" if is_ignored else "false"))
        print("")

    return 0


def cmd_test(
    clinfo_executable_json_path: str,
    validation_json_path: str,
    platform: str,
    platform_number: int,
    device: str,
    device_number: int,
) -> int:
    """Validate selected OpenCL device properties."""
    command = _resolve_clinfo_command(clinfo_executable_json_path)
    if command is None:
        return 1

    validation_set = load_validation_set(
        validation_json_path,
        platform,
        device,
    )

    logger.info(
        "Validating OpenCL properties for platform: '%s', device: '%s'",
        platform,
        device,
    )
    target = "{}:{}".format(platform_number, device_number)
    validated_properties = []
    mismatches = []
    for prop_name, expected_value in validation_set.items():
        prop_result = _run_clinfo_command(
            "{} -d {} --prop {}".format(command, target, prop_name)
        )
        if prop_result.returncode != 0:
            error_text = prop_result.stderr.strip() or prop_result.stdout.strip()
            mismatches.append(
                "{}: command failed ({}) {}".format(
                    prop_name,
                    prop_result.returncode,
                    error_text,
                )
            )
            continue

        actual_value = parse_property_value(prop_result.stdout, prop_name)
        if actual_value is None:
            mismatches.append("{}: property output not found".format(prop_name))
            continue

        if actual_value != expected_value:
            mismatches.append(
                "{}: expected {}, got {}".format(
                    prop_name,
                    expected_value,
                    actual_value,
                )
            )
            continue

        validated_properties.append(
            "{}: {}".format(prop_name, actual_value)
        )

    if validated_properties:
        logger.info("Validated OpenCL properties:")
        for validated_property in validated_properties:
            logger.info("\t%s", validated_property)

    if mismatches:
        logger.error("Failed OpenCL properties:")
        for mismatch in mismatches:
            logger.error("\t%s", mismatch)
        return 1

    logger.info(
        "PASS: OpenCL validation passed (platform: '%s', device: '%s')",
        platform,
        device
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)

    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "-cejp",
        "--clinfo-executable-json-path",
        default="",
        help="path to JSON file describing the customized clinfo executable",
    )
    common_parser.add_argument(
        "--debug",
        action="store_true",
        help="enable debug logging",
    )

    subparsers.add_parser("detect", parents=[common_parser])

    resource_parser = subparsers.add_parser(
        "resource", parents=[common_parser]
    )
    resource_parser.add_argument(
        "-vjp",
        "--validation-json-path",
        default="",
        help="path to validation JSON file (reads ignored_set)",
    )

    test_parser = subparsers.add_parser("test", parents=[common_parser])
    test_parser.add_argument(
        "-vjp",
        "--validation-json-path",
        default="",
        help="path to validation JSON file (reads customized_validation_set)",
    )
    test_parser.add_argument(
        "-p",
        "--platform",
        required=True,
        help="OpenCL platform name",
    )
    test_parser.add_argument(
        "-pn",
        "--platform-number",
        required=True,
        help="OpenCL platform number",
    )
    test_parser.add_argument(
        "-d",
        "--device",
        required=True,
        help="OpenCL device name",
    )
    test_parser.add_argument(
        "-dn",
        "--device-number",
        required=True,
        help="OpenCL device number",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.action == "detect":
        return cmd_detect(args.clinfo_executable_json_path)
    if args.action == "resource":
        return cmd_resource(
            args.clinfo_executable_json_path,
            args.validation_json_path,
        )
    if args.action == "test":
        return cmd_test(
            args.clinfo_executable_json_path,
            args.validation_json_path,
            args.platform,
            args.platform_number,
            args.device,
            args.device_number,
        )

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
