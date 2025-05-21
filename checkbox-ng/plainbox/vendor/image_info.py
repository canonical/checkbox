#!/usr/bin/env python3
import sys
import json
import argparse
import subprocess
import re
from pathlib import Path

BASE_URL = "https://oem-share.canonical.com/partners"
DCD_FILE_IOT = Path("/run/mnt/ubuntu-seed/.disk/info")
VERSION = 1


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        "-v",
        help="Prints the version of the tool and exits",
        action="store_true",
    )

    return parser.parse_args(argv)


def parse_ubuntu_report():
    try:
        return json.loads(
            subprocess.check_output(
                ["ubuntu-report", "show"],
                universal_newlines=True,
            ),
        )
    except FileNotFoundError:
        raise SystemExit(
            "ubuntu-report is not installed, "
            "install it to collect this information"
        )


def dcd_string_to_info(dcd_string):
    """
    Creates a dict with all available information that can be extracted from
    the PC's dcd string, at the very least:
    - project
    - series
    - kernel type
    - build date
    - build number
    - url
    """
    # prefix, should always be present
    dcd_string = dcd_string.replace("canonical-", "")
    dcd_string = dcd_string.replace("oem-", "")
    dcd_string_arr = dcd_string.split("-")
    if len(dcd_string_arr) == 5:
        project, series, kernel_type, build_date, build_number = dcd_string_arr
        info = {
            "base_url": BASE_URL,
            "project": project,
            "series": series,
            "kernel_type": kernel_type,
            "build_date": build_date,
            "build_number": build_number,
        }
        info["url"] = (
            "{base_url}/{project}/share/releases/"
            "{series}/{kernel_type}/{build_date}-{build_number}/"
        ).format(**info)
    elif len(dcd_string_arr) == 6:
        (
            project,
            series,
            kernel_type,
            kernel_version,
            build_date,
            build_number,
        ) = dcd_string_arr
        info = {
            "base_url": BASE_URL,
            "project": project,
            "series": series,
            "kernel_type": kernel_type,
            "kernel_version": kernel_version,
            "build_date": build_date,
            "build_number": build_number,
        }
        info["url"] = (
            "{base_url}/{project}/share/releases/"
            "{series}/{kernel_type}-{kernel_version}/"
            "{build_date}-{build_number}/"
        ).format(**info)
    elif len(dcd_string_arr) == 7:
        (
            project,
            series,
            kernel_type,
            kernel_version,
            kernel_suffix,
            build_date,
            build_number,
        ) = dcd_string_arr
        info = {
            "base_url": BASE_URL,
            "project": project,
            "series": series,
            "kernel_type": kernel_type,
            "kernel_version": kernel_version,
            "kernel_suffix": kernel_suffix,
            "build_date": build_date,
            "build_number": build_number,
        }
        info["url"] = (
            "{base_url}/{project}/share/releases/"
            "{series}/{kernel_type}-{kernel_version}-{kernel_suffix}/"
            "{build_date}-{build_number}/"
        ).format(**info)
    else:
        raise SystemExit("Unknown dcd string format: {}".format(dcd_string))
    return info


def dcd_string_to_info_iot(dcd_string):
    """
    Convert IoT's dcd string to a URL based on specified rules.

    # Regex pattern:
    ^canonical-oem- : Must start with "canonical-oem-"
    ([a-zA-Z0-9]+) : Project name (alphanumeric, mandatory)
    :([a-zA-Z0-9-]+) : Series (alphanumeric and dash, mandatory)
    :([0-9.-]+) : Build ID (numbers, dot, dash, mandatory)
    (:(.*))? : Additional info (anything, optional) - currently unused
    """
    pattern = (
        r"^canonical-oem-([a-zA-Z0-9]+):([a-zA-Z0-9-]+):([0-9.-]+)(:(.*))?$"
    )

    match = re.match(pattern, dcd_string)
    if not match:
        raise ValueError(f"Invalid DCD format: {dcd_string}")

    project_name, series, build_id, _, additional_info = match.groups()

    info = {
        "base_url": BASE_URL,
        "project": project_name,
        "series": series,
        "build_id": build_id,
    }

    image_name = f"{project_name}-{series}-{build_id}.tar.xz"
    info["url"] = (
        f"{BASE_URL}/{project_name}/share/{series}/{build_id}/{image_name}"
    )

    return info


def dcd_info():
    try:
        if DCD_FILE_IOT.is_file():
            with DCD_FILE_IOT.open("r", encoding="utf-8") as f:
                dcd_string = f.read().strip()
            print("Found IoT dcd string: {}".format(dcd_string), file=sys.stderr)
            return dcd_string_to_info_iot(dcd_string)
    except (IOError, OSError):
        print("IoT dcd file not found. Assuming PC platform", file=sys.stderr)

    ubuntu_report = parse_ubuntu_report()
    print(
        "Parsed report: {}".format(json.dumps(ubuntu_report)), file=sys.stderr
    )
    try:
        dcd_string = ubuntu_report["OEM"]["DCD"]
    except KeyError:
        raise SystemExit(
            "Unable to find the OEM DCD string in the parsed report"
        )
    return dcd_string_to_info(dcd_string)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)
    if args.version:
        print(VERSION)
        return
    info = dcd_info()
    json.dump(info, sys.stdout)


if __name__ == "__main__":
    main(sys.argv[1:])
