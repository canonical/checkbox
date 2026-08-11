#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import os
import re
import subprocess


def arg_parser() -> argparse.ArgumentParser:
    """
    Parses the command line arguments.

    Returns:
    argparse.ArgumentParser: The argument parser object.
    """

    parser = argparse.ArgumentParser(
        description="Run Mediatek Proprietart tools."
    )
    parser.add_argument(
        "tool",
        choices=[
            "benchmark_dla",
            "apu_mdw_test",
            "edma_test",
            "vpu5_test",
            "mdla2_player",
            "mdla3_player",
        ],
        type=str,
    )
    parser.add_argument(
        "rest",
        nargs=argparse.REMAINDER,
        help="Arguments for the selected tool",
    )

    tool_to_function = {
        "benchmark_dla": do_benchmark_dla,
        "apu_mdw_test": do_task_and_expect_no_error,
        "edma_test": do_task_and_meet_success_pattern,
        "vpu5_test": do_task_and_expect_no_error,
        "mdla2_player": do_task_and_expect_no_error,
        "mdla3_player": do_task_and_expect_no_error,
    }

    parser.set_defaults(func=lambda args: tool_to_function[args.tool](args))

    return parser.parse_args()


def run_command(command):
    print("Executing command: '{}'".format(command))
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
        )
        print(result.stdout)
        return result.stdout
    except Exception as e:
        raise SystemExit(
            "An error occurred while executing the script: {}".format(e)
        )


def check_pattern(output: str, pattern: str) -> bool:
    """
    Checks if any line in the given output string matches the specified regex
    pattern.

    Args:
        output (str): The multiline string output to be checked.
        pattern (str): The regex pattern to search for within the output.

    Returns:
        bool: True if any line matches the pattern, False otherwise.
    """
    regex = re.compile(pattern, re.IGNORECASE)
    return any(regex.search(line) for line in output.split("\n"))


def check_positive(output: str, positive_pattern: str = r"all pass") -> bool:
    """
    Checks if any line in the given output string matches the positive pattern.

    Args:
        output (str): The multiline string output to be checked.
        positive_pattern (str, optional): The regex pattern to search for
            positive matches. Defaults to r"all pass".

    Returns:
        bool: True if any line matches the positive pattern, False otherwise.
    """
    return check_pattern(output, positive_pattern)


def check_negative(output: str, negative_pattern: str = r"error|fail") -> bool:
    """
    Checks if any line in the given output string matches the negative pattern.

    Args:
        output (str): The multiline string output to be checked.
        negative_pattern (str, optional): The regex pattern to search for
            negative matches. Defaults to r"error|fail".

    Returns:
        bool: True if any line matches the negative pattern, False otherwise.
    """
    return check_pattern(output, negative_pattern)


def do_task_and_meet_success_pattern(args) -> bool:
    """
    Returns:
        bool: True means Pass, False otherwise.
    """
    output = run_command([args.tool] + args.rest)
    return check_positive(output)


def do_task_and_expect_no_error(args) -> bool:
    """
    Returns:
        bool: True means Pass, False otherwise.
    """
    output = run_command([args.tool] + args.rest)
    return not check_negative(output)


def do_benchmark_dla(args) -> bool:
    """
    Executes the benchmark script at the specified path.
    https://mediatek.gitlab.io/genio/doc/ubuntu/bsp-installation/neuropilot.html

    Returns:
        bool: True means Pass, False otherwise.
    """
    # By design from Mediatek, the script must need to be put at specific path
    script_path = "/usr/share/benchmark_dla/benchmark.py"
    if not os.path.exists(script_path):
        raise SystemExit(
            "benchmark.py script doesn't exist at /usr/share/benchmark_dla/"
        )

    command = ["python3", script_path, "--auto"]
    output = run_command(command)

    res = compare_inference_times_of_benchmark_dla(data=output)

    if not res:
        print("Error: not all mdla's average inference time less than vpu_fpu")
    return res


def compare_inference_times_of_benchmark_dla(data: str) -> bool:
    """
    Compares the average inference times of models between `mdla` and `vpu_fpu`

    This function parses a given string containing inference time data for
    various models and compares the average inference times between `mdla` and
    `vpu_fpu` for each model.

    Parameters:
        - data (str): The input data contains the specific pattern, always has
            mdla(2.0/3.0) and vpu_fpu as pair.
            EX:
              /usr/share/benchmark_dla/ssd_mobilenet_v1_coco_quantized.tflite, mdla2.0, avg inference time: 3.04    # noqa E501
              /usr/share/benchmark_dla/ssd_mobilenet_v1_coco_quantized.tflite, vpu_fpu, avg inference time: 25.59   # noqa E501

    Returns:
        `True` if all `mdla` inference times are lower than the corresponding
        `vpu_fpu` inference times, otherwise it returns `False`.
    """
    # Regular expression to extract the relevant parts of the output
    pattern = re.compile(
        r"(?P<model_path>.+\.tflite), (?P<type>mdla\d\.0|vpu_fpu), avg inference time: (?P<avg_time>\d+\.\d+)"  # noqa E501
    )

    # Dictionaries to store the inference times
    mdla_times = {}
    vpu_fpu_times = {}

    # Parse the data
    for line in data.splitlines():
        match = pattern.search(line)
        if match:
            model_path = match.group("model_path").strip()
            inf_type = match.group("type").strip()
            avg_time = float(match.group("avg_time").strip())

            if "mdla" in inf_type:
                mdla_times[model_path] = avg_time
            elif inf_type == "vpu_fpu":
                vpu_fpu_times[model_path] = avg_time

    # Check and compare inference times
    all_good = all(
        mdla_times[model] < vpu_fpu_times[model]
        for model in mdla_times
        if model in vpu_fpu_times
    )
    return all_good


def main() -> None:
    args = arg_parser()
    is_pass = args.func(args)
    raise SystemExit(not is_pass)


if __name__ == "__main__":
    main()
