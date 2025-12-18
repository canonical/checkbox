#!/usr/bin/env python3
import subprocess
import os
import argparse
from checkbox_support.helpers.release_info import get_release_info


def get_module_list():
    output = subprocess.check_output(["lsmod"], universal_newlines=True)
    return [line.split()[0] for line in output.splitlines() if line]


def check_modules():
    release = int(get_release_info()["release"].split(".")[0])

    if release >= 24:
        expected_modules = ["intel_ishtp_hid", "intel_ish_ipc", "intel_ishtp"]
    else:
        expected_modules = [
            "intel_ishtp_loader",
            "intel_ishtp_hid",
            "intel_ish_ipc",
            "intel_ishtp",
        ]

    module_list = get_module_list()
    for module in expected_modules:
        print("Checking module: {}".format(module))
        if module not in module_list:
            raise SystemExit(
                "FAIL: The '{}' module is not loaded!".format(module)
            )
        else:
            print("PASS: It's loaded")
        print()


def check_devices():
    ishtp_dir = "/sys/bus/ishtp/devices/"

    if not os.path.isdir(ishtp_dir):
        raise SystemExit(
            "The ISHTP folder does not exist:  {}".format(ishtp_dir)
        )

    devices = os.listdir(ishtp_dir)
    if not devices:
        raise SystemExit(
            "No devices found on the ISHTP folder:  {}".format(ishtp_dir)
        )

    print("Found ishtp devices under {}:".format(ishtp_dir))
    for device in devices:
        print(" - {}".format(device))


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

    if args.module:
        check_modules()

    if args.device:
        check_devices()
