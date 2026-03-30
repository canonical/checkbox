#!/usr/bin/env python3
import os
import subprocess
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
    config_path = os.environ.get("NPU_UMD_TEST_CONFIG") or "basic.yaml"

    gtest_output = subprocess.check_output(
        ["intel-npu-driver.npu-umd-test", "-l", "--config", config_path],
        universal_newlines=True,
    )

    known_failures = (
        subprocess.check_output(
            ["intel-npu-driver.known-failures"], universal_newlines=True
        )
        .strip()
        .splitlines()
    )

    for line in gtest_output.strip().splitlines():
        if "." in line:
            is_known_failure = line in known_failures

            category, test_name = line.split(".", 1)
            extra_flags = get_extra_flags(category)

            records = OrderedDict()
            records["name"] = test_name
            records["category"] = category
            records["extra_flags"] = " ".join(extra_flags)
            records["known_failure"] = is_known_failure

            print_as_resource(records)


if __name__ == "__main__":
    main()
