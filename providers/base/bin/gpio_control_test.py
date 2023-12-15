import sys
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime


def init_logger():
    """
    Set the logger to log DEBUG and INFO to stdout, and
    WARNING, ERROR, CRITICAL to stderr.
    """
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

    return root_logger


class GPIOController():

    GPIORootPath = "/sys/class/gpio"
    GPIOExportPath = "{}/export".format(GPIORootPath)
    GPIOUnexportPath = "{}/unexport".format(GPIORootPath)

    def __init__(self, gpio_chip, gpio_pin, direction, need_export):
        self.gpio_pin = gpio_pin
        self.gpio_chip_node = Path(self.GPIORootPath).joinpath(
                                    "gpiochip{}".format(gpio_chip))
        self.gpio_node = None
        self.value_node = None
        self.direction_node = None
        self.gpiochip_info = {"base": None, "ngpio": None}
        self._direction = direction
        self._need_export = need_export
        self.initial_state = {"value": None, "direction": None}

    def __enter__(self):
        logging.debug("setup action for GPIO testing")
        for key in ["base", "ngpio"]:
            with self.gpio_chip_node.joinpath(key) as gpio_node:
                if gpio_node.exists():
                    self.gpiochip_info[key] = gpio_node.read_text().strip("\n")
                else:
                    raise FileNotFoundError(
                        "{} file not exists".format(str(gpio_node)))

        if int(self.gpio_pin) > int(self.gpiochip_info["ngpio"]):
            raise IndexError(
                "GPIO pin '{}' greater than ngpio value '{}'".format(
                    self.gpio_pin, self.gpiochip_info["ngpio"]
                )
            )

        self.gpio_pin = (
            int(self.gpiochip_info["base"]) + int(self.gpio_pin) - 1)
        self.gpio_node = Path(self.GPIORootPath).joinpath(
                                    "gpio{}".format(self.gpio_pin))

        # Export GPIO node if needed
        if self.initial_state["need_export"]:
            self._export(str(self.gpio_pin))
            time.sleep(1)

        if not self.gpio_node.exists():
            raise FileNotFoundError(
                        "{} file not exists".format(str(self.gpio_node)))

        # Store the initial state for GPIO
        self.initial_state["value"] = self.value
        self.initial_state["direction"] = self.direction

        self.direction = self._direction

        return self

    def __exit__(self, type, value, traceback):
        logging.debug("teardown action for LED testing")
        self.value = self.initial_state["value"]
        self.direction = self.initial_state["direction"]
        if self._need_export:
            self._unexport(str(self.gpio_pin))

    def _node_exists(self, node):
        if node.exists() is False:
            raise FileNotFoundError("{} file not exists".format(str(node)))

    def _read_node(self, node):
        self._node_exists(node)
        return node.read_text().strip("\n")

    def _write_node(self, node, value, check=True):

        self._node_exists(node)
        node.write_text(value)
        if check and self._read_node(node) != value:
            raise ValueError(
                "Unable to change the value of {} file".format(str(node)))

    def _export(self, pin):
        logging.debug("export %s node", self.gpio_node.name)
        with Path(self.GPIOExportPath) as gpio_node:
            gpio_node.write_text(pin)

    def _unexport(self, pin):
        logging.debug("unexport %s node", self.gpio_node.name)
        with Path(self.GPIOUnexportPath) as gpio_node:
            gpio_node.write_text(pin)

    @property
    def direction(self):
        with self.gpio_node.joinpath("direction") as gpio_node:
            return self._read_node(gpio_node)

    @direction.setter
    def direction(self, value):

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
    def value(self, value):
        with self.gpio_node.joinpath("value") as gpio_node:
            logging.debug("set value to {} for {}".format(
                value, gpio_node.name
            ))
            self._write_node(gpio_node, value)

    def on(self):
        logging.debug("turn on GPIO{} LED".format(self.gpio_pin))
        self.value = 1

    def off(self):
        logging.debug("turn off GPIO{} LED".format(self.gpio_pin))
        self.value = 0

    def blinking(self, duration=10, interval=1):
        logging.debug("set GPIO{} LED blinking".format(self.gpio_pin))
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
                        args.led_name, args.duration, args.interval))
        led_controller.blinking(args.duration, args.interval)


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='GPIO Control Tests')
    sub_parsers = parser.add_subparsers(help="GPIO test type")
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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Turn on debug level output for extra info during test run.",
    )
    gpio_led_parser.set_defaults(test_func=blinking_test)

    args = parser.parse_args()
    return args


def main():
    args = register_arguments()
    logger = init_logger()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    try:
        args.test_func(args)
    except Exception as err:
        logging.error(err)


if __name__ == "__main__":
    main()
