#!/usr/bin/env python3
import sys
import logging
import argparse
from enum import Enum
from pathlib import Path


def init_logger():
    """
    Set the logger to log DEBUG and INFO to stdout, and
    WARNING, ERROR, CRITICAL to stderr.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logger_format = "%(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    #stdout_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stderr_handler = logging.StreamHandler(sys.stderr)
    # stderr_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stdout_handler.setLevel(logging.DEBUG)
    stderr_handler.setLevel(logging.WARNING)

    # Add a filter to the stdout handler to limit log records to
    # INFO level and below
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(stdout_handler)

    return root_logger


class RegulatorEnum(Enum):
    VOLTAGE = "voltage"
    CURRENT = "current"


SYS_REGULATOR_PATH = "/sys/class/regulator"
VOLTAGE_REGULATOR_ATTRIBUTES = ["name", "microvolts"]


class RegulatorBase():

    def __init__(self, regulator_type):
        self.regulator_type = regulator_type
        self.raw_regulators = {}
        self.regulators = {}

    def collect_data(self, node):
        try:
            rg_type_node = node.joinpath("type")
            rg_type_text = rg_type_node.read_text().strip()
            rg_type = RegulatorEnum(rg_type_text)
            if rg_type == RegulatorEnum.VOLTAGE:
                possible_keys = VOLTAGE_REGULATOR_ATTRIBUTES
                rg_type = RegulatorEnum.VOLTAGE.value
            elif rg_type == RegulatorEnum.CURRENT:
                possible_keys = []

            logging.info("\ntype: %s", rg_type)
            data = {"type": rg_type}
            for key in possible_keys:
                child = node.joinpath(key)
                if child.exists():
                    value = child.read_text().strip()
                    data[key] = value
                    logging.info("%s: %s", key, value)
            return data
        except ValueError:
            logging.error("Unexpected regulator type: %s", rg_type_text)
        except FileNotFoundError:
            logging.error("%s regulator type does not exists", node.name)

    def dump_sysfs_regulator(self):
        for rg_dev in sorted(Path(SYS_REGULATOR_PATH).glob("regulator*")):
            self.raw_regulators[rg_dev.name] = self.collect_data(rg_dev)

    def filter_regulators_by_type(self):
        logging.info("\n# filtering %s regulator..", self.regulator_type)
        for dev in self.raw_regulators.values():
            if dev["type"] != self.regulator_type:
                logging.info("skip '%s' regulator", dev["name"])
                continue

            key = dev.pop("name")
            self.regulators[key] = dev

    def is_regulator_available(self, name):
        if name in self.regulators.keys():
            return True
        logging.error("%s regulator not found", name)
        return False

    def is_regulator_attr_available(self, regulator, attr):
        if attr in self.regulators[regulator].keys():
            return True
        logging.error("%s attribute not exists", attr)
        return False

    def get_regulator_attr(self, regulator, attr):
        return self.regulators[regulator][attr]


def convert_regulator_devices(type, data):
    devices = {}

    for part in data.split("|"):
        if RegulatorEnum(type) == RegulatorEnum.VOLTAGE:
            parts = part.split(":")
            if len(parts) != len(VOLTAGE_REGULATOR_ATTRIBUTES):
                logging.error("Unexpected regulator data: %s", part)
                continue
            dev = dict(zip(VOLTAGE_REGULATOR_ATTRIBUTES, parts))

        key = dev.pop("name")
        devices[key] = dev

    return devices


def summarize_test_results(details_logs):
    logging.info("\n# Details Test Results")
    for regulator, msgs in details_logs.items():
        log = "## '{}' regulator: ".format(regulator)
        log += "Failed" if msgs else "Passed"
        log += msgs
        logging.info(log)


def check_difference(exp_regulators, sysfs_regulators):
    test_results = {"result": False, "logs": {}}

    for regulator, data in exp_regulators.items():
        details = ""
        if not sysfs_regulators.is_regulator_available(regulator):
            details += "\n- regulator device not exists"
            test_results["logs"][regulator] = details
            test_results["result"] = True
            continue

        for attr, value in data.items():
            if not sysfs_regulators.is_regulator_attr_available(
                regulator, attr
            ):
                details += "\n- {} attribute not exits".format(attr)
                test_results["result"] = True
                continue

            actual_attr = sysfs_regulators.get_regulator_attr(regulator, attr)
            if value != actual_attr:
                details += (
                    "\n- mismatch value for {}. expected: {}, actual: {}"
                ).format(
                    attr, value, actual_attr
                )
                test_results["result"] = True
            test_results["logs"][regulator] = details

    return test_results


def compare_regulators(args):
    type = args.type
    exp_regulator_devs = convert_regulator_devices(type, args.devices)
    if not exp_regulator_devs:
        raise SystemExit("Invalid input argument for devices")

    regulator = RegulatorBase(type)
    regulator.dump_sysfs_regulator()
    regulator.filter_regulators_by_type()

    results = check_difference(
        exp_regulator_devs, regulator
    )
    summarize_test_results(results["logs"])
    if results["result"]:
        raise SystemExit(
            "\nFailed: the expected {} regulatorss does not match".format(
                type
            )
        )
    else:
        logging.info(
            "\nPassed: the expected %s regulatorss are all available", type
        )


def register_arguments():
    parser = argparse.ArgumentParser(
        description="Voltage Regulator detection Tests",
    )
    parser.add_argument(
        "devices",
        type=str,
        help=(
            "provides expected regulator information with following format.\n"
            "format: name:microvolts|..."
            "e.g. LO1:1800000|LO2:3300000"
        ),
    )
    parser.add_argument(
        "--type",
        "-t",
        choices=[RegulatorEnum.VOLTAGE.value, RegulatorEnum.CURRENT.value],
        help="the regulator type"
    )

    args = parser.parse_args()
    return args


def main():
    init_logger()
    args = register_arguments()
    compare_regulators(args)


if __name__ == "__main__":
    main()
