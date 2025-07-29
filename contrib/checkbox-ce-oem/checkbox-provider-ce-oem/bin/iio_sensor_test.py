#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Stanley Huang <stanley.huang@canonical.com>
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
import re
import argparse
import logging
import sys
from pathlib import Path


IIO_PATH = "/sys/bus/iio/devices/"

NODE_MAPPING = {
    "pressure": [
        "in_pressure_input",
        "in_pressure_oversampling_ratio",
        "in_pressure_sampling_frequency",
    ],
    "accelerometer": [
        "in_accel_sampling_frequency",
        "in_accel_scale",
        "in_accel_x_calibbias",
        "in_accel_x_raw",
        "in_accel_y_calibbias",
        "in_accel_y_raw",
        "in_accel_z_calibbias",
        "in_accel_z_raw",
    ],
    "humidity": [
        "in_humidityrelative_integration_time",
        "in_humidityrelative_scale",
        "in_humidityrelative_raw",
    ],
    "adc": [
        "in_voltage",
        "in_voltage_scale",
    ],
}


def _get_iio_device_mapping():
    """
    Get a mapping of IIO device names to their full paths.

    Returns:
        dict: A dictionary where keys are sensor names (str) and values
              are their full IIO device paths (str).
    """
    iio_devices = {}
    if Path(IIO_PATH).exists():
        for device_path in Path(IIO_PATH).glob("iio:device*"):
            name_node = device_path.joinpath("name")
            if name_node.exists():
                name = name_node.read_text().strip()
                iio_devices[name] = str(device_path)
        return iio_devices
    else:
        return None


def _check_device(name):
    """
    Initial a Path object for the industrial I/O sensor

    Args:
        name (str):

    Raises:
        FileNotFoundError: the sysfs of sensor not exists

    Returns:
        iio_node: The node of the industrial I/O sensor. (Path object)
    """
    iio_devices = _get_iio_device_mapping()
    if iio_devices:
        if name in iio_devices.keys():
            logging.info("Found IIO device %s.", name)
            return Path(iio_devices[name])
    raise FileNotFoundError("IIO device {} not exists".format(name))


def _check_node(path):
    """
    Initial a Path object for the industrial I/O sensor

    Args:
        path (str): the full path of the industrial I/O sensor

    Raises:
        FileNotFoundError: the sysfs of sensor not exists

    Returns:
        iio_node: The node of the industrial I/O sensor. (Path object)
    """
    iio_node = Path(path)
    if not iio_node.exists():
        raise FileNotFoundError("{} node not exists".format(iio_node))

    return iio_node


def _check_reading(values):
    """
    Check the format of sensor reading

    Args:
        values (list): a list of sensor reading

    Returns:
        bool: True if all reading match expected format
    """
    result = True
    reading_pattern = r"^[+-]?\d+(\.[0-9]+)?$"
    for value in values:
        if re.search(reading_pattern, value) is None:
            result = False

    return result


def _update_adc_nodes_mapping(nodes_mapping, input_num):
    """
    Updates the 'adc' key in the nodes_mapping dictionary
    to include in_voltageX_raw and in_voltageX_scale nodes
    up to input_num.

    Args:
        nodes_mapping (dict): The original dictionary of node mappings.
        input_num (int): The number of voltage input nodes to generate
                         (0 to input_num-1).

    Returns:
        dict: The updated nodes_mapping dictionary.
    """
    new_adc_nodes = []
    for i in range(input_num):
        new_adc_nodes.append("in_voltage{}_raw".format(i))
    new_adc_nodes.append("in_voltage_scale")
    nodes_mapping["adc"] = new_adc_nodes
    return nodes_mapping


def check_sensor(name, type, nodes):
    """
    Validate the sysfs of industrial I/O accelerometer sensor

    Args:
        name (str): The expected name of sensor
        type (str): The expected type of sensor

    Raises:
        ValueError: The reading of sensor is not expected format
    """
    readings = []
    iio_node = _check_device(name)

    for sub_node in nodes[type]:
        tmp_node = iio_node.joinpath(sub_node)
        _check_node(tmp_node)
        value = tmp_node.read_text().strip("\n")
        logging.info("The value of %s node is %s", tmp_node, value)
        readings.append(value)

    if readings and _check_reading(readings):
        logging.info("The %s sensor test passed", type)
    else:
        raise ValueError("ERROR: The {} value is not valid.".format(type))


def validate_iio_sensor(args):
    """
    Check sensor and validate the format of reading

    Args:
        args (Namespace): the arguments includes type and index of sensor
    """
    if args.type == "adc":
        nodes = _update_adc_nodes_mapping(NODE_MAPPING, args.input_num)
    else:
        nodes = NODE_MAPPING

    logging.info("# Perform %s sensor test - name %s", args.type, args.name)
    check_sensor(args.name, args.type, nodes)


def dump_sensor_resource(args):
    """
    Print out the sensor index and sensor type

    Args:
        args (Namespace): The arguments includes type and index of sensor
    """
    output = ""
    resource_text = "name: {}\ntype: {}\ninput_num: {}\n\n"
    #  Fallback logic for existing checkbox config
    if "|" in args.mapping:
        mapping = args.mapping.split("|")
    else:
        mapping = args.mapping.split()
    for sensor in mapping:
        parts = sensor.split(":")
        if len(parts) == 2:
            name, sensor_type = parts
            output += resource_text.format(name, sensor_type, None)
        else:
            name, sensor_type, input_num = parts
            output += resource_text.format(name, sensor_type, input_num)
    print(output)


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Industrial IO sensor tests",
    )

    sub_parsers = parser.add_subparsers(dest="test_func")
    sub_parsers.required = True

    iio_test_parser = sub_parsers.add_parser("test")
    iio_test_parser.add_argument(
        "-t",
        "--type",
        required=True,
        choices=["pressure", "accelerometer", "humidityrelative", "adc"],
        type=str,
    )
    iio_test_parser.add_argument(
        "-n",
        "--name",
        required=True,
        type=str,
        help="The name of expected IIO device.",
    )
    iio_test_parser.add_argument(
        "-i",
        "--input-num",
        type=int,
        help="The expected total number of input pin for the ADC.",
    )
    iio_test_parser.set_defaults(test_func=validate_iio_sensor)

    iio_arg_parser = sub_parsers.add_parser("sensor-resource")
    iio_arg_parser.add_argument(
        "mapping",
        help=(
            "Usage of parameter: IIO_SENSORS="
            "{name}:{sensor_type}|"
            "{name}:{sensor_type_adc}:{expected_input_number}"
        ),
    )

    iio_arg_parser.set_defaults(test_func=dump_sensor_resource)

    args = parser.parse_args()

    return args


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(message)s", stream=sys.stdout
    )

    args = register_arguments()

    args.test_func(args)
