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
  detect    Verify clinfo exists and that at least one platform/device exists.
  resource  Emit platform/device records for Checkbox resource jobs.
  test      Placeholder validation command (currently same detection baseline).
"""

import argparse
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any, List, Optional, Sequence, Set, Tuple, TypedDict


PLATFORM_PATTERN = re.compile(r"^\s*Platform\s+#(\d+):\s*(.+?)\s*$")
DEVICE_PATTERN = re.compile(r"^\s*[`|]--\s*Device\s+#(\d+):\s*(.+?)\s*$")
PAIR_PATTERN = re.compile(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]")

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


def resolve_binary(binary_name: str) -> Optional[str]:
    """Resolve a binary path from explicit path or PATH lookup."""
    if os.path.sep in binary_name:
        if os.path.isfile(binary_name) and os.access(binary_name, os.X_OK):
            return binary_name
        binary_path = None
    else:
        binary_path = shutil.which(binary_name)

    if binary_path is None:
        logger.error("clinfo binary not found: %s", binary_name)

    return binary_path


def run_clinfo(
    binary_path: str,
    args: Sequence[str],
    capture_output: bool = False,
) -> subprocess.CompletedProcess:
    """Run clinfo and return a CompletedProcess object."""
    return subprocess.run(
        [binary_path, *args],
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


def parse_json_pairs(payload: str) -> Set[Tuple[str, str]]:
    """Parse ignore pairs from JSON string or object."""
    parsed: Any = json.loads(payload)
    ignored: Set[Tuple[str, str]] = set()

    if isinstance(parsed, dict):
        for platform, devices in parsed.items():
            if isinstance(platform, str) and isinstance(devices, str):
                ignored.add((platform, devices))
            elif isinstance(platform, str) and isinstance(devices, list):
                for device in devices:
                    if isinstance(device, str):
                        ignored.add((platform, device))
        return ignored

    if isinstance(parsed, list):
        for item in parsed:
            if not isinstance(item, dict):
                continue
            platform = item.get("platform")
            device = item.get("device")
            if isinstance(platform, str) and isinstance(device, str):
                ignored.add((platform, device))
        return ignored

    return ignored


def parse_ignore_spec(spec: str) -> Set[Tuple[str, str]]:
    """Parse ignore spec from raw pairs, json text, or JSON file path."""
    if not spec or not spec.strip():
        return set()

    raw_spec = spec.strip()
    if os.path.isfile(raw_spec):
        with open(raw_spec, "r", encoding="utf-8") as file_obj:
            raw_spec = file_obj.read().strip()

    if not raw_spec:
        return set()

    ignored_pairs: Set[Tuple[str, str]] = set()
    try:
        ignored_pairs |= parse_json_pairs(raw_spec)
    except (json.JSONDecodeError, TypeError):
        pass

    for platform, device in PAIR_PATTERN.findall(raw_spec):
        ignored_pairs.add((platform, device))

    if ignored_pairs:
        return ignored_pairs

    for part in raw_spec.split(","):
        if ":" not in part:
            continue
        platform, device = part.split(":", 1)
        platform = platform.strip(" ' \"")
        device = device.strip(" ' \"")
        if platform and device:
            ignored_pairs.add((platform, device))

    return ignored_pairs


def cmd_detect(binary: str) -> int:
    binary_path = resolve_binary(binary)
    if binary_path is None:
        return 1

    version_result = run_clinfo(binary_path, ["-v"])
    if version_result.returncode != 0:
        logger.error(
            "Unable to query clinfo version using %s", binary_path
        )
        return version_result.returncode

    list_result = run_clinfo(binary_path, ["-l"], capture_output=True)
    if list_result.returncode != 0:
        if list_result.stderr:
            logger.error(list_result.stderr.rstrip())
        return list_result.returncode

    records = parse_clinfo_list_output(list_result.stdout)
    if not records:
        logger.error("No OpenCL platform/device found!")
        return 1
    logger.info(": \n%s\n\nPASS: OpenCL platform/device detected", list_result.stdout.rstrip())

    return 0


def cmd_resource(binary: str, ignore: str) -> int:
    binary_path = resolve_binary(binary)
    if binary_path is None:
        return 1

    list_result = run_clinfo(binary_path, ["-l"], capture_output=True)
    if list_result.returncode != 0:
        if list_result.stderr:
            logger.error(list_result.stderr.rstrip())
        return list_result.returncode

    records = parse_clinfo_list_output(list_result.stdout)
    ignored_pairs = parse_ignore_spec(ignore)

    for record in records:
        is_ignored = (record["platform"], record["device"]) in ignored_pairs
        print("platform: {}".format(record["platform"]))
        print("platform_number: {}".format(record["platform_number"]))
        print("device: {}".format(record["device"]))
        print("device_number: {}".format(record["device_number"]))
        print("ignore: {}".format("true" if is_ignored else "false"))
        print("")

    return 0


def cmd_test(binary: str, validation_json_path: str) -> int:
    """Run baseline validation. Full validation flow is pending."""
    if validation_json_path:
        if not os.path.isfile(validation_json_path):
            logger.error(
                "validation json file not found: %s",
                validation_json_path,
            )
            return 1

    return cmd_detect(binary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)

    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "-b",
        "--binary",
        default="clinfo",
        help="clinfo executable path or command name",
    )

    subparsers.add_parser("detect", parents=[common_parser])

    resource_parser = subparsers.add_parser(
        "resource", parents=[common_parser]
    )
    resource_parser.add_argument(
        "-i",
        "--ignore",
        default="",
        help="ignored platform/device pairs or path to JSON file",
    )

    test_parser = subparsers.add_parser("test", parents=[common_parser])
    test_parser.add_argument(
        "-vjp",
        "--validation-json-path",
        default="",
        help="path to validation json file",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.action == "detect":
        return cmd_detect(args.binary)
    if args.action == "resource":
        return cmd_resource(args.binary, args.ignore)
    if args.action == "test":
        return cmd_test(args.binary, args.validation_json_path)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
