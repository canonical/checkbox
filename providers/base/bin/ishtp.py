#!/usr/bin/env python3
import subprocess
import sys
import os
import argparse


def get_release_version():
    try:
        output = subprocess.check_output(
            ["lsb_release", "-rs"], text=True
        ).strip()
        return int(float(output))
    except (subprocess.CalledProcessError, ValueError):
        print("Error: Unable to determine release version.")
        sys.exit(1)


def is_module_loaded(module_name):
    try:
        output = subprocess.check_output(["lsmod"], text=True)
        return module_name in output
    except subprocess.CalledProcessError:
        return False


def check_modules():
    release = get_release_version()

    if release >= 24:
        expected_modules = ["intel_ishtp_hid", "intel_ish_ipc", "intel_ishtp"]
    else:
        expected_modules = [
            "intel_ishtp_loader",
            "intel_ishtp_hid",
            "intel_ish_ipc",
            "intel_ishtp",
        ]

    exit_code = 0
    for module in expected_modules:
        print(f"Checking module: {module}")
        if not is_module_loaded(module):
            print(f"FAIL: The '{module}' module is not loaded!")
            exit_code = 1
        else:
            print("PASS: It's loaded")
        print()

    return exit_code


def check_devices():
    ishtp_dir = "/sys/bus/ishtp/devices/"

    if not os.path.isdir(ishtp_dir):
        print("ISHTP devices directory does not exist!")
        print("The ISHTP folder: {}".format(ishtp_dir))
        return 1

    devices = os.listdir(ishtp_dir)
    if not devices:
        print("ISHTP devices directory empty - no devices found!")
        print("The ISHTP folder: {}".format(ishtp_dir))
        return 1

    print("Found ishtp devices under {}:".format(ishtp_dir))
    for device in devices:
        print(" - {}".format(device))

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-m",
        "--module",
        action="store_true",
        help="Check ISHTP kernel modules",
    )
    parser.add_argument(
        "-d", "--device", action="store_true", help="Check ISHTP devices"
    )
    args = parser.parse_args()

    exit_code = 0

    if args.module:
        exit_code |= check_modules()

    if args.device:
        exit_code |= check_devices()

    sys.exit(exit_code)
