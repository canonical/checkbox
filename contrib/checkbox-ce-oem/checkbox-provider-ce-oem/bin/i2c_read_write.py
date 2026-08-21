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
import re
import subprocess
import time
from pathlib import Path

from typing import Any, Dict, List

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s - %(module)-10s: %(funcName)s "
    + "%(lineno)-4d - %(message)s",
)

logger = logging.getLogger(__name__)

I2CTRANSFER_CMD = "i2ctransfer"


def _normalize_hex_byte(value: Any, field_name: str) -> str:
    """Validate a byte value and return canonical form like 0x1a.

    Examples:
        input: value="0xA", field_name="data"
        output: "0x0a"

        input: value=255, field_name="data"
        output: "0xff"

        input: value="0x1ff", field_name="data"
        output: ValueError

    Raises:
        ValueError: If the value is not a valid single byte.
    """
    if isinstance(value, str):
        stripped = value.strip().lower()
        if re.fullmatch(r"0x[0-9a-f]{1,2}", stripped):
            return "0x{:02x}".format(int(stripped, 16))
        raise ValueError("Invalid byte in '{}' : {!r}".format(field_name, value))

    if isinstance(value, int) and 0 <= value <= 0xFF:
        return "0x{:02x}".format(value)

    raise ValueError("Invalid byte in '{}' : {!r}".format(field_name, value))


def _normalize_hex_byte_list(value: Any, field_name: str) -> List[str]:
    """Validate a list of bytes and return canonical list.

    Examples:
        input: value=["0x1", "0xA", 255], field_name="reg_address"
        output: ["0x01", "0x0a", "0xff"]

        input: value="0x01", field_name="reg_address"
        output: ValueError

    Raises:
        ValueError: If the field is not a list of valid byte values.
    """
    if not isinstance(value, list):
        raise ValueError("Field '{}' must be a list of bytes.".format(field_name))

    result: List[str] = []
    for item in value:
        normalized = _normalize_hex_byte(item, field_name)
        result.append(normalized)
    return result


def _normalize_chip_address(value: Any) -> str:
    """Validate I2C chip address and return canonical hexadecimal format.

    Examples:
        input: value="0x50"
        output: "0x50"

        input: value=80
        output: "0x50"

        input: value="0x80"
        output: ValueError  # out of 7-bit I2C address range

    Raises:
        ValueError: If chip_address is invalid or out of 7-bit range.
    """
    if isinstance(value, str):
        stripped = value.strip().lower()
        if re.fullmatch(r"0x[0-9a-f]{1,2}", stripped):
            addr = int(stripped, 16)
        else:
            raise ValueError("Invalid chip_address: {!r}".format(value))
    elif isinstance(value, int):
        addr = value
    else:
        raise ValueError("Invalid chip_address type: {!r}".format(value))

    if not 0 <= addr <= 0x7F:
        raise ValueError("chip_address out of 7-bit range: {!r}".format(value))
    return "0x{:02x}".format(addr)


def _run_i2c_transfer(bus: int, messages: List[str]) -> subprocess.CompletedProcess:
    """Run a single i2ctransfer command and return the process result.

    Raises:
        RuntimeError: If command execution fails.
    """
    cmd = [I2CTRANSFER_CMD, "-y", str(bus)]
    for message in messages:
        cmd.extend(message.split())
    logger.info("Run command: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise RuntimeError("{} command not found.".format(I2CTRANSFER_CMD))
    except OSError as err:
        raise RuntimeError(
            "Failed to run {}: {}".format(I2CTRANSFER_CMD, err)
        )

    if result.returncode != 0:
        raise RuntimeError(
            "{} failed (rc={}). stderr={}".format(
                I2CTRANSFER_CMD,
                result.returncode,
                result.stderr.strip(),
            )
        )

    return result


def _extract_hex_bytes(output: str) -> List[str]:
    """Extract hexadecimal bytes from i2ctransfer output."""
    matches = re.findall(r"0x[0-9a-fA-F]{1,2}", output)
    return ["0x{:02x}".format(int(item, 16)) for item in matches]

def load_json_file(
    json_file_path: str,
    enable_logger: bool = False,
) -> Dict[str, Any]:
    """Load a JSON file and return its content as a dictionary.

    Args:
        json_file_path: Path to the JSON file. Relative paths are first
            resolved under PLAINBOX_PROVIDER_DATA.
        enable_logger: Whether to emit info/warning logs while loading.

    Returns:
        Parsed JSON object as a dictionary. Returns an empty dictionary
        when the input path is invalid, the file is missing, or parsing fails.
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
    """Load scenario definitions from I2C_SPECIFIC_SCENARIO_FILE_PATH.

    Args:
        enable_logger: Whether to enable logging while loading the JSON file.

    Returns:
        Scenario mapping loaded from the JSON file, or an empty dictionary.
    """
    scenario_file_path = load_json_file(
        os.getenv("I2C_SPECIFIC_SCENARIO_FILE_PATH", ""), enable_logger=enable_logger
    )
    return scenario_file_path


def _execute_write_step(
    step: Dict[str, Any],
    i2c_bus: int,
    chip_address: str,
    reg_address: List[str],
    variables: Dict[str, List[str]],
) -> bool:
    """Execute one I2C write step.

    Args:
        step: Step definition dictionary for a write operation.
        i2c_bus: Target I2C bus number.
        chip_address: Target chip address in normalized hex form.
        reg_address: Optional register-address bytes to prepend.
        variables: Stored values from previous read steps.

    Returns:
        True when the write step completes successfully, otherwise False.
    """
    has_data = "data" in step
    has_data_from_variable = "data_from_variable" in step
    if has_data == has_data_from_variable:
        logger.error(
            "Write step must contain exactly one of "
            "'data' or 'data_from_variable'.",
        )
        return False

    if has_data:
        try:
            write_data = _normalize_hex_byte_list(step.get("data"), "data")
        except ValueError as err:
            logger.error("Write step has invalid data: %s", err)
            return False
        if not write_data:
            logger.error("Write step has invalid data.")
            return False
    else:
        # Conditionally optional field: used when write data
        # comes from a previous read step.
        variable_name = step.get("data_from_variable")
        if not isinstance(variable_name, str) or not variable_name:
            logger.error("Write step has invalid data_from_variable.")
            return False
        if variable_name not in variables:
            logger.error(
                "Write step references undefined variable: %s",
                variable_name,
            )
            return False
        write_data = variables[variable_name]

    payload = reg_address + write_data
    if not payload:
        logger.error("Write step has empty write payload.")
        return False

    write_message = "w{}@{} {}".format(
        len(payload), chip_address, " ".join(payload)
    )
    try:
        _run_i2c_transfer(i2c_bus, [write_message])
    except RuntimeError as err:
        logger.error("%s", err)
        return False

    return True


def _execute_read_step(
    step: Dict[str, Any],
    i2c_bus: int,
    chip_address: str,
    reg_address: List[str],
    variables: Dict[str, List[str]],
) -> bool:
    """Execute one I2C read step.

    Args:
        step: Step definition dictionary for a read operation.
        i2c_bus: Target I2C bus number.
        chip_address: Target chip address in normalized hex form.
        reg_address: Optional register-address bytes used as read pointer.
        variables: Storage for values shared across steps.

    Returns:
        True when the read step completes successfully, otherwise False.
    """
    read_length = step.get("read_length")
    if not isinstance(read_length, int) or read_length <= 0:
        logger.error("Read step requires positive integer read_length.")
        return False

    messages: List[str] = []
    if reg_address:
        reg_write_message = "w{}@{} {}".format(
            len(reg_address), chip_address, " ".join(reg_address)
        )
        messages.append(reg_write_message)
    messages.append("r{}@{}".format(read_length, chip_address))

    try:
        result = _run_i2c_transfer(i2c_bus, messages)
    except RuntimeError as err:
        logger.error("%s", err)
        return False

    read_values = _extract_hex_bytes(result.stdout)
    if len(read_values) < read_length:
        logger.error(
            "Read step expected %d bytes, but got %d from output: %r",
            read_length,
            len(read_values),
            result.stdout.strip(),
        )
        return False
    read_values = read_values[:read_length]
    logger.info("Read values: %s", " ".join(read_values))

    # Optional field: save read bytes for later write steps.
    save_to_variable = step.get("save_to_variable")
    if save_to_variable is not None:
        if not isinstance(save_to_variable, str) or not save_to_variable:
            logger.error("Read step has invalid save_to_variable.")
            return False
        variables[save_to_variable] = read_values
        logger.info(
            "Stored read values to variable '%s'.", save_to_variable
        )

    # Optional field: assert fixed expected bytes when provided.
    if "expected_output" in step:
        try:
            expected_output = _normalize_hex_byte_list(
                step.get("expected_output"), "expected_output"
            )
        except ValueError as err:
            logger.error("Read step has invalid expected_output: %s", err)
            return False
        if read_values != expected_output:
            logger.error(
                "Read step mismatch. expected=%s actual=%s",
                " ".join(expected_output),
                " ".join(read_values),
            )
            return False
        logger.info("expected_output verification passed.")

    return True

def cmd_resource() -> int:
    """Print all available scenario names as resource output.

    Returns:
        Exit status code. Returns 0 when output is generated.
    """
    scenarios = get_i2c_scenarios()
    for _, k in enumerate(scenarios):
        print("scenario_name: {}".format(k))
        print("")
    return 0

def cmd_test(scenario_name: str) -> int:
    """Execute an I2C test scenario by name.

    Args:
        scenario_name: Scenario key in the JSON file to execute.

    Returns:
        Exit status code. Returns 0 on success, 1 on validation or runtime
        failure.
    """
    logger.info("Executing test for scenario: %s", scenario_name)
    scenarios = get_i2c_scenarios(enable_logger=True)

    if scenario_name not in scenarios:
        logger.error("Scenario '%s' not found in the scenarios file.", scenario_name)
        logger.info("Available scenarios: %s", list(scenarios.keys()))
        return 1

    scenario = scenarios[scenario_name]
    steps = scenario.get("steps")
    if not isinstance(steps, list) or not steps:
        logger.error("Scenario '%s' has no valid steps.", scenario_name)
        return 1

    variables: Dict[str, List[str]] = {}

    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            logger.error("Step #%d is not a JSON object.", idx)
            return 1

        description = step.get("description", "")
        operation = step.get("operation")
        i2c_bus = step.get("i2c_bus")
        try:
            chip_address = _normalize_chip_address(step.get("chip_address"))
        except ValueError as err:
            logger.error("Step #%d has invalid chip_address: %s", idx, err)
            return 1

        if not isinstance(description, str) or not description.strip():
            logger.error("Step #%d is missing a valid 'description'.", idx)
            return 1
        if operation not in ("write", "read"):
            logger.error("Step #%d has invalid operation: %r", idx, operation)
            return 1
        if not isinstance(i2c_bus, int) or i2c_bus < 0:
            logger.error("Step #%d has invalid i2c_bus: %r", idx, i2c_bus)
            return 1
        # Optional field: reg_address is only needed for devices
        # that require an internal register/memory pointer.
        reg_address: List[str] = []
        if "reg_address" in step:
            try:
                normalized_reg = _normalize_hex_byte_list(
                    step.get("reg_address"), "reg_address"
                )
            except ValueError as err:
                logger.error("Step #%d has invalid reg_address: %s", idx, err)
                return 1
            reg_address = normalized_reg

        # Optional field: delay_ms defaults to 0 when omitted.
        delay_ms = step.get("delay_ms", 0)
        if not isinstance(delay_ms, int) or delay_ms < 0:
            logger.error("Step #%d has invalid delay_ms: %r", idx, delay_ms)
            return 1

        logger.info("Step #%d: %s", idx, description)

        if operation == "write":
            if not _execute_write_step(
                step,
                i2c_bus,
                chip_address,
                reg_address,
                variables,
            ):
                return 1

        elif operation == "read":
            if not _execute_read_step(
                step,
                i2c_bus,
                chip_address,
                reg_address,
                variables,
            ):
                return 1

        if delay_ms > 0:
            logger.info("Delay %d ms", delay_ms)
            time.sleep(delay_ms / 1000.0)

    logger.info("Scenario '%s' completed successfully.", scenario_name)
    return 0

def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for this script.

    Returns:
        Configured ArgumentParser with resource/test subcommands.
    """
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)

    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--debug",
        action="store_true",
        help="enable debug logging",
    )

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