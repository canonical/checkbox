#!/usr/bin/env python3
import re
import subprocess
from pathlib import (
    Path,
)

FIRMWARE_SEARCH_DIR = Path("/var/snap/intel-npu-driver/current/intel/vpu")
VERSION_PATTERN = re.compile(r"^(\d{8}\*|[A-Z][a-z]{2}\s+\d{1,2}\s+\d{4}\*).*")


def get_active_firmware_line():
    result = subprocess.run(
        [
            "journalctl",
            "--dmesg",
        ],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    all_lines = result.stdout.splitlines()

    matching_lines = [
        line for line in all_lines if "Firmware: intel/vpu" in line
    ]

    if not matching_lines:
        raise SystemExit("No 'intel_vpu' firmware logs found in dmesg.")
        return None

    return matching_lines[-1]


def find_version_in_file(filepath):
    try:
        result = subprocess.run(
            [
                "strings",
                filepath,
            ],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        for line in result.stdout.splitlines():
            # Return the first match found
            if VERSION_PATTERN.match(line):
                return line
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
    ):
        # This can happen with corrupted files or if 'strings' isn't installed
        return None
    return None


def main():
    active_firmware_line = get_active_firmware_line()

    if not FIRMWARE_SEARCH_DIR.is_dir():
        raise SystemExit("Firmware directory not found.")

    for filepath in FIRMWARE_SEARCH_DIR.iterdir():
        if filepath.is_file() and filepath.suffix == ".bin":
            driver_version = find_version_in_file(filepath)

            if driver_version and driver_version in active_firmware_line:
                print(
                    "Test success: Loaded NPU firmware version matches a "
                    "file from the snap. Version: {}, File: "
                    "{}".format(
                        driver_version,
                        str(filepath),
                    )
                )
                return

    raise SystemExit(
        "The loaded firmware does not match any version in the snap files."
    )


if __name__ == "__main__":
    main()
