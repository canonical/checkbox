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
import argparse
import logging
import os
import sys
import time
from pathlib import Path


HWMON_BASE_PATH = Path("/sys/class/hwmon")
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)


def find_hwmon_node_path(chip_name: str) -> "str|None":
    """
    Finds the absolute path of the hwmon directory given the chip name.
    """
    logging.info("Searching for hwmon node with name: '%s'...", chip_name)

    for hwmon_path in HWMON_BASE_PATH.iterdir():
        name_file = hwmon_path.joinpath("name")
        if hwmon_path.is_dir() and name_file.exists():
            try:
                actual_name = name_file.read_text(encoding="utf-8").strip()

                if actual_name == chip_name:
                    logging.info("SUCCESS: Found node path: %s", hwmon_path)
                    return hwmon_path
            except IOError as e:
                logging.error("Warning: Could not read %s: %s", name_file, e)
                continue

    logging.error("ERROR: Hwmon node '%s' not found.", chip_name)
    return None


class HwmonController:
    """
    Object-oriented controller for managing a single hwmon chip's fan controls
    """

    def __init__(self, path: Path):
        if not path.is_dir():
            raise FileNotFoundError("Hwmon path not found: {}".format(path))

        self.path = path
        self.pwm_file = self.path.joinpath("pwm1")
        self.enable_file = self.path.joinpath("pwm1_enable")

        if not self.pwm_file.exists():
            raise FileNotFoundError(
                "PWM control file 'pwm1' does not exist in {}. "
                "No fan controller found.".format(self.path)
            )

    def _read_sys_file(self, file_path: Path) -> str:
        if not file_path.exists():
            return None
        try:
            return file_path.read_text(encoding="utf-8").strip()
        except IOError as e:
            raise IOError("Failed to read {}. Error: {}".format(file_path, e))

    def _write_sys_file(self, file_path: Path, value: str):
        try:
            file_path.write_text(value, encoding="utf-8")
        except IOError as e:
            raise IOError(
                "Failed to write to {}. Error: {}".format(file_path, e)
            )

    @property
    def name(self) -> str:
        return self._read_sys_file(self.path.joinpath("name"))

    @property
    def pwm1_enable(self) -> int:
        """Reads the pwm1_enable state (0: off, 1: manual, 2+: auto)."""
        value = self._read_sys_file(self.enable_file)
        return int(value) if value.isdigit() else None

    @pwm1_enable.setter
    def pwm1_enable(self, mode: int):
        if mode not in [0, 1, 2]:
            raise ValueError(
                "PWM enable mode must be 0 (off), 1 (manual), or 2 (auto)."
            )
        self._write_sys_file(self.enable_file, str(mode))

    @property
    def pwm1(self) -> int:
        """Reads the current PWM duty cycle (0-255)."""
        value = self._read_sys_file(self.pwm_file)
        return int(value) if value.isdigit() else None

    @pwm1.setter
    def pwm1(self, value: int):
        """Sets the PWM duty cycle, checking and forcing manual mode (1)."""
        if not isinstance(value, int):
            raise ValueError("PWM value must be an integer")

        if not 0 <= value <= 255:
            raise ValueError("PWM value must be between 0 and 255")

        self._write_sys_file(self.pwm_file, str(value))
        logging.info("SUCCESS: Wrote PWM value %s", value)

    def set_pwm_with_validation(self, value: int):
        if self.pwm1_enable != 1:
            logging.info("Setting pwm1_enable to MANUAL mode (1)")
            self.pwm1_enable = 1

        self.pwm1 = value

        if self.pwm1 != value:
            logging.error("PWM value verification failed.")
            return False
        return True

    def _verify_fan_speed(self, prompt: str) -> bool:
        logging.info("%s (y/n)?", prompt)
        confirmation = input()
        if confirmation.lower().strip() in ["y", "yes"]:
            logging.info("Verification confirmed.")
            return True
        else:
            logging.error(
                "Verification failed. The fan speed was not as expected."
            )
            return False

    def turn_fan_on(self, speed=255):
        logging.info("--- TEST: Turning Fan ON (Speed: %d/255) ---", speed)
        try:
            if not self.set_pwm_with_validation(speed):
                return False
        except (IOError, ValueError) as e:
            logging.error("Failed to set fan speed: %s", e)
            return False

        time.sleep(1)
        return self._verify_fan_speed(
            "Did the fan successfully turn ON "
            "and spin at maximum speed ({}/255)?".format(speed)
        )

    def turn_fan_off(self, speed=0):
        logging.info("--- TEST: Turning Fan OFF (Speed: 0) ---")
        try:
            if not self.set_pwm_with_validation(speed):
                return False
        except (IOError, ValueError) as e:
            logging.error("Failed to set fan speed: %s", e)
            return False

        time.sleep(1)
        return self._verify_fan_speed(
            "Did the fan successfully turn OFF (stop spinning)?"
        )


def register_arguments():
    parser = argparse.ArgumentParser(
        description="PWM FAN controller test",
    )
    parser.add_argument(
        "device",
        type=str,
        help="provides a pwm controller name. e.g. pwmfan",
    )

    return parser.parse_args()


def main():
    args = register_arguments()
    fan_controller = args.device
    if not fan_controller:
        print("Usage: sudo python3 hwmon_pwm_control.py <chip_name>")
        print("  chip_name means the value of /sys/class/hwmon/hwmonX/name>")
        print("Example: sudo python3 hwmon_pwm_control.py nct6775")
        sys.exit(1)

    if os.geteuid() != 0:
        print("FATAL: This script must be run with root privileges ('sudo').")
        sys.exit(1)

    test_result = False
    hwmon_path = find_hwmon_node_path(fan_controller)
    if not hwmon_path:
        sys.exit(1)

    con = None
    initial_enable_mode = None
    initial_pwm1 = None

    try:
        con = HwmonController(hwmon_path)
        logging.info(
            "Initialized HwmonController for '%s' at %s", con.name, con.path
        )

        initial_enable_mode = con.pwm1_enable
        initial_pwm1 = con.pwm1
        logging.info(
            "--- INITIAL STATE SAVED ---\nInitial PWM: %d/255\n"
            "Initial Enable Mode: %d\n---------------------------",
            initial_pwm1,
            initial_enable_mode,
        )

        if con.turn_fan_on(speed=255) and con.turn_fan_off(speed=0):
            test_result = True

        logging.info("All tests complete.")

    except FileNotFoundError as e:
        logging.error("File Not Found Error: %s", e)
    except KeyboardInterrupt:
        logging.warning("Operation cancelled by user.")
    finally:
        logging.info("--- CLEANUP AND RESTORATION ---")
        if con:
            if initial_enable_mode is not None:
                try:
                    # Restore the original enable mode
                    con.pwm1_enable = initial_enable_mode
                    logging.info(
                        "Restored PWM Enable Mode to: %s", initial_enable_mode
                    )
                except IOError as e:
                    logging.error(
                        "Failed to restore PWM Enable Mode. Error: %s", e
                    )
            if initial_pwm1 is not None and initial_enable_mode >= 2:
                try:
                    con.pwm1 = initial_pwm1
                    logging.info("Restored PWM Value to: %s", initial_pwm1)

                except IOError as e:
                    logging.error("Failed to restore PWM Value. Error: %s", e)
    sys.exit(0 if test_result else 1)


if __name__ == "__main__":
    main()
