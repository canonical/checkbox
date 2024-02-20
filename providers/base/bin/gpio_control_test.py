#!/usr/bin/env python3
import re
import sys
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime


class GPIOController:

    GPIORootPath = "/sys/class/gpio"
    GPIOExportPath = "{}/export".format(GPIORootPath)
    GPIOUnexportPath = "{}/unexport".format(GPIORootPath)

    def __init__(self, gpiochip: str, gpiopin: str,
                 direction: int, need_export: bool):
        if gpiochip.isnumeric() is False or gpiopin.isnumeric() is False:
            raise ValueError("Invalid GPIO chip or GPIO pin")

        self._gpio_root_node = Path(self.GPIORootPath)
        self._gpiochip_mapping = self.get_gpiochip_mapping()

        if gpiochip not in self._gpiochip_mapping.keys():
            raise KeyError("GPIO chip number {} is incorrect".format(gpiochip))

        self.gpio_chip_node = self._gpio_root_node.joinpath(
                                    "gpiochip{}".format(
                                        self._gpiochip_mapping.get(gpiochip)))
        self.gpio_node = self.value_node = None
        self.gpiochip_info = {"base": None, "ngpio": None, "offset": gpiopin}
        self._direction = direction
        self._need_export = need_export
        self.initial_state = {
            "value": None, "direction": None, "number": None
        }

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, type, value, traceback):
        self.teardown()

    def check_gpio_offset(self, pin: str, ngpio: str):
        if int(pin) == 0:
            raise ValueError("")

        if int(pin) > int(ngpio):
            raise IndexError(
                "GPIO pin '{}' greater than ngpio value '{}'".format(
                    pin, ngpio))

    def get_gpiochip_mapping(self):
        mapping = {}
        nodes = sorted(
                    self._gpio_root_node.glob("gpiochip*/device/gpiochip*"))
        for node in nodes:
            match = re.search(
                r"/sys/class/gpio/gpiochip([0-9]+)/device/gpiochip([0-9]+)",
                str(node))
            if match:
                mapping.update({match.groups()[1]: match.groups()[0]})
        return mapping

    def setup(self):
        logging.debug("setup action for GPIO testing")
        for key in ["base", "ngpio"]:
            with self.gpio_chip_node.joinpath(key) as gpio_node:
                if self._node_exists(gpio_node) is False:
                    raise FileNotFoundError(
                        "{} file not exists".format(str(gpio_node)))
                self.gpiochip_info[key] = self._read_node(gpio_node)

        self.check_gpio_offset(
            self.gpiochip_info["offset"], self.gpiochip_info["ngpio"]
        )

        self.initial_state["number"] = str((
            int(self.gpiochip_info["base"]) +
            int(self.gpiochip_info["offset"]) - 1
        ))
        self.gpio_node = self._gpio_root_node.joinpath(
                "gpio{}".format(self.initial_state["number"]))

        # Export GPIO node if needed
        if self._need_export:
            self._export(self.initial_state["number"])
            time.sleep(1)

        if self._node_exists(self.gpio_node) is False:
            raise FileNotFoundError(
                        "{} file not exists".format(str(self.gpio_node)))

        # Store the initial state for GPIO
        self.initial_state["value"] = self.value
        self.initial_state["direction"] = self.direction

        # Configure the GPIO direction
        self.direction = self._direction

    def teardown(self):
        logging.debug("teardown action for LED testing")
        self.value = self.initial_state["value"]
        self.direction = self.initial_state["direction"]
        if self._need_export:
            self._unexport(self.initial_state["number"])

    def _node_exists(self, node: Path):
        if node.exists() is False:
            raise FileNotFoundError("{} file not exists".format(str(node)))

    def _read_node(self, node: Path):
        self._node_exists(node)
        return node.read_text().strip("\n")

    def _write_node(self, node: Path, value: str, check=True):

        self._node_exists(node)
        node.write_text(value)
        if check and self._read_node(node) != value:
            raise ValueError(
                "Unable to change the value of {} file".format(str(node)))

    def _export(self, gpio_number: str):
        logging.debug("export GPIO node %s", gpio_number)
        with Path(self.GPIOExportPath) as gpio_node:
            self._write_node(gpio_node, gpio_number, False)

    def _unexport(self, gpio_number: str):
        logging.debug("unexport GPIO node %s", gpio_number)
        with Path(self.GPIOUnexportPath) as gpio_node:
            self._write_node(gpio_node, gpio_number, False)

    @property
    def direction(self):
        with self.gpio_node.joinpath("direction") as gpio_node:
            return self._read_node(gpio_node)

    @direction.setter
    def direction(self, value: str):
        if value not in ["in", "out"]:
            raise ValueError(
                "The {} is not allowed for direction".format(value))

        with self.gpio_node.joinpath("direction") as gpio_node:
            logging.debug("set direction to {} for {}".format(
                value, gpio_node.name
            ))
            self._write_node(gpio_node, value)

    @property
    def value(self):
        with self.gpio_node.joinpath("value") as gpio_node:
            return self._read_node(gpio_node)

    @value.setter
    def value(self, value: str):
        if value not in ["1", "0"]:
            raise ValueError(
                "The {} is not allowed for value".format(value))

        with self.gpio_node.joinpath("value") as gpio_node:
            logging.debug("set value to {} for {}".format(
                value, gpio_node.name
            ))
            self._write_node(gpio_node, value)

    def on(self):
        logging.debug("turn on GPIO")
        self.value = "1"

    def off(self):
        logging.debug("turn off GPIO")
        self.value = "0"

    def blinking(self, duration=10, interval=1):
        logging.debug(
            "set GPIO{} LED blinking".format(self.initial_state["number"]))
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() <= duration:
            self.on()
            time.sleep(interval)
            self.off()
            time.sleep(interval)


def blinking_test(args):

    with GPIOController(args.gpio_chip, args.gpio_pin,
                        "out", args.need_export) as led_controller:
        logging.info(("# Set the {} LED blinking around {} seconds "
                     "with {} seconds blink interval").format(
                        args.name, args.duration, args.interval))
        led_controller.blinking(args.duration, args.interval)


def dump_gpiochip(args):
    gpio_debug_path = "/sys/kernel/debug/gpio"

    gpio_debug = Path(gpio_debug_path)
    if gpio_debug.exists():
        print(gpio_debug.read_text())
    else:
        raise FileNotFoundError("{} file not exists".format(str(gpio_debug)))


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='GPIO Control Tests')
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Turn on debug level output for extra info during test run.",
    )

    sub_parsers = parser.add_subparsers(help="GPIO test type",
                                        dest="test_func")
    sub_parsers.required = True

    gpio_led_parser = sub_parsers.add_parser("led")
    gpio_led_parser.add_argument(
        "-n", "--name",
        required=True,
        type=str
    )
    gpio_led_parser.add_argument(
        "-d", "--duration",
        type=int,
        default=5
    )
    gpio_led_parser.add_argument(
        "-i", "--interval",
        type=int,
        default=0.5
    )
    gpio_led_parser.add_argument(
        "--gpio-chip",
        type=str,
        required=True
    )
    gpio_led_parser.add_argument(
        "--gpio-pin",
        type=str,
        required=True
    )
    gpio_led_parser.add_argument(
        "--need-export",
        action="store_true",
        default=False
    )
    gpio_led_parser.set_defaults(test_func=blinking_test)

    gpio_dump_parser = sub_parsers.add_parser("dump")
    gpio_dump_parser.set_defaults(test_func=dump_gpiochip)

    args = parser.parse_args()
    return args


if __name__ == "__main__":

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logger_format = "%(asctime)s %(levelname)-8s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stdout_handler.setLevel(logging.DEBUG)
    stderr_handler.setLevel(logging.WARNING)

    # Add a filter to the stdout handler to limit log records to
    # INFO level and below
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(stdout_handler)

    args = register_arguments()

    if args.debug:
        root_logger.setLevel(logging.DEBUG)

    try:
        args.test_func(args)
    except Exception as err:
        logging.error(err)
