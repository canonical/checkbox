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
from pathlib import Path


IIO_PATH = "/sys/bus/iio/devices/iio:device"

pressure_nodes = [
    "in_pressure_input",
    "in_pressure_oversampling_ratio",
    "in_pressure_sampling_frequency"
]
accelerometer_nodes = [
    "in_accel_sampling_frequency",
    "in_accel_scale",
    "in_accel_x_calibbias",
    "in_accel_x_raw",
    "in_accel_y_calibbias",
    "in_accel_y_raw",
    "in_accel_z_calibbias",
    "in_accel_z_raw"
]
humidity_nodes = [
    "in_humidityrelative_integration_time",
    "in_humidityrelative_scale",
    "in_humidityrelative_raw",
]


def _check_node(path):
    """
    Initial a Path object for the industrial I/O sensor

    Args:
        path (str): the full path of the industrial I/O sensor

    Raises:
        FileNotFoundError: the sysfs of sensor not exists

    Returns:
        iio_node: the node of the industrial I/O sensor. (Path object)
    """
    iio_node = Path(path)
    if not iio_node.exists():
        raise FileNotFoundError("{} file not exists".format(str(iio_node)))

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


def check_pressure_sensor(index):
    """
    Validate the sysfs of industrial I/O pressure sensor

    Args:
        index (str): the index of sensor

    Raises:
        ValueError: the reading of sensor is not expected format
    """
    iio_node = _check_node(IIO_PATH + index)
    readings = []

    for sub_node in pressure_nodes:
        tmp_node = iio_node.joinpath(sub_node)
        _check_node(tmp_node)
        value = tmp_node.read_text().strip("\n")
        print("the value of {} node is {}".format(str(tmp_node), value))
        readings.append(value)

    if readings and _check_reading(readings):
        print("The pressure sensor test passed")
    else:
        raise ValueError("ERROR: The pressure value is not valid")


def check_accelerometer_sensor(index):
    """
    Validate the sysfs of industrial I/O accelerometer sensor

    Args:
        index (str): the index of sensor

    Raises:
        ValueError: the reading of sensor is not expected format
    """
    readings = []
    iio_node = _check_node(IIO_PATH + index)

    for sub_node in accelerometer_nodes:
        tmp_node = iio_node.joinpath(sub_node)
        _check_node(tmp_node)

        value = tmp_node.read_text().strip("\n")
        print("the value of {} node is {}".format(str(tmp_node), value))
        readings.append(value)

    if readings and _check_reading(readings):
        print("The accelerometer sensor test passed")
    else:
        raise ValueError("ERROR: The accelerometer value is not valid")


def check_humidity_sensor(index):
    """
    Validate the sysfs of industrial I/O humidity sensor

    Args:
        index (str): the index of sensor

    Raises:
        ValueError: the reading of sensor is not expected format
    """
    readings = []
    iio_node = _check_node(IIO_PATH + index)

    for sub_node in humidity_nodes:
        tmp_node = iio_node.joinpath(sub_node)
        _check_node(tmp_node)
        value = tmp_node.read_text().strip("\n")
        print("the value of {} node is {}".format(str(tmp_node), value))
        readings.append(value)

    if readings and _check_reading(readings):
        print("The humidity sensor test passed")
    else:
        raise ValueError("ERROR: The humidity value is not valid")


def validate_iio_sensor(args):
    """
    Check sensor and validate the format of reading

    Args:
        args (Namespace): the arguments includes type and index of sensor
    """
    test_funcs = {
        "pressure": check_pressure_sensor,
        "accelerometer": check_accelerometer_sensor,
        "humidityrelative": check_humidity_sensor
    }

    print("# Perform {} sensor test - index {}".format(args.type, args.index))
    test_funcs[args.type](args.index)
    print("# The {} sensor test passed".format(args.type))


def dump_sensor_resource(args):
    """
    Print out the sensor index and sensor type

    Args:
        args (Namespace): the arguments includes type and index of sensor
    """
    output = ""
    resource_text = "index: {}\ntype: {}\n\n"
    for sensor in args.mapping.split():
        index, sensor_type = sensor.split(":")
        output += resource_text.format(index, sensor_type)
    print(output)


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Industrial IO sensor tests')

    sub_parsers = parser.add_subparsers(dest="test_func")
    sub_parsers.required = True

    iio_test_parser = sub_parsers.add_parser("test")
    iio_test_parser.add_argument(
        "-t", "--type",
        required=True,
        choices=["pressure", "accelerometer", "humidityrelative"],
        type=str
    )
    iio_test_parser.add_argument(
        "-i", "--index",
        required=True,
        type=str,
    )
    iio_test_parser.set_defaults(test_func=validate_iio_sensor)

    iio_arg_parser = sub_parsers.add_parser("sensor-resource")
    iio_arg_parser.add_argument(
        "mapping",
        help=("Usage of parameter: IIO_SENSORS="
              "{index}:{sensor_type} {index}:{sensor_type}")
    )

    iio_arg_parser.set_defaults(test_func=dump_sensor_resource)

    args = parser.parse_args()
    return args


if __name__ == "__main__":

    args = register_arguments()

    args.test_func(args)
