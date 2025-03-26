#!/usr/bin/env python3
import argparse
import glob
import json
import os
import re
import shlex
import subprocess

from look_up_xtest import look_up_app
from pathlib import Path
from systemd import journal
from xtest_install_ta import find_ta_path, install_ta


TEST_FILE_PREFIX = "optee-test-"


def _run_command(cmd, **kwargs):
    """Helper function to run commands and print out the command and output"""
    print("Running command: {}".format(cmd), flush=True)
    try:
        return subprocess.run(shlex.split(cmd), **kwargs)
    except subprocess.CalledProcessError as e:
        print(
            "Command failed with return code {}".format(e.returncode),
            flush=True,
        )
        print("Error output: ()".format(e.stderr), flush=True)
        raise e
    except Exception as e:
        print(
            "Unexpected error running command: {}".format(str(e)), flush=True
        )
        raise e


def launch_xtest(test_suite, test_id):
    test_utility = look_up_app("xtest", os.environ.get("XTEST"))

    print("Looking for PID of tee-supplicant..", flush=True)
    _run_command("pgrep tee-supplicant", check=True)

    optee_fw = _lookup_optee_version()

    if optee_fw is None:
        print(
            "OPTEE firmware version unavailable in journal log"
            ", check OPTEE OS is activate",
            flush=True,
        )
        return 2
    elif optee_fw < "4.0":
        ta_path = find_ta_path()
        install_ta(test_utility, ta_path)

    ret = _run_command(
        "{} -t {} {}".format(test_utility, test_suite, test_id), check=False
    )
    return ret.returncode


def parse_test_cases():
    test_cases = []
    pattern = r"ADBG_CASE_DEFINE\((.*?), (.*?), (.*?),\s+\"(.*?)\"\);"

    for file in glob.glob("**/*.c", recursive=True):
        file_obj = Path(file)
        matches = re.findall(pattern, file_obj.read_text(), re.DOTALL)
        for match in matches:
            suite, test_num, test_name, test_desc = match
            test_desc = test_desc.replace(": ", " - ")

            if suite.strip() not in ["ffa_spmc", "gp"]:
                test_desc = test_desc.strip()
                test_cases.append(
                    {
                        "suite": suite.strip(),
                        "test_id": test_num.strip(),
                        "test_name": test_name.strip(),
                        "test_description": test_desc,
                    }
                )

    return test_cases


def parse_xtest_src(version):
    output_file = "{}{}.json".format(TEST_FILE_PREFIX, version)
    test_cases = parse_test_cases()
    with open(output_file, "w") as fp:
        json.dump(test_cases, fp, indent=4)


def _lookup_optee_version():
    j_reader = journal.Reader()
    j_reader.this_boot()
    for entry in j_reader:
        match = re.search(
            r"optee: (version|revision) (\d+.\d+)", entry["MESSAGE"]
        )
        if match:
            return match.group(2)
    return None


def check_version(expected_ver):

    optee_version = _lookup_optee_version() or "unknown"
    print("optee_firmware: {}".format(optee_version))
    print("expected version: {}".format(expected_ver))
    if not expected_ver or optee_version != expected_ver:
        raise SystemExit("Error: OPTEE firmware version is not expected")
    else:
        print("Passed: OPTEE firmware version is expected")


def parse_json_file(filepath, filter_pkcs11=False):

    if not filepath:
        default_provider_path = (
            "/snap/checkbox-ce-oem/current/providers"
            "/checkbox-provider-ce-oem/data/"
        )
        fw_ver = _lookup_optee_version()
        if not fw_ver:
            print("error: failed to retrieve the version of optee")
            return
        # append 0 when the version is not fit
        if len(fw_ver.split(".")) == 2:
            filepath = "{}{}{}.0.json".format(
                default_provider_path, TEST_FILE_PREFIX, fw_ver
            )
        else:
            filepath = "{}{}{}.json".format(
                default_provider_path, TEST_FILE_PREFIX, fw_ver
            )

    fp = Path(filepath)
    if not fp.exists():
        print("error: {} is not available".format(filepath))
    else:
        for test in json.loads(fp.read_text()):
            if (filter_pkcs11 and test["suite"] == "pkcs11") or (
                not filter_pkcs11 and test["suite"] != "pkcs11"
            ):
                print_test_info(test)


def print_test_info(test):
    print("suite: {}".format(test["suite"]))
    print("test_id: {}".format(test["test_id"]))
    print("test_name: {}".format(test["test_name"]))
    print("description: {}".format(test["test_description"]))
    print()


def register_arguments():
    parser = argparse.ArgumentParser(description="OPTEE helper scripts")
    sub_parsers = parser.add_subparsers(dest="action", required=True)

    gen_tests_parser = sub_parsers.add_parser(
        "generate", description="Parse an OPTEE JSON file"
    )
    gen_tests_parser.add_argument(
        "-p",
        "--pkcs11",
        help="To filter out PKCS11 for the suite." "field in JSON.",
        action="store_true",
    )

    parse_src_parser = sub_parsers.add_parser(
        "parse_xtest_src",
        description="Parse xtest source code and dump a JSON file",
    )
    parse_src_parser.add_argument("file_suffix")

    check_parser = sub_parsers.add_parser(
        "check_firmware_version", description="check OPTEE firmware"
    )
    check_parser.add_argument(
        "expected_version", help="OPTEE firmware version"
    )

    test_parser = sub_parsers.add_parser(
        "xtest", description="perform xtest case"
    )
    test_parser.add_argument("test_suite", type=str)
    test_parser.add_argument("test_id", type=str)

    return parser.parse_args()


def main():
    args = register_arguments()
    if args.action == "generate":
        parse_json_file(os.environ.get("OPTEE_CASES"), args.pkcs11)
    elif args.action == "check_firmware_version":
        check_version(args.expected_version)
    elif args.action == "parse_xtest_src":
        parse_xtest_src(args.file_suffix)
    elif args.action == "xtest":
        raise SystemExit(launch_xtest(args.test_suite, args.test_id))


if __name__ == "__main__":
    main()
