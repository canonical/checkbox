#!/usr/bin/python3

import subprocess
import argparse


def run_vk_test(test_file):
    result = subprocess.run(
        [
            "/usr/local/checkbox-gfx/VK-GL-CTS/build/external/vulkancts/modules/vulkan/deqp-vk",
            "--deqp-caselist-file=%s" % test_file,
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
        help="Path to VK-GL-CTS test file",
    )
    args = parser.parse_args()

    run_vk_test(args.test_file)
