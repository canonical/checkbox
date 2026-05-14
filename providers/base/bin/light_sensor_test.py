#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
import argparse
import os
import time
from typing import Dict, List, Optional


def get_all_sensors() -> List[Dict[str, str]]:
    """Returns a list of dictionaries for all detected light sensors."""
    sensors = []
    base_path = "/sys/bus/iio/devices/"

    if not os.path.exists(base_path):
        return sensors

    for device in sorted(os.listdir(base_path)):
        if "trigger" in device:
            continue

        dev_path = os.path.join(base_path, device)
        name_file = os.path.join(dev_path, "name")

        sensor_name = None
        if os.path.exists(name_file):
            try:
                with open(name_file, "r") as f:
                    sensor_name = f.read().strip()
            except IOError:
                continue

        is_light = False
        # Check by name or file presence
        if sensor_name and any(
            x in sensor_name.lower() for x in ["light", "als", "tsl", "ltr"]
        ):
            is_light = True
        else:
            try:
                if any("in_illuminance" in f for f in os.listdir(dev_path)):
                    is_light = True
            except OSError:
                continue

        if is_light:
            sensors.append(
                {
                    "name": sensor_name if sensor_name else device,
                    "path": dev_path,
                }
            )

    return sensors


def read_illuminance(sensor_path: str) -> Optional[float]:
    """Reads lux/illuminance value from sysfs."""
    targets = ["in_illuminance_input", "in_illuminance_raw", "in_illuminance"]
    for target in targets:
        file_path = os.path.join(sensor_path, target)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    return float(f.read().strip())
            except (ValueError, IOError):
                continue
    return None


def main():
    parser = argparse.ArgumentParser(description="Light Sensor Utility")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("resource", help="Print all sensor device names")

    subparsers.add_parser("detect", help="Detect if light sensors exist")

    test_parser = subparsers.add_parser("test", help="Test specific sensor")
    test_parser.add_argument("--name", required=True, help="Device name")
    test_parser.add_argument(
        "--rounds", type=int, default=5, help="Test rounds"
    )
    test_parser.add_argument(
        "--period",
        type=int,
        default=10,
        help="Seconds to wait for light change between readings",
    )
    test_parser.add_argument(
        "--delay", type=int, default=2, help="Seconds of delay between rounds"
    )
    test_parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="Minimum %% change to count as PASS",
    )

    args = parser.parse_args()

    if args.command == "resource":
        sensors = get_all_sensors()
        for s in sensors:
            print("name: {}".format(s["name"]))
            print()

    elif args.command == "detect":
        sensors = get_all_sensors()
        if not sensors:
            raise SystemExit("There is no light sensor")

    elif args.command == "test":
        sensors = get_all_sensors()
        sensors_with_matching_name = [
            s for s in sensors if s["name"] == args.name
        ]
        if len(sensors_with_matching_name) == 0:
            raise SystemExit("Error: Sensor '{}' not found.".format(args.name))
        elif len(sensors_with_matching_name) > 1:
            raise SystemExit(
                "Warning: More than 1 sensor has the name '{}'.".format(
                    args.name
                )
            )
        target_sensor = sensors_with_matching_name[0]

        passes = 0
        path = target_sensor["path"]
        print("Press enter to start test ")
        input()
        for i in range(1, args.rounds + 1):
            print("\n--- ROUND {}/{} ---".format(i, args.rounds), flush=True)
            val1 = read_illuminance(path)
            if val1 is None:
                print("Error: Could not read sensor.", flush=True)
                continue

            print(
                "Initial: {:.2f}. Change light now!".format(val1), flush=True
            )
            time.sleep(args.period)

            val2 = read_illuminance(path)
            if val2 is None:
                print("Error: Failed second reading.", flush=True)
                continue

            diff = abs(val2 - val1)
            # When val1 is 0, any positive val2 is a 100% change; otherwise
            # compute percentage relative to the baseline reading.
            pct = (
                (diff / val1 * 100)
                if val1 != 0
                else (100.0 if val2 > 0 else 0)
            )

            print("Catch new value: {:.2f}.".format(val2), flush=True)
            if pct >= args.threshold:
                print("Result: PASS ({:.1f}%)".format(pct), flush=True)
                passes += 1
            else:
                print(
                    "Result: FAIL ({:.1f}%) was detected, "
                    "but >= ({}%) was required".format(pct, args.threshold),
                    flush=True,
                )

            if i < args.rounds:
                time.sleep(args.delay)

        print(
            "\nFINAL RESULTS: {}/{} Passed".format(passes, args.rounds),
            flush=True,
        )
        if passes != args.rounds:
            raise SystemExit("Test failed")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
