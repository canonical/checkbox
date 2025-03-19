#!/usr/bin/env python3
import argparse
import glob
import json
import os
import re

from look_up_xtest import look_up_app
from pathlib import Path
from systemd import journal


TEST_FILE_PREFIX = "optee-test-"


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


def dump_version():

    optee_version = _lookup_optee_version() or "unknown"
    print("optee_firmware: {}".format(optee_version))


def parse_json_file(filepath, filter=False, xtest=None):

    if not filepath:
        fw_ver = _lookup_optee_version()
        filepath = "{}{}".format(TEST_FILE_PREFIX, fw_ver)
        # append 0 when the version is not fit
        if len(fw_ver.split(".")) == 2:
            filepath += ".0"
        filepath += ".json"

    fp = Path(filepath)
    if not fp.exists():
        print("suite: {} is not available".format(filepath))
    else:
        for test in json.loads(fp.read_text()):
            if check_suite(test["suite"], filter):
                print_test_info(test, xtest)


def check_suite(suite, filter):
    if filter:
        return suite == "pkcs11"
    else:
        return suite != "pkcs11"


def print_test_info(test, xtest):
    print("suite: {}".format(test["suite"]))
    print("test_id: {}".format(test["test_id"]))
    print("test_name: {}".format(test["test_name"]))
    print("description: {}".format(test["test_description"]))
    print("tool: {}\n".format(xtest))


def register_arguments():
    parser = argparse.ArgumentParser(description="OPTEE helper scripts")
    sub_parsers = parser.add_subparsers(dest="action")

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
        "parse_xtest_src", description="Parse xtest source code and dump a JSON file"
    )
    parse_src_parser.add_argument("file_suffix")

    sub_parsers.add_parser(
        "firmware_version", description="dump OPTEE firmware and test suite source"
    )
    return parser.parse_args()


def main():
    args = register_arguments()
    if args.action == "generate":
        try:
            xtest = look_up_app("xtest", os.environ.get("XTEST"))
        except SystemError:
            xtest = None
        parse_json_file(os.environ.get("OPTEE_CASES"), args.pkcs11, xtest)
    elif args.action == "firmware_version":
        dump_version()
    elif args.action == "parse_xtest_src":
        parse_xtest_src(args.file_suffix)


if __name__ == "__main__":
    main()
