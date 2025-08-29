#!/usr/bin/python3

import subprocess
import argparse


def run_vk_test(test_file):
    install_dir = "/usr/local/checkbox-gfx/VK-GL-CTS/"
    binary = install_dir + "build/external/vulkancts/modules/vulkan/deqp-vk"
    testfile_dir = install_dir + "external/vulkancts/mustpass/main/vk-default/"
    result = subprocess.run(
        [
            binary,
            f"--deqp-caselist-file={testfile_dir + test_file}",
        ],
        capture_output=True,
        text=True,
    )
    print(result.stdout + result.stderr)
    exit(result.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run a vulkan test from VK-GL-CTS"
    )
    parser.add_argument(
        "--test_file",
        type=str,
        required=True,
        help="deqp caselist file (e.g. api.txt)",
    )
    args = parser.parse_args()

    run_vk_test(args.test_file)
