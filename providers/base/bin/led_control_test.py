#!/usr/bin/env python3

import sys
import re
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime


class SysFsLEDController:

    SysFsLEDPath = "/sys/class/leds"

    def __init__(
        self, name, on_value="0", off_value="0", is_multi_color_led=False
    ):
        self.led_name = name
        self._on_value = on_value
        self._off_value = off_value
        self.blinking_test_func = self.blinking
        self.is_multi_color_led = is_multi_color_led

        self.led_node = Path(self.SysFsLEDPath).joinpath(name)
        self.brightness_node = self.led_node.joinpath("brightness")
        self.max_brightness_node = self.led_node.joinpath("max_brightness")
        self.trigger_node = self.led_node.joinpath("trigger")
        self.initial_state = {"trigger": None, "brightness": None}

        if self.is_multi_color_led:
            self.blinking_test_func = self.multi_color_blinking
            self.multi_index_node = self.led_node.joinpath("multi_index")
            self.multi_intensity_node = self.led_node.joinpath(
                "multi_intensity"
            )
            self.initial_state["multi_intensity"] = None

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, type, value, traceback):
        self.teardown()

    def setup(self):
        logging.debug("setup action for LED testing")

        if int(self._on_value) > int(self.max_brightness):
            raise ValueError("brightness value greater than max brightness")
        if self._on_value == "0":
            self._on_value = self.max_brightness

        # Get the initial value of trigger, brightness and multi_intensity
        self._get_initial_state()
        # Set the trigger type to none
        self.trigger = "none"
        self.off()

        if self.is_multi_color_led:
            self.color_mapping = self.multi_index.split()

    def teardown(self):
        logging.debug("teardown action for LED testing")
        initial_state = self.initial_state
        self.brightness = initial_state["brightness"]
        self.trigger = initial_state["trigger"]
        if self.is_multi_color_led:
            self.multi_intensity = initial_state["multi_intensity"]

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
                "Unable to change the value of {} file".format(str(node))
            )

    @property
    def brightness(self):
        return self._read_node(self.brightness_node)

    @brightness.setter
    def brightness(self, value):
        logging.debug("set brightness to %s for %s LED", value, self.led_name)
        self._write_node(self.brightness_node, value)

    @property
    def max_brightness(self):
        return self._read_node(self.max_brightness_node)

    @property
    def trigger(self):
        return self._read_node(self.trigger_node)

    @trigger.setter
    def trigger(self, value):
        logging.debug(
            "set trigger action to {} for {} LED".format(value, self.led_name)
        )
        # The read value from trigger node is all supported trigger type
        # So skip the check
        self._write_node(self.trigger_node, value, False)

    def _get_initial_state(self):
        match = re.search(r"\[([\w-]+)\]", self.trigger)
        if match:
            self.initial_state["trigger"] = match.groups()[0]

        self.initial_state["brightness"] = self.brightness
        if self.is_multi_color_led:
            self.initial_state["multi_intensity"] = self.multi_intensity

    @property
    def multi_intensity(self):
        return self._read_node(self.multi_intensity_node)

    @multi_intensity.setter
    def multi_intensity(self, value):
        logging.debug(
            "set color intensities to %s for %s LED", value, self.led_name
        )
        self._write_node(self.multi_intensity_node, value)

    @property
    def multi_index(self):
        return self._read_node(self.multi_index_node)

    def form_multi_intensity_value(self, color):
        intensities = []
        for c in self.color_mapping:
            value = self.max_brightness if color == c else "0"
            intensities.append(value)

        return " ".join(intensities)

    def on(self):
        logging.debug("turn on {} LED".format(self.led_name))
        self.brightness = self._on_value

    def off(self):
        logging.debug("turn off {} LED".format(self.led_name))
        self.brightness = self._off_value

    def blinking(self, duration, interval):
        logging.info(
            "## Set the %s LED to blink for %d seconds",
            self.led_name,
            duration,
        )
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() <= duration:
            self.on()
            time.sleep(interval)
            self.off()
            time.sleep(interval)
        logging.info(
            "## Is the %s LED blinking around %s seconds?",
            self.led_name,
            duration,
        )

    def multi_color_blinking(self, duration, interval):
        for color in self.color_mapping:
            logging.info(
                "\n## Adjust the multi color LED %s to %s color",
                self.led_name,
                color,
            )
            intensities = self.form_multi_intensity_value(color)
            self.multi_intensity = intensities
            self.blinking(duration, interval)
            logging.info(
                "## Is the %s LED blinking with %s color?",
                self.led_name,
                color,
            )

    def blinking_test(self, duration=10, interval=1):
        self.blinking_test_func(duration, interval)


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="LED Tests",
    )
    parser.add_argument("-n", "--name", required=True, type=str)
    parser.add_argument("-d", "--duration", type=int, default=5)
    parser.add_argument("-i", "--interval", type=int, default=0.5)
    parser.add_argument("--on-value", type=int, default="0")
    parser.add_argument("--off-value", type=int, default="0")
    parser.add_argument("--color-type", type=str, choices=["single", "multi"])
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Turn on debug level output for extra info during test run.",
    )

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

    logging.info("# Start LED testing")
    with SysFsLEDController(
        args.name,
        str(args.on_value),
        str(args.off_value),
        is_multi_color_led=(args.color_type == "multi"),
    ) as led_controller:
        led_controller.blinking_test(args.duration, args.interval)
