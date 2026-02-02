#!/usr/bin/env python3
import re
import subprocess
from pathlib import Path

FIRMWARE_SEARCH_DIR = Path("/var/snap/intel-npu-driver/current/intel/vpu")
VERSION_PATTERN = re.compile(r"^(\d{8}\*|[A-Z][a-z]{2}\s+\d{1,2}\s+\d{4}\*).*")


def get_active_firmware_line():
    result = subprocess.check_output(
        ["journalctl", "--dmesg"], universal_newlines=True
    ).splitlines()

    matching_lines = [line for line in result if "Firmware: intel/vpu" in line]

    if not matching_lines:
        raise SystemExit("No 'intel_vpu' firmware logs found in dmesg.")

    return matching_lines[-1]


def find_version_in_file(filepath):
    try:
        result = subprocess.check_output(
            ["strings", filepath], universal_newlines=True
        )
        for line in result.splitlines():
            # Return the first match found
            if VERSION_PATTERN.match(line):
                return line
    except (subprocess.CalledProcessError, FileNotFoundError):
        # This can happen with corrupted files or if 'strings' isn't installed
        raise SystemExit(
            "`strings` is not installed or can't read "
            "the firmware file {}.".format(filepath)
        )

    print("No version number found in the file {}".format(filepath))


def main():
    active_firmware_line = get_active_firmware_line()

    if not FIRMWARE_SEARCH_DIR.is_dir():
        raise SystemExit("Firmware directory not found.")

    found_driver_versions = []
    for filepath in FIRMWARE_SEARCH_DIR.iterdir():
        if filepath.is_file() and filepath.suffix == ".bin":
            driver_version = find_version_in_file(filepath)

            if driver_version:
                if driver_version in active_firmware_line:
                    print(
                        "Test success: Loaded NPU firmware version matches a "
                        "file from the snap. Version: {}, File: "
                        "{}".format(driver_version, str(filepath))
                    )
                    return

                found_driver_versions.append(driver_version)

    raise SystemExit(
        "The loaded firmware does not match any version in the snap files.\n"
        "Loaded firmware: {}\n"
        "Versions found in the snap: {}".format(
            active_firmware_line,
            "\n".join(map(lambda e: " - " + e, found_driver_versions)),
        )
    )


if __name__ == "__main__":
    main()
