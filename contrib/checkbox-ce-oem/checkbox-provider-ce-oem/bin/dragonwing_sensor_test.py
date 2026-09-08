#!/usr/bin/env python3
import subprocess
import argparse
import shlex
import os
import json
import logging
import re

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)


def run_cmd(command):
    """Execute shell command"""
    logging.info("Executing {}".format(command))
    ret = subprocess.run(
        shlex.split(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
    )
    return ret


def read_json_file(path):
    """Read the content of a JSON file"""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        logging.error("Fail to load the '{}' file".format(f))
        raise


def get_sensor_list(platform):
    """Get sensor list and supported rate"""
    path = os.path.expandvars(
        "$PLAINBOX_PROVIDER_DATA/sensor/supported_sensors.json"
    )
    sensor_list = read_json_file(path)

    if platform not in sensor_list:
        raise SystemExit("Can't find {} in the support list.".format(platform))

    return sensor_list[platform]


def dump_sensor_resource(args):
    """Dump sensor resource for tests"""
    sensors = get_sensor_list(args.platform)
    for sensor in sensors:
        for rate in sensor["supported_rate"]:
            print("name: {}".format(sensor["name"]))
            print("sample_rate: {}".format(rate))
            print()


def detect_sensor(args):
    """Detect sensors using see_workhorse"""
    command = "see_workhorse -show_sensors=1"
    result = run_cmd(command)
    if result.returncode != 0:
        logging.error("Error executing command: {}".format(result.stderr))
        return 1

    sensors = get_sensor_list(args.platform)
    expected_sensors = [sensor["name"] for sensor in sensors]

    missing = []
    for sensor_name in expected_sensors:
        if not re.search(
            r"\b" + re.escape(sensor_name) + r"\b", result.stdout
        ):
            missing.append(sensor_name)
            logging.error("{} not found.".format(sensor_name))

    if missing:
        logging.error("Missing sensors: {}".format(", ".join(missing)))
        return 1

    logging.info("All sensors are detected")
    return 0


def validate(expected, actual):
    """Validate if result are within the acceptable range."""
    lower_bound = expected * 0.9
    upper_bound = expected * 1.1

    if lower_bound <= actual <= upper_bound:
        logging.info("{} is within the expected range.".format(actual))
    else:
        logging.error("{} is out of the expected range.".format(actual))
        return 1


def streaming(args):
    """Run streaming test using ssc_drva_test."""
    command = "ssc_drva_test -sensor={} -duration={} -sample_rate={}".format(
        args.sensor, args.duration, args.sample_rate
    )
    result = run_cmd(command)
    if result.returncode != 0:
        logging.error("Error executing command: {}".format(result.stderr))
        return

    expected_sample = args.sample_rate * args.duration
    match = re.search(r"-total_samples=(\d+)", result.stdout)

    if match:
        total_sample = int(match.group(1))
        validate(expected_sample, total_sample)
    else:
        logging.error("No 'total_samples' found in the output")
        return 1

    return 0


def streaming_workhorse(args):
    """Run streaming test using see_workhorse."""
    command = (
        "see_workhorse -sensor={} -duration={}"
        " -sample_rate={} -display_events=1".format(
            args.sensor, args.duration, args.sample_rate
        )
    )
    result = run_cmd(command)
    if result.returncode != 0:
        logging.error("Error executing command: {}".format(result.stderr))
        return

    expected_count = args.sample_rate * args.duration
    match = re.findall(r'"Event Counter" : (\d+)', result.stdout)

    if match:
        event_count = int(match[-1])
        validate(expected_count, event_count)
    else:
        logging.error("No 'Event Counter' found in the output")
        return 1

    return 0


def main():
    commands = {
        "sensor-list": dump_sensor_resource,
        "detect-sensors": detect_sensor,
        "streaming": streaming,
        "streaming-workhorse": streaming_workhorse,
    }
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "subcommand", help=("subcommand to run"), choices=commands.keys()
    )
    parser.add_argument(
        "-s", "--sensor", type=str, help="which sensor to run test on"
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=int,
        help="test duration in second",
        default=10,
    )
    parser.add_argument(
        "-r", "--sample_rate", type=float, help="test sample rate"
    )
    parser.add_argument(
        "-p", "--platform", type=str, help="test target platform"
    )

    args = parser.parse_args()

    return commands[args.subcommand](args)


if __name__ == "__main__":
    raise SystemExit(main())
