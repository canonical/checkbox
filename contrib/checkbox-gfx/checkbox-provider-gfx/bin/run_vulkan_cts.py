#!/usr/bin/python3

import subprocess
import argparse
import os
import sys


def run_vk_test(test_file, from_provider_data=False, terminate_on_fail=False):
    install_dir = "/usr/local/checkbox-gfx/VK-GL-CTS/"
    run_dir = install_dir + "build/external/vulkancts/modules/vulkan"
    binary = run_dir + "/deqp-vk"
    testfile_dir = install_dir + "external/vulkancts/mustpass/main/vk-default/"
    terminate_on_fail_str = "enable" if terminate_on_fail else "disable"
    file_path = (
        "{}/{}".format(os.environ["PLAINBOX_PROVIDER_DATA"], test_file)
        if from_provider_data
        else testfile_dir + test_file
    )

    command_list = [
        binary,
        "--deqp-caselist-file={}".format(file_path),
        "--deqp-terminate-on-fail={}".format(terminate_on_fail_str),
    ]

    process = subprocess.Popen(
        command_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=run_dir,
        universal_newlines=True,
    )

    while True:
        line = process.stdout.readline()
        if not line:
            break
        # Print the line immediately
        sys.stdout.write(line)
        sys.stdout.flush()

    return_code = process.wait()
    stderr_output = process.stderr.read()
    (
        sys.stderr.write(stderr_output)
        if stderr_output
        else sys.stderr.write("No STDERR output.\n")
    )

    exit(return_code)


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
        help="Take the test_file in the PLAINBOX_PROVIDER_DATA directory",
    )
    parser.add_argument(
        "--terminate_on_fail",
        action="store_true",
        help="Terminate on first failure",
    )
    args = parser.parse_args()

    run_vk_test(
        args.test_file, args.from_provider_data, args.terminate_on_fail
    )
