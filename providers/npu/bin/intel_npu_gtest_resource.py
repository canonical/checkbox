#!/usr/bin/env python3
import os
import subprocess
import argparse
from collections import OrderedDict


def print_as_resource(d):
    for k, v in d.items():
        print("{}: {}".format(k, v))
    print("")


def get_extra_flags(category):
    extra_flags = []
    if category.startswith("ZeInit"):
        extra_flags.append("--ze-init-tests")

    if "DmaHeap" in category:
        extra_flags.append("--dma-heap")

    return extra_flags


def main():
    parser = argparse.ArgumentParser(description="Filter NPU UMD tests.")
    parser.add_argument(
        "-m",
        "--mode",
        choices=["blocker", "non-blocker"],
        default="blocker",
        help=" 'blocker' prints only tests that aren't known failures,"
        "'non-blocker' prints only known failures.",
    )
    args = parser.parse_args()

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
        if "." in line:
            is_known_failure = line in known_failures

            if args.mode == "blocker" and is_known_failure:
                continue
            if args.mode == "non-blocker" and not is_known_failure:
                continue

            category, test_name = line.split(".", 1)
            extra_flags = get_extra_flags(category)

            records = OrderedDict()
            records["name"] = test_name
            records["category"] = category
            records["extra_flags"] = " ".join(extra_flags)

            print_as_resource(records)


if __name__ == "__main__":
    main()
