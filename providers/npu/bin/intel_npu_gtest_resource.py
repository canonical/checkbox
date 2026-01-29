#!/usr/bin/env python3
import os
import subprocess
from collections import OrderedDict


def print_as_resource(d):
    for (
        k,
        v,
    ) in d.items():
        print("{}: {}".format(k, v))

    print("")


def parse_test_line(line, known_failures):
    if "." not in line:
        return None

    category, test_name = line.split(".", 1)
    extra_flags = get_extra_flags(category)

    record = OrderedDict()
    record["name"] = test_name
    record["category"] = category
    record["extra_flags"] = " ".join(extra_flags)
    record["cert_status"] = (
        "non-blocker" if line in known_failures else "blocker"
    )
    return record


def get_extra_flags(category):
    extra_flags = []
    if category.startswith("ZeInit"):
        extra_flags.append("--ze-init-tests")
    return extra_flags


def main():
    config_path = os.environ.get("NPU_UMD_TEST_CONFIG") or "basic.yaml"

    gtest_output = subprocess.run(
        ["intel-npu-driver.npu-umd-test", "-l", "--config", config_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    known_failures = (
        subprocess.run(
            ["intel-npu-driver.known-failures"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        .stdout.strip()
        .splitlines()
    )

    for line in gtest_output.stdout.strip().splitlines():
        record = parse_test_line(line, known_failures)
        print_as_resource(record)


if __name__ == "__main__":
    main()
