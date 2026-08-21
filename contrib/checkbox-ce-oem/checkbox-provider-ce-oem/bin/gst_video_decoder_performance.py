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

from codec_base import BaseCodecProject
from codec_platforms import create_scenario_project
from gst_utils import (
    execute_command,
    manage_test_file_by_name,
)

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
        "-fpss",
        "--fpsdisplaysink_sync",
        default="true",
        type=str,
        help=(
            "The property option of fpsdisplaysink. (Default: true)"
            "https://gstreamer.freedesktop.org/documentation/debugutilsbad/"
            "fpsdisplaysink.html?gi-language=python#fpsdisplaysink:sync"
        ),
    )
    parser.add_argument(
        "-p",
        "--platform",
        required=True,
        type=str,
        help="device platform uses for choosing pipeline builder e.g. imx8mp",
    )

    args = parser.parse_args()
    return args


def build_gst_command(
    gst_bin: str,
    golden_sample_path: str,
    decoder: str,
    sink: str,
    fpsdisplaysink_sync: str,
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
    :param fpsdisplaysink_sync:
        The property option of fpsdisplaysink."
        Ref: https://gstreamer.freedesktop.org/documentation/debugutilsbad/
        fpsdisplaysink.html?gi-language=python#fpsdisplaysink:sync

    :returns:
        The GStreamer command to execute.
    """
    cmd = (
        "{} -v filesrc location={} ! parsebin ! queue ! {} ! queue ! "
        "v4l2convert output-io-mode=dmabuf-import capture-io-mode=dmabuf ! "
        'queue ! fpsdisplaysink video-sink="{}"'
        " text-overlay=false sync={}"
    ).format(gst_bin, golden_sample_path, decoder, sink, fpsdisplaysink_sync)

    return cmd


class GenericDecoderPerformanceProject(BaseCodecProject):
    """
    Generic decoder-performance pipeline project; builds the command
    through the module's build_gst_command.
    """

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(
            platform=args.platform,
            codec=args.decoder_plugin,
            width=0,
            height=0,
            framerate=0,
        )
        self._golden_sample = args.golden_sample_path
        self._sink = args.sink
        self._fpsdisplaysink_sync = args.fpsdisplaysink_sync
        self._pipeline_builders = {
            args.decoder_plugin: self._performance_pipeline_builder,
        }

    def _performance_pipeline_builder(self) -> str:
        return build_gst_command(
            gst_bin=os.getenv("GST_LAUNCH_BIN", "gst-launch-1.0"),
            golden_sample_path=self._golden_sample,
            decoder=self._codec,
            sink=self._sink,
            fpsdisplaysink_sync=self._fpsdisplaysink_sync,
        )


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
        (
            "Pass Criteria \n"
            " 1. All dropped frames must be 0\n"
            " 2. All average fps values must greater than or equal to %s"
        ),
        args.minimum_fps,
    )
    with manage_test_file_by_name(
        file_name=os.path.basename(args.golden_sample_path),
        target_dir=os.path.dirname(args.golden_sample_path),
    ):
        # Platforms with their own decoder pipeline provide a
        # create_decoder_performance_project in their codec_<family>.py
        # module; everyone else uses the generic pipeline.
        project = create_scenario_project(
            args.platform,
            "create_decoder_performance_project",
            GenericDecoderPerformanceProject,
            args,
        )
        cmd = project.build_pipeline()

        output = execute_command(cmd).rstrip(os.linesep)

        is_valid = is_valid_result(output, args.minimum_fps)
        if not is_valid:
            raise SystemExit(1)
        logging.info("Pass")


if __name__ == "__main__":
    main()
