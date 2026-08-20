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

import argparse
import logging
import os
import json
from pathlib import Path

from typing import Any, Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s - %(module)-10s: %(funcName)s "
    + "%(lineno)-4d - %(message)s",
)

logger = logging.getLogger(__name__)

I2CTRANSFER_CMD = "i2ctransfer"

def load_json_file(
    json_file_path: str,
    enable_logger: bool = False,
) -> Dict[str, Any]:
    """Load a JSON file and return its contents as a dictionary.
    
        Does not raise exceptions for missing or unreadable files; instead,
        it returns an empty dictionary. Let the caller handle the case of an empty
        dictionary if needed.
    """

    if not json_file_path or not isinstance(json_file_path, str):
        if enable_logger:
            logging.warning(
                "Empty JSON file path provided, returning empty dictionary"
            )
        return {}

    resolved_path = os.path.join(os.getenv("PLAINBOX_PROVIDER_DATA", ""), json_file_path)
    if not Path(resolved_path).exists():
        resolved_path = json_file_path

    try:
        if enable_logger:
            logging.info("Attempting to load JSON file: %s", resolved_path)
        with open(resolved_path, "r", encoding="utf-8") as file_obj:
            return json.load(file_obj)
    except FileNotFoundError:
        if enable_logger:
            logging.warning("JSON file not found: %s", resolved_path)
        return {}
    except (PermissionError, json.JSONDecodeError, OSError):
        if enable_logger:
            logging.warning("Failed to load JSON file: %s", resolved_path)
        return {}

def get_i2c_scenarios(enable_logger: bool = False) -> dict:
    scenario_file_path = load_json_file(
        os.getenv("I2C_SPECIFIC_SCENARIO_FILE_PATH", ""), enable_logger=enable_logger
    )
    return scenario_file_path

def cmd_resource() -> int:
    scenarios = get_i2c_scenarios()
    for _, k in enumerate(scenarios):
        print("scenario_name: {}".format(k))
        print("")
    return 0

def cmd_test(scenario_name: str) -> int:
    logger.info("Executing test for scenario: %s", scenario_name)
    scenarios = get_i2c_scenarios(enable_logger=True)
    if scenario_name not in scenarios:
        logger.error("Scenario '%s' not found in the scenarios file.", scenario_name)
        logger.info("Available scenarios: %s", list(scenarios.keys()))
        return 1
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

    # common_parser.add_argument(
    #     "-irwp",
    #     "--i2c-read-write-json-path",
    #     default="",
    #     help="path to the i2c read and write specific scenario JSON file",
    # )

    subparsers.add_parser("resource", parents=[common_parser], help="Generate the resource of i2c read and write scenario from an external JSON file")

    test_parser = subparsers.add_parser("test", parents=[common_parser], help="Execute the i2c read and write case based on the scenario name")

    test_parser.add_argument(
        "-sn",
        "--scenario-name",
        required=True,
        help="The scenario name to be tested which is defined in the i2c read and write specific scenario JSON file, e.g. 'FT24C32 EEPROM Basic Write-Read'",
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
        return cmd_test(args.scenario_name,)

    parser.print_help()
    return 1


if __name__ == "__main__":
    exit(main())