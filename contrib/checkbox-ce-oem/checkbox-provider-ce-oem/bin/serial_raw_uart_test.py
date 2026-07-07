#!/usr/bin/env python3
"""List and test raw UART loopback devices for CE OEM serial jobs."""

import argparse
import fcntl
import glob
import os
import re
import struct
import time

import serial

TIOCGSERIAL = 0x541E
SERIAL_STRUCT_FORMAT = "iiiiiiiiiiiHHi"
RAW_UART_CONFIG_FORMAT = "NAME:TARGET:BAUD"
BAUD_MODES = ("max", "sweep", "autoscan-max")
PING_PATTERN = b"PING"
USB_SERIAL_PREFIXES = ("ttyUSB", "ttyACM")
STANDARD_RATES = [
    9600,
    19200,
    38400,
    57600,
    115200,
    230400,
    460800,
    500000,
    576000,
    921600,
    1000000,
    1152000,
    1500000,
    2000000,
    2500000,
    3000000,
    3500000,
    4000000,
]
DRIVER_DEV_PREFIX = {
    "serial": "ttyS",
    "fsl-lpuart": "ttyLP",
    "IMX-uart": "ttymxc",
    "max310x": "ttyMAX",
    "ttyAMA": "ttyAMA",
}


class RawUartPort:
    """A configured raw UART loopback target."""

    def __init__(self, name, target, baud):
        self.name = name
        self.target = target
        self.baud = baud
        self.target_type = "node" if target.startswith("/dev/") else "addr"

    @property
    def name_id(self):
        """Return the configured name normalized for generated job IDs."""

        return sanitize_id(self.name)

    @property
    def target_id(self):
        """Return the configured target normalized for generated job IDs."""

        return sanitize_id(self.target)


class UartDevice:
    """Resolved raw UART device metadata."""

    def __init__(self, target, dev_node, baud_base, is_console):
        self.target = target
        self.dev_node = dev_node
        self.baud_base = baud_base
        self.is_console = is_console


class LoopbackResult:
    """Result of a single loopback test."""

    def __init__(self, baud_rate, passed, message):
        self.baud_rate = baud_rate
        self.passed = passed
        self.message = message


def sanitize_id(value):
    """Return a short identifier safe for generated Checkbox job IDs."""

    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def parse_positive_int(raw_value, field_name):
    """Parse a positive integer or raise a field-specific ValueError."""

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError("{} must be an integer".format(field_name)) from exc
    if value < 1:
        raise ValueError("{} must be greater than 0".format(field_name))
    return value


def parse_baud(raw_value):
    """Parse a RAW_UART_PORTS baud value."""

    normalized = raw_value.lower()
    if normalized in BAUD_MODES:
        return normalized
    return parse_positive_int(raw_value, "BAUD")


def parse_raw_uart_port(entry):
    """Parse one RAW_UART_PORTS entry."""

    parts = entry.split(":")
    if len(parts) != 3:
        raise ValueError(
            "invalid format, expected {}".format(RAW_UART_CONFIG_FORMAT)
        )
    name, target, baud = parts
    if not name:
        raise ValueError("NAME must not be empty")
    if not sanitize_id(name):
        raise ValueError("NAME must contain an ID-safe character")
    if not target:
        raise ValueError("TARGET must not be empty")
    if not sanitize_id(target):
        raise ValueError("TARGET must contain an ID-safe character")
    return RawUartPort(name=name, target=target, baud=parse_baud(baud))


def parse_raw_uart_ports(config):
    """Parse space-separated RAW_UART_PORTS entries."""

    return [parse_raw_uart_port(entry) for entry in config.split()]


def format_baud(baud):
    """Return a resource-friendly baud string."""

    return str(baud)


def print_raw_uart_resources(config):
    """Print Checkbox resource records for configured raw UART ports."""

    for port in parse_raw_uart_ports(config):
        print("name: {}".format(port.name))
        print("name_id: {}".format(port.name_id))
        print("target: {}".format(port.target))
        print("target_id: {}".format(port.target_id))
        print("target_type: {}".format(port.target_type))
        print("baud: {}".format(format_baud(port.baud)))
        print()


def normalize_addr(addr):
    """Normalize a hardware address to lowercase hex form."""

    value = addr.lower().strip()
    if value.startswith("0x"):
        return value
    try:
        return hex(int(value))
    except ValueError:
        return value


def is_usb_serial_node(dev_node):
    """Return True if a device node looks like a USB serial adapter."""

    basename = os.path.basename(dev_node)
    return basename.startswith(USB_SERIAL_PREFIXES)


def get_driver_baud_base(device_path):
    """Return the kernel driver baud_base for a serial node, or 0."""

    try:
        fd = os.open(device_path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            serial_struct = struct.pack("i" * 19, *([0] * 19))
            result = fcntl.ioctl(fd, TIOCGSERIAL, serial_struct)
            unpacked = struct.unpack(
                SERIAL_STRUCT_FORMAT,
                result[: struct.calcsize(SERIAL_STRUCT_FORMAT)],
            )
            return unpacked[7]
        finally:
            os.close(fd)
    except (OSError, struct.error):
        return 0


def scan_available_uarts(raw_uart_only=True):
    """Scan Linux UART driver data and return address-to-node mappings."""

    results = {}
    for filepath in glob.glob("/proc/tty/driver/*"):
        driver_name = os.path.basename(filepath)
        if raw_uart_only and driver_name == "usb-serial":
            continue
        dev_prefix = DRIVER_DEV_PREFIX.get(driver_name)
        if not dev_prefix and "serial" in driver_name:
            dev_prefix = "ttyS"
        if not dev_prefix:
            continue

        try:
            with open(filepath, "r") as driver_file:
                for line in driver_file:
                    match = re.search(
                        r"^\s*(\d+):.*(?:mmio|port|I/O):\s*"
                        r"(0x[0-9a-fA-F]+|[0-9]+)",
                        line,
                    )
                    if not match or "uart:unknown" in line:
                        continue
                    index = match.group(1)
                    addr = normalize_addr(match.group(2))
                    results[addr] = "/dev/{}{}".format(dev_prefix, index)
        except (OSError, IOError):
            continue
    return results


def get_active_consoles():
    """Return active console tty basenames."""

    try:
        with open("/sys/class/tty/console/active", "r") as console_file:
            return set(console_file.read().strip().split())
    except (OSError, IOError):
        return set()


def resolve_device(target, allow_console=False, raw_uart_only=True):
    """Resolve a configured target to a usable raw UART device."""

    if target.startswith("/dev/"):
        dev_node = target
        resolved_target = target
    else:
        resolved_target = normalize_addr(target)
        uarts = scan_available_uarts(raw_uart_only=raw_uart_only)
        dev_node = uarts.get(resolved_target)
        if not dev_node:
            raise RuntimeError(
                "Raw UART target {} was not found".format(resolved_target)
            )

    if raw_uart_only and is_usb_serial_node(dev_node):
        raise RuntimeError(
            "USB serial adapters are not allowed for raw UART loopback"
        )

    is_console = os.path.basename(dev_node) in get_active_consoles()
    if is_console and not allow_console:
        raise RuntimeError("{} is an active system console".format(dev_node))

    return UartDevice(
        target=resolved_target,
        dev_node=dev_node,
        baud_base=get_driver_baud_base(dev_node),
        is_console=is_console,
    )


def get_rates_to_test(baud_base, baud):
    """Return baud rates for an integer or symbolic baud mode."""

    if isinstance(baud, int):
        return [baud]
    if baud == "max":
        return [baud_base if baud_base > 0 else 115200]

    limit = baud_base if baud_base > 0 else max(STANDARD_RATES)
    rates = [rate for rate in STANDARD_RATES if rate <= limit]
    if baud_base > 0 and baud_base not in rates:
        rates.append(baud_base)
    rates = sorted(set(rates))

    if baud == "sweep":
        return rates
    if baud == "autoscan-max":
        return list(reversed(rates))
    raise ValueError("unsupported baud mode: {}".format(baud))


def run_ping(serial_conn):
    """Run a quick loopback ping on an open serial connection."""

    serial_conn.timeout = 1.0
    serial_conn.reset_input_buffer()
    serial_conn.write(PING_PATTERN)
    serial_conn.flush()
    time.sleep(0.05)
    received = serial_conn.read(len(PING_PATTERN))
    return received == PING_PATTERN


def run_stress(serial_conn, count, size, timeout_factor=3.0):
    """Run loopback stress traffic on an open serial connection."""

    byte_time = (size * 10) / serial_conn.baudrate
    serial_conn.timeout = max(2.0, byte_time * timeout_factor)
    serial_conn.reset_input_buffer()
    serial_conn.reset_output_buffer()

    for _index in range(count):
        payload = os.urandom(size)
        serial_conn.write(payload)
        serial_conn.flush()
        received = serial_conn.read(size)
        if received != payload:
            return False
    return True


def open_serial_and_run(dev_node, baud_rate, run_fn):
    """Open a serial node at a baud rate and run a callback."""

    serial_conn = serial.Serial(dev_node, baud_rate, timeout=1.0)
    try:
        return run_fn(serial_conn)
    finally:
        serial_conn.close()
        time.sleep(0.1)


def run_loopback(target, baud, mode, stress_count=100, stress_size=1024):
    """Run quick or stress loopback tests for one target."""

    device = resolve_device(target)
    rates = get_rates_to_test(device.baud_base, baud)
    results = []

    for rate in rates:
        try:
            if mode == "quick":
                passed = open_serial_and_run(device.dev_node, rate, run_ping)
            elif mode == "stress":
                passed = open_serial_and_run(
                    device.dev_node,
                    rate,
                    lambda serial_conn: run_stress(
                        serial_conn, stress_count, stress_size
                    ),
                )
            else:
                raise ValueError("unsupported mode: {}".format(mode))
        except (OSError, serial.SerialException) as exc:
            passed = False
            message = str(exc)
        else:
            message = "PASSED" if passed else "FAILED"

        result = LoopbackResult(rate, passed, message)
        results.append(result)
        print(
            "{}: {} {} baud {}".format(
                "PASS" if passed else "FAIL",
                device.dev_node,
                rate,
                message,
            )
        )

        if baud == "autoscan-max" and passed:
            print("Max working baud: {}".format(rate))
            return results

    return results


def parse_args(argv=None):
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser(
        "list", help="Print Checkbox resources from RAW_UART_PORTS"
    )
    list_parser.add_argument(
        "config",
        help=(
            "Space-separated entries using the format "
            "{}".format(RAW_UART_CONFIG_FORMAT)
        ),
    )

    quick_parser = subparsers.add_parser(
        "quick", help="Run a raw UART loopback ping test"
    )
    quick_parser.add_argument("--target", required=True)
    quick_parser.add_argument("--baud", required=True, type=parse_baud)

    stress_parser = subparsers.add_parser(
        "stress", help="Run a raw UART loopback stress test"
    )
    stress_parser.add_argument("--target", required=True)
    stress_parser.add_argument("--baud", required=True, type=parse_baud)
    stress_parser.add_argument(
        "--count",
        required=True,
        type=lambda value: parse_positive_int(value, "COUNT"),
    )
    stress_parser.add_argument(
        "--size",
        required=True,
        type=lambda value: parse_positive_int(value, "SIZE"),
    )

    return parser, parser.parse_args(argv)


def main(argv=None):
    parser, args = parse_args(argv)
    if not args.command:
        parser.print_usage()
        raise SystemExit(1)

    try:
        if args.command == "list":
            print_raw_uart_resources(args.config)
            return
        if args.command == "quick":
            results = run_loopback(args.target, args.baud, "quick")
        elif args.command == "stress":
            results = run_loopback(
                args.target,
                args.baud,
                "stress",
                stress_count=args.count,
                stress_size=args.size,
            )
        else:
            parser.print_usage()
            raise SystemExit(1)
    except (RuntimeError, ValueError) as exc:
        print("Error: {}".format(exc))
        raise SystemExit(1)

    if not all(result.passed for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
