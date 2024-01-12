#!/usr/bin/env python3
import sys
import time
import logging
import shlex
import subprocess
import argparse
from pathlib import Path

SYS_THERMAL_PATH = "/sys/class/thermal"


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


class ThermalMonitor():

    def __init__(self, name):
        self._name = name
        self.root_node = Path(SYS_THERMAL_PATH).joinpath(self._name)
        self.type_node = self.root_node.joinpath("type")
        self.temp_node = self.root_node.joinpath("temp")
        self.mode_node = self.root_node.joinpath("mode")
        self.initial_temp = None

    def _read_node(self, node):
        if node.exists():
            return node.read_text().strip("\n")
        else:
            raise FileNotFoundError("{} file not exists".format(str(node)))

    @property
    def name(self):
        return self._name

    @property
    def type(self):
        return self._read_node(self.type_node)

    @property
    def temperature(self):
        temp = self._read_node(self.temp_node)
        if not temp.isnumeric():
            raise ValueError("temperate value is not a number!")
        return temp

    @property
    def mode(self):
        return self._read_node(self.mode_node)


def check_temperature(current, initial):
    logging.info("Initial value: %s, current value: %s", initial, current)
    return (int(current) != 0 and current != initial)


def thermal_monitor_test(args):
    logging.info(
        "# Monitor the temperature of %s thermal around %s seconds",
        args.name, args.duration)

    if args.extra_commands == "stress-ng":
        cmd = ("stress-ng --cpu 0 --io 4 --vm 2 "
               "--vm-bytes 128M --timeout {}s").format(args.duration)
    else:
        cmd = args.extra_commands

    thermal_op = ThermalMonitor(args.name)
    if thermal_op.mode == "disabled":
        raise SystemExit("Error: The {}-{} thermal is disabled".format(
                                            thermal_op.name, thermal_op.type))
    initial_value = thermal_op.temperature

    result = False
    proc = None
    try:
        proc = subprocess.Popen(shlex.split(cmd))
    except Exception:
        # Bypass any error while issue command through Popen
        # Due to the command here is trying to increase system loading
        pass

    for _ in range(args.duration):
        cur_temp = thermal_op.temperature
        result = check_temperature(cur_temp, initial_value)
        if result:
            logging.info(
                "# The temperature of %s thermal has been altered",
                args.name)
            break
        time.sleep(1)
    if proc and proc.poll() is None:
        # kill the subprocess if it is still alive
        proc.kill()

    if result is False:
        logging.error(
            "# The temperature of the %s thermal remains consistently at %s",
            args.name, initial_value)
        raise SystemExit(1)


def dump_thermal_zones(args):

    for thermal in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        node = ThermalMonitor(thermal.name)
        print("name: {}\nmode: {}\ntype: {}\n".format(
                    node.name, node.mode, node.type))


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Thermal temperature Tests')
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Turn on debug level output for extra info during test run."
    )

    sub_parsers = parser.add_subparsers(
        help="Thermal test type", dest="test_type", required=True)

    monitor_parser = sub_parsers.add_parser("monitor")
    monitor_parser.add_argument(
        "-n", "--name",
        required=True,
        type=str
    )
    monitor_parser.add_argument(
        "-d", "--duration",
        type=int,
        default=60,
        help="the time period to monitor thermal temperature"
    )
    monitor_parser.add_argument(
        "--extra-commands",
        type=str,
        default="stress-ng",
        help=("the command is for increase the system loading, "
              "will apply stress-ng by default")
    )
    monitor_parser.set_defaults(test_type=thermal_monitor_test)

    dump_parser = sub_parsers.add_parser("dump")
    dump_parser.set_defaults(test_type=dump_thermal_zones)

    args = parser.parse_args()
    return args


def main():
    args = register_arguments()
    logger = init_logger()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    args.test_type(args)


if __name__ == "__main__":
    main()
