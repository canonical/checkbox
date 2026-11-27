#!/usr/bin/env python3
"""List and test RS485 Modbus RTU peripherals."""

import argparse
import re
from typing import Callable, List

EXPECTED_FORMAT = (
    "NAME:NODE:BAUDRATE:UNIT_ID:REGISTER_TYPE:REGISTER_ADDRESS:"
    "REGISTER_COUNT:PARITY"
)
REGISTER_TYPES = ("holding", "input")


def sanitize_id(value):
    """Return a short identifier safe for generated Checkbox job IDs."""

    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


class RS485ModbusPeripheral:
    """A configured RS485 Modbus peripheral."""

    def __init__(
        self,
        name,
        node,
        baudrate,
        unit_id,
        register_type,
        register_address,
        register_count,
        parity,
    ):
        self.name = name
        self.node = node
        self.baudrate = baudrate
        self.unit_id = unit_id
        self.register_type = register_type
        self.register_address = register_address
        self.register_count = register_count
        self.parity = parity

    @property
    def name_id(self) -> str:
        """Return the configured name normalized for generated job IDs."""

        return sanitize_id(self.name)

    @property
    def node_id(self) -> str:
        """Return a short node identifier safe for generated job IDs."""

        return sanitize_id(self.node)


class ModbusReadConfig:
    """Configuration for one Modbus RTU register read."""

    def __init__(
        self,
        port,
        baudrate,
        unit_id,
        register_type,
        address,
        count,
        parity,
    ):
        self.port = port
        self.baudrate = baudrate
        self.unit_id = unit_id
        self.register_type = register_type
        self.address = address
        self.count = count
        self.parity = parity


def _parse_positive_int(raw_value, field_name):
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError("{} must be an integer".format(field_name)) from exc
    if value < 1:
        raise ValueError("{} must be greater than 0".format(field_name))
    return value


def _parse_non_negative_int(raw_value, field_name):
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError("{} must be an integer".format(field_name)) from exc
    if value < 0:
        raise ValueError("{} must be 0 or greater".format(field_name))
    return value


def positive_int(raw_value):
    """Parse a positive integer for argparse."""

    try:
        return _parse_positive_int(raw_value, "value")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def non_negative_int(raw_value):
    """Parse a non-negative integer for argparse."""

    try:
        return _parse_non_negative_int(raw_value, "value")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def parse_peripheral(entry: str) -> RS485ModbusPeripheral:
    """Parse one RS485 Modbus peripheral configuration entry."""

    parts = entry.split(":")
    if len(parts) != 8:
        raise ValueError("invalid format, expected {}".format(EXPECTED_FORMAT))

    (
        name,
        node,
        baudrate,
        unit_id,
        register_type,
        register_address,
        register_count,
        parity,
    ) = parts

    if not name:
        raise ValueError("NAME must not be empty")
    if not sanitize_id(name):
        raise ValueError("NAME must contain an ID-safe character")
    if not node:
        raise ValueError("NODE must not be empty")
    if not sanitize_id(node):
        raise ValueError("NODE must contain an ID-safe character")

    normalized_register_type = register_type.lower()
    if normalized_register_type not in REGISTER_TYPES:
        raise ValueError(
            "REGISTER_TYPE must be one of: {}".format(
                ", ".join(REGISTER_TYPES)
            )
        )

    normalized_parity = parity.upper()
    if normalized_parity not in ("N", "E", "O"):
        raise ValueError("PARITY must be one of: N, E, O")

    return RS485ModbusPeripheral(
        name=name,
        node=node,
        baudrate=_parse_positive_int(baudrate, "BAUDRATE"),
        unit_id=_parse_positive_int(unit_id, "UNIT_ID"),
        register_type=normalized_register_type,
        register_address=_parse_non_negative_int(
            register_address, "REGISTER_ADDRESS"
        ),
        register_count=_parse_positive_int(register_count, "REGISTER_COUNT"),
        parity=normalized_parity,
    )


def parse_peripherals(config: str) -> List[RS485ModbusPeripheral]:
    """Parse a space-separated RS485 Modbus peripheral configuration."""

    return [parse_peripheral(entry) for entry in config.split()]


def print_peripherals_config(config: str) -> None:
    """Print Checkbox resource records for configured peripherals."""

    for peripheral in parse_peripherals(config):
        print("name: {}".format(peripheral.name))
        print("name_id: {}".format(peripheral.name_id))
        print("node: {}".format(peripheral.node))
        print("node_id: {}".format(peripheral.node_id))
        print("baudrate: {}".format(peripheral.baudrate))
        print("unit_id: {}".format(peripheral.unit_id))
        print("register_type: {}".format(peripheral.register_type))
        print("register_address: {}".format(peripheral.register_address))
        print("register_count: {}".format(peripheral.register_count))
        print("parity: {}".format(peripheral.parity))
        print()


def create_modbus_client(config: ModbusReadConfig):
    """Create a pymodbus RTU serial client.

    The import supports both pymodbus 2.x and 3.x module layouts.
    """

    try:
        from pymodbus.client import ModbusSerialClient
    except ImportError:
        from pymodbus.client.sync import ModbusSerialClient

    client_args = {
        "port": config.port,
        "baudrate": config.baudrate,
        "parity": config.parity,
        "stopbits": 1,
        "bytesize": 8,
        "timeout": 3,
    }
    try:
        return ModbusSerialClient(method="rtu", **client_args)
    except TypeError:
        return ModbusSerialClient(framer="rtu", **client_args)


def read_registers(config, client):
    """Read registers from an open Modbus client."""

    if config.register_type == "holding":
        read_method = client.read_holding_registers
    elif config.register_type == "input":
        read_method = client.read_input_registers
    else:
        raise ValueError(
            "unsupported register type: {}".format(config.register_type)
        )

    for unit_id_keyword in ("slave", "unit", "device_id"):
        try:
            result = read_method(
                config.address,
                count=config.count,
                **{unit_id_keyword: config.unit_id}
            )
            break
        except TypeError:
            if unit_id_keyword == "device_id":
                raise

    if result.isError():
        raise RuntimeError("Modbus error response: {}".format(result))

    registers = getattr(result, "registers", None)
    if registers is None:
        raise RuntimeError("Modbus response does not contain registers")

    return list(registers)


def run_modbus_read(
    config: ModbusReadConfig,
    client_factory: Callable[
        [ModbusReadConfig], object
    ] = create_modbus_client,
):
    """Connect to a Modbus peripheral and read configured registers."""

    client = client_factory(config)
    try:
        if not client.connect():
            raise RuntimeError("Failed to connect to {}".format(config.port))
        return read_registers(config, client)
    finally:
        client.close()


def build_read_config(args):
    """Build a Modbus read config from parsed CLI arguments."""

    return ModbusReadConfig(
        port=args.port,
        baudrate=args.baudrate,
        unit_id=args.unit_id,
        register_type=args.register_type,
        address=args.address,
        count=args.count,
        parity=args.parity,
    )


def list_command(args):
    """Run the list subcommand."""

    try:
        print_peripherals_config(args.config)
    except ValueError as exc:
        print("Error: {}".format(exc))
        raise SystemExit(1)


def read_command(args):
    """Run the read subcommand."""

    config = build_read_config(args)
    try:
        registers = run_modbus_read(config)
    except (RuntimeError, ValueError) as exc:
        print("Error: {}".format(exc))
        raise SystemExit(1)

    print("registers: {}".format(" ".join(str(value) for value in registers)))


def write_command(args):
    """Run the write subcommand."""

    print("Error: Modbus write is not implemented")
    raise SystemExit(1)


def build_parser():
    """Build the rs485_modbus_test command-line parser."""

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser(
        "list",
        help="Print Checkbox resources from RS485_MODBUS_PERIPHERALS",
    )
    list_parser.add_argument(
        "config",
        help=(
            "Space-separated entries using the format "
            "{}".format(EXPECTED_FORMAT)
        ),
    )
    list_parser.set_defaults(entry_func=list_command)

    read_parser = subparsers.add_parser(
        "read",
        help="Read raw registers from an RS485 Modbus peripheral",
    )
    read_parser.add_argument("--port", required=True)
    read_parser.add_argument("--baudrate", required=True, type=positive_int)
    read_parser.add_argument("--unit-id", required=True, type=positive_int)
    read_parser.add_argument(
        "--register-type",
        required=True,
        choices=REGISTER_TYPES,
    )
    read_parser.add_argument("--address", required=True, type=non_negative_int)
    read_parser.add_argument("--count", required=True, type=positive_int)
    read_parser.add_argument(
        "--parity",
        required=True,
        choices=("N", "E", "O"),
        type=str.upper,
    )
    read_parser.set_defaults(entry_func=read_command)

    write_parser = subparsers.add_parser(
        "write",
        help="Reserved for future RS485 Modbus write tests",
    )
    write_parser.set_defaults(entry_func=write_command)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "entry_func"):
        parser.print_usage()
        raise SystemExit(1)
    args.entry_func(args)


if __name__ == "__main__":
    main()
