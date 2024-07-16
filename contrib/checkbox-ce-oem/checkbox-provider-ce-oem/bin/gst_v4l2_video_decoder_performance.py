#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.

import argparse
import logging
import os
import re
import shlex
import subprocess

from performance_mode_controller import performance_mode

logging.basicConfig(level=logging.INFO)


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Script helps verify the performance of specific decoder won't"
            " violate some Pass Criteria."
        ),
    )

    parser.add_argument(
        "-gp",
        "--golden_sample_path",
        required=True,
        type=str,
        help="Path of Golden Sample file",
    )

    parser.add_argument(
        "-dp",
        "--decoder_plugin",
        required=True,
        type=str,
        help="Decoder plugin be used in gstreamer pipeline e.g. v4l2h264dec",
    )

    parser.add_argument(
        "-s",
        "--sink",
        default="fakesink",
        type=str,
        help=("Specific sink that helps on judgement (default: fakesink)"),
    )

    parser.add_argument(
        "-mf",
        "--minimum_fps",
        required=True,
        type=str,
        help=(
            "The minimum value of FPS that "
            "all average FPS value should not violate"
        ),
    )

    parser.add_argument(
        "-pmt",
        "--performance_mode_target",
        default="",
        type=str,
        help="",
    )

    args = parser.parse_args()
    return args


def build_gst_command(
    gst_bin: str, golden_sample_path: str, decoder: str, sink: str
) -> str:
    """
    Builds a GStreamer command to process the golden sample.

    :param gst_bin:
        The binary name of gstreamer. Default is "gst-launch-1.0"
        You can assign the snap name to GST_LAUNCH_BIN env variable if you
        want to using snap.
    :param golden_sample:
        The path to the golden sample file.
    :param decoder:
        The decoder to use for the video, e.g., "v4l2vp8dec", "v4l2vp9dec".
    :param sink:
        The desired sink option, e.g., "fakesink".

    :returns:
        The GStreamer command to execute.
    """
    cmd = (
        "{} -v filesrc location={} ! parsebin ! queue ! {} ! queue ! "
        "v4l2convert output-io-mode=dmabuf-import capture-io-mode=dmabuf ! "
        'queue ! fpsdisplaysink video-sink="{}"'
        " text-overlay=false sync=false"
    ).format(gst_bin, golden_sample_path, decoder, sink)

    return cmd


def execute_command(cmd: str) -> str:
    """
    Executes the GStreamer command and extracts the specific data from the
    output. The specific data is the value of last-message which is exposed by
    fpsdisplaysink.

    :param cmd:
        The GStreamer command to execute.

    :returns:
        The extracted last_message.
    """
    try:
        logging.info("Starting command: '{}'".format(cmd))
        ret = subprocess.run(
            shlex.split(cmd),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            timeout=30,
        )
        logging.info(ret.stdout)
        return ret.stdout
    except Exception as e:
        logging.error(e.stderr)
        raise SystemExit(e.returncode)


def is_valid_result(input_text: str, min_fps: float) -> bool:
    """
    Extracts the last-message value from the given input string.
    Example
            last-message = rendered: 98, dropped: 0, current: 95.53,
                average: 98.43
    Pass criteria
        1. The value of dropped frame must be 0
        2. The value of average fps must greater than or equal to min_fps

    :param input_text:
        The input string containing the data of last-message.

    :param min_fps:
        A value that all average FPS must not fall below

    :returns:
        True if the result meets the pass criteria; false otherwise .
    """
    # Find all matches in the input text
    pattern = re.compile(r"dropped: (\d+), current: [\d.]+, average: ([\d.]+)")
    matches = pattern.findall(input_text)
    if not matches:
        logging.error("Unable to find any matching data.")
        return False
    for dropped, average in matches:
        # Leave once a value doesn't match the pass criteria
        if int(dropped) != 0 or float(average) < float(min_fps):
            logging.error("Found values that violate the pass criteria.")
            return False
    return True


def main() -> None:
    """
    This function performs the following steps:

    1. Checks if the golden sample file exist.
    2. Builds a GStreamer command to process the golden sample using the
        specified decoder.
    3. Executes the command and get the outcome back
    4. Judge the outcome to see if it meets the Pass Criteria

    :param args:
        An object containing the following attributes:
            - `golden_sample_path` (str): The path to the golden sample file.
            - `decoder_plugin` (str): The video decoder to use, e.g.,
                "v4l2vp8dec", "v4l2vp9dec".
            - `minimum_average_fps` (str): The minimum value of FPS
                that all average FPS value should not violate

    :raises SystemExit:
        If the golden sample file does not exist, or if the outcome violates
        the pass criteria.
    """
    args = register_arguments()
    logging.info(
        "Pass Criteria"
        "\n 1. All dropped frames must be 0"
        "\n 2. All average fps values must greater than or equal to {}".format(
            args.minimum_fps
        )
    )
    # Check the golden sample exixt
    if not os.path.exists(args.golden_sample_path):
        raise SystemExit(
            "Golden Sample '{}' doesn't exist".format(args.golden_sample_path)
        )
    gst_launch_bin = os.getenv("GST_LAUNCH_BIN", "gst-launch-1.0")
    cmd = build_gst_command(
        gst_bin=gst_launch_bin,
        golden_sample_path=args.golden_sample_path,
        decoder=args.decoder_plugin,
        sink=args.sink,
    )

    with performance_mode(args.performance_mode_target):
        output = execute_command(cmd).rstrip(os.linesep)

    if not is_valid_result(output, args.minimum_fps):
        raise SystemExit(1)
    logging.info("Pass")


if __name__ == "__main__":
    main()
