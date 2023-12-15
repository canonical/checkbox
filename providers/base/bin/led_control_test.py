import sys
import re
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


class SysFsLEDController():

    SysFsLEDPath = "/sys/class/leds"

    def __init__(self, name, on_value="0", off_value="0"):
        self.led_name = name
        self.led_node = Path(self.SysFsLEDPath).joinpath(name)
        self.brightness_node = self.led_node / "brightness"
        self.max_brightness_node = self.led_node / "max_brightness"
        self.trigger_node = self.led_node / "trigger"
        self.initial_state = {"trigger": None, "brightness": None}
        self._on_value = on_value
        self._off_value = off_value

    def __enter__(self):
        logging.debug("setup action for LED testing")

        if int(self._on_value) > int(self.max_brightness):
            raise ValueError("brightness value greater than max brightness")
        if self._on_value == "0":
            self._on_value = self.max_brightness

        # Get the initial value of trigger and brightness
        self._get_initial_state()
        # Set the trigger type to none
        self.trigger = "none"
        self.off()

        return self

    def __exit__(self, type, value, traceback):
        logging.debug("teardown action for LED testing")
        initial_state = self.initial_state
        self.brightness = initial_state["brightness"]
        self.trigger = initial_state["trigger"]

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
        logging.debug("set trigger action to {} for {} LED".format(
            value, self.led_name
        ))
        # The read value from trigger node is all supported trigger type
        # So skip the check
        self._write_node(self.trigger_node, value, False)

    def _get_initial_state(self):
        match = re.search(r"\[([\w-]+)\]", self.trigger)
        if match:
            self.initial_state["trigger"] = match.groups()[0]

        self.initial_state["brightness"] = self.brightness

    def on(self):
        logging.debug("turn on {} LED".format(self.led_name))
        self.brightness = self._on_value

    def off(self):
        logging.debug("turn off {} LED".format(self.led_name))
        self.brightness = self._off_value

    def blinking(self, duration=10, interval=1):
        logging.debug("set {} LED blinking".format(self.led_name))
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() <= duration:
            self.on()
            time.sleep(interval)
            self.off()
            time.sleep(interval)


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='LED Tests')
    parser.add_argument(
        "-n", "--name",
        required=True,
        type=str
    )
    parser.add_argument(
        "-d", "--duration",
        type=int,
        default=5
    )
    parser.add_argument(
        "-i", "--interval",
        type=int,
        default=0.5
    )
    parser.add_argument(
        "--on-value",
        type=int,
        default="0"
    )
    parser.add_argument(
        "--off-value",
        type=int,
        default="0"
    )

    args = parser.parse_args()
    return args


def main():
    args = register_arguments()
    logger = init_logger()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    logging.info("# Start LED testing")
    logging.info(("# Set the %s LED blinking around %d seconds"
                  "with %d seconds blink interval"),
                 args.led_name, args.duration, args.interval)

    with SysFsLEDController(args.led_name, str(args.on_value),
                            str(args.off_value)) as led_controller:
        led_controller.blinking(args.duration, args.interval)


if __name__ == "__main__":
    main()
