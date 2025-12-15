#!/usr/bin/env python3
import sys
import logging
import argparse
import copy

from collections import Counter
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

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(logger_format))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(logger_format))

    stdout_handler.setLevel(logging.DEBUG)
    stderr_handler.setLevel(logging.WARNING)

    # Add a filter to the stdout handler to limit log records to
    # INFO level and below
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(stdout_handler)

    return root_logger


SYS_REGULATOR_PATH = "/sys/class/regulator"


class RegulatorTypeEnum(Enum):
    VOLTAGE = "voltage"
    CURRENT = "current"

    def __str__(self):
        return self.value


class RegulatorAttribute:

    def __init__(self):
        self.name = "name"
        self.type = "type"


def read_node_text(node):
    try:
        value = node.read_text().strip()
    except FileNotFoundError:
        logging.error("'%s' does not exists", str(node))
        return None
    except OSError as err:
        logging.error("Unexpected error while accessing %s. %s", str(node), err)
        return None

    return value


class RegulatorBase:

    def __init__(self, regulator_type):
        self.regulator_type = regulator_type
        self.raw_regulators = {}
        self.regulators = {}
        self.duplicated_regulators = []

    def collect_data(self, node):
        regulator_attr = RegulatorAttribute()
        rg_type_text = read_node_text(node.joinpath(regulator_attr.type))
        if not rg_type_text:
            return None

        try:
            RegulatorTypeEnum(rg_type_text)
            data = {}
            for key in regulator_attr.__dict__:
                value = read_node_text(node.joinpath(key))
                if value is not None:
                    data[key] = value
                    logging.info("%s: %s", key, value)

            return data
        except ValueError:
            logging.error(
                "Unexpected type for '%s' regulator: %s",
                node.name,
                rg_type_text,
            )

    def dump_sysfs_regulator(self):
        for rg_dev in sorted(Path(SYS_REGULATOR_PATH).glob("regulator*")):
            logging.info("- %s", rg_dev.name)
            data = self.collect_data(rg_dev)
            if data:
                self.raw_regulators[rg_dev.name] = data

    def filter_regulators_by_type(self):
        logging.info("\n# filtering %s regulator ..", self.regulator_type)
        for dev in self.raw_regulators.values():
            if RegulatorTypeEnum(dev["type"]) != self.regulator_type:
                logging.info("skip '%s' regulator", dev["name"])
                continue

            rg = copy.deepcopy(dev)
            key = rg.pop("name")
            self.regulators[key] = rg

    def has_duplicated_regulators(self):
        logging.info("\n# checking duplicated regulators ..")
        name_counts = Counter([attrs["name"] for attrs in self.raw_regulators.values()])
        result = {
            node: attrs["name"]
            for node, attrs in self.raw_regulators.items()
            if name_counts[attrs["name"]] > 1
        }

        if result:
            logging.error("# Some regulators has the same name")
            for node, name in result.items():
                logging.error("- node: %s, name: %s", node, name)
            return True

        return False

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


def summarize_test_results(details_logs):
    logging.info("\n# Details Test Results")
    for regulator, msgs in details_logs.items():
        log = "## '{}' regulator: ".format(regulator)
        log += "Failed" if msgs else "Passed"
        log += msgs
        logging.info(log)


def check_difference(exp_regulators, sysfs_regulators):
    logging.info("\n# comparing regulators ..")
    test_results = {"result": False, "logs": {}}

    for regulator in exp_regulators:
        details = ""
        if not sysfs_regulators.is_regulator_available(regulator):
            details += "\n- regulator device not exists"
            test_results["result"] = True
        test_results["logs"][regulator] = details

    return test_results


def compare_regulators(args):
    type = args.type

    exp_regulator_devs = args.devices.split("|")
    if not exp_regulator_devs:
        raise SystemExit("Invalid input argument for devices")

    regulator = RegulatorBase(type)
    regulator.dump_sysfs_regulator()
    regulator.filter_regulators_by_type()
    duplicated = regulator.has_duplicated_regulators()

    results = check_difference(exp_regulator_devs, regulator)
    summarize_test_results(results["logs"])
    if results["result"]:
        logging.error("\nFailed: the expected %s regulators does not match", type)
    else:
        logging.info("\nPassed: the expected %s regulators are all available", type)

    if duplicated or results["result"]:
        raise SystemExit(1)


def register_arguments():
    parser = argparse.ArgumentParser(
        description="Voltage Regulator detection Tests",
    )
    parser.add_argument(
        "devices",
        type=str,
        help=(
            "provides expected regulator information with following format.\n"
            "format: name|...\n"
            "  e.g. LO1|LO2"
        ),
    )
    parser.add_argument(
        "-t",
        "--type",
        type=RegulatorTypeEnum,
        choices=list(RegulatorTypeEnum),
        help="the regulator type",
    )

    args = parser.parse_args()
    return args


def main():
    init_logger()
    args = register_arguments()
    compare_regulators(args)


if __name__ == "__main__":
    main()
