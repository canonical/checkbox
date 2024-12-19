#!/usr/bin/env python3
import sys
import json
import argparse
import subprocess

BASE_URL = "https://oem-share.canonical.com/partners"
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
    the dcd string, at the very least:
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


def dcd_info():
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
