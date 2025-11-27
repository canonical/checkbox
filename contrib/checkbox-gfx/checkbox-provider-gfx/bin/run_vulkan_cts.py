#!/usr/bin/python3

import subprocess
import argparse
import os


def run_vk_test(test_file, from_provider_data, terminate_on_fail=False):
    install_dir = "/usr/local/checkbox-gfx/VK-GL-CTS/"
    binary = install_dir + "build/external/vulkancts/modules/vulkan/deqp-vk"
    testfile_dir = install_dir + "external/vulkancts/mustpass/main/vk-default/"
    terminate_on_fail_str = "enable" if terminate_on_fail else "disable"
    file_path = (
        "{}/{}".format(os.environ["PLAINBOX_PROVIDER_DATA"], test_file)
        if from_provider_data
        else testfile_dir + test_file
    )

    result = subprocess.run(
        [
            binary,
            "--deqp-caselist-file={}".format(file_path),
            "--deqp-terminate-on-fail={}".format(terminate_on_fail_str)
        ],
        capture_output=True,
        text=True,
    )
    print(result.stdout + result.stderr)
    exit(result.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a vulkan test from VK-GL-CTS")
    parser.add_argument(
        "--test_file",
        type=str,
        required=True,
        help="deqp caselist file (e.g. api.txt)",
    )
    parser.add_argument(
        "--from_provider_data",
        action="store_true",
        help="Indicates that the test_file is located in the PLAINBOX_PROVIDER_DATA directory",
    )
    parser.add_argument(
        "--keep_running_on_failures",
        action="store_true",
        help="Keep running the other tests after encountering a failure."
    )
    args = parser.parse_args()

    print(os.environ.get("PLAINBOX_PROVIDER_DATA", "Not Set"))
    run_vk_test(args.test_file, args.from_provider_data, not args.keep_running_on_failures)
