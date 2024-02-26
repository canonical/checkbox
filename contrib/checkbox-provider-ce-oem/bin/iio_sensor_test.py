#!/usr/bin/env python3
import logging
import argparse
from pathlib import Path


IIO_PATH = "/sys/bus/iio/devices/iio:device"


def _check_root_node(path):

    iio_node = Path(path)
    if not iio_node.exists():
        raise FileNotFoundError("{} file not exists".format(str(iio_node)))

    return iio_node


def check_pressure_sensor(index):

    iio_node = _check_root_node(IIO_PATH + index)
    sub_nodes = [
        "in_pressure_input",
        "in_pressure_oversampling_ratio",
        "in_pressure_sampling_frequency"
    ]
    for sub_node in sub_nodes:
        tmp_node = iio_node.joinpath(sub_node)
        if tmp_node.exists():
            value = tmp_node.read_text().strip("\n")
            print("the value of {} node is {}".format(str(tmp_node), value))

            try:
                float(value)
            except ValueError:
                print("The accelerometer sensor test failed")
                raise ValueError("The accelerometer value is not valid")
        else:
            print("The pressure sensor test failed")
            raise FileNotFoundError(
                    "{} file not exists".format(str(tmp_node)))


def check_accelerometer_sensor(index):

    iio_node = _check_root_node(IIO_PATH + index)
    sub_nodes = [
        "in_accel_sampling_frequency",
        "in_accel_scale",
        "in_accel_x_calibbias",
        "in_accel_x_raw",
        "in_accel_y_calibbias",
        "in_accel_y_raw",
        "in_accel_z_calibbias",
        "in_accel_z_raw"
    ]
    for sub_node in sub_nodes:
        tmp_node = iio_node.joinpath(sub_node)
        if tmp_node.exists():
            value = tmp_node.read_text().strip("\n")
            print("the value of {} node is {}".format(str(tmp_node), value))

            try:
                float(value)
            except ValueError:
                print("The accelerometer sensor test failed")
                raise ValueError("The accelerometer value is not valid")
        else:
            print("The accelerometer sensor test failed")
            raise FileNotFoundError(
                    "{} file not exists".format(str(tmp_node)))


def check_humidity_sensor(index):

    iio_node = _check_root_node(IIO_PATH + index)
    sub_nodes = [
        "in_humidityrelative_integration_time",
        "in_humidityrelative_scale",
        "in_humidityrelative_raw",
    ]
    for sub_node in sub_nodes:
        tmp_node = iio_node.joinpath(sub_node)
        if tmp_node.exists():
            value = tmp_node.read_text().strip("\n")
            print("the value of {} node is {}".format(str(tmp_node), value))

            try:
                value = float(value)
            except ValueError:
                print("The accelerometer sensor test failed")
                raise ValueError("The accelerometer value is not valid")
        else:
            print("The humidity sensor test failed")
            raise FileNotFoundError(
                    "{} file not exists".format(str(tmp_node)))


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Industrial IO sensor tests')
    parser.add_argument(
        "-t", "--type",
        required=True,
        choices=["pressure", "accelerometer", "humidityrelative"],
        type=str
    )
    parser.add_argument(
        "-i", "--index",
        required=True,
        type=str,
    )

    args = parser.parse_args()
    return args


if __name__ == "__main__":

    args = register_arguments()

    test_funcs = {
        "pressure": check_pressure_sensor,
        "accelerometer": check_accelerometer_sensor,
        "humidityrelative": check_humidity_sensor
    }

    try:
        print("# Perform {} sensor test - index {}".format(
            args.type, args.index
        ))
        test_funcs[args.type](args.index)

        print("# The {} sensor test passed".format(args.type))

    except Exception as err:
        logging.error(err)
