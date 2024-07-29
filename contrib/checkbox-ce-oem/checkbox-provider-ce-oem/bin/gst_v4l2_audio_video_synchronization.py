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
import shlex
import subprocess
from typing import Any

logging.basicConfig(level=logging.INFO)


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Script helps playing a golden sample video on specific display"
            ' by the specific "video sink", e.g. waylandsink. The golden '
            "is special video for verifying AV Synchronization."
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
        "-vs",
        "--video_sink",
        default="waylandsink",
        type=str,
        help=(
            "Specific value of video-sink for gstreamer that a video can be"
            " displayed on. (Default: waylandsink)"
        ),
    )

    parser.add_argument(
        "-cp",
        "--capssetter_pipeline",
        default="",
        type=str,
        help=("Specific value for caps setting. (Default: " ")"),
    )

    args = parser.parse_args()
    return args


def build_gst_command(
    gst_bin: str,
    golden_sample_path: str,
    decoder: str,
    video_sink: str,
    capssetter_pipeline: str,
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
    :param video_sink:
        The specific sink for video displaying on, e.g. "waylandsink"
    :param capssetter_pipeline:
        The specific value for caps setting

    :returns:
        The GStreamer command to execute.
    """

    # Why we need capssetter_pipeline?
    # Because some golden samples need a special colorimetry and configuration
    # to get it streaming smoothly.
    if capssetter_pipeline:
        decoder = "{} ! {}".format(capssetter_pipeline, decoder)

    cmd = (
        "{} -v filesrc location={} ! qtdemux name=demux demux.video_0 !"
        " queue ! parsebin ! {} ! v4l2convert "
        "output-io-mode=dmabuf-import capture-io-mode=dmabuf ! {} "
        "demux.audio_0 ! queue ! decodebin ! audioconvert ! audioresample !"
        " autoaudiosink"
    ).format(gst_bin, golden_sample_path, decoder, video_sink)

    return cmd


def execute_command(cmd: str, timeout: int = 30) -> None:
    """
    Executes the GStreamer command to play video.

    :param cmd:
        The GStreamer command to execute.
    """
    try:
        logging.info("Starting command: '{}'".format(cmd))
        ret = subprocess.run(
            shlex.split(cmd),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            timeout=timeout,
        )
        logging.info(ret.stdout)
    except subprocess.TimeoutExpired:
        # Ignore the timeout exception because some golden samples's length is
        # too long
        pass
    except Exception as e:
        logging.error(e.stderr)
        raise SystemExit(e.returncode)


def play_video_for_av_synchronization_test(args: Any) -> None:
    """
    This function performs the following steps:

    1. Checks if the golden sample file exists.
    2. Builds a GStreamer command to process the golden sample using the
        specified decoder and video sink.
    3. Executes the GStreamer command.

    :param args:
        An object containing the following attributes:
            - `golden_sample_path` (str): The path to the golden sample file.
            - `decoder_plugin` (str): The video decoder to use, e.g.,
                "v4l2vp8dec", "v4l2vp9dec".
            - `video_sink` (str): The specific sink for video displaying on,
                e.g. "waylandsink

    :raises SystemExit:
        If the golden sample file or the golden MD5 checksum file does not
        exist, or if the extracted MD5 checksum does not match the golden MD5
        checksum.
    """
    # Check the golden sample exists
    if not os.path.exists(args.golden_sample_path):
        raise SystemExit(
            "Golden Sample '{}' doesn't exist".format(args.golden_sample_path)
        )
    gst_launch_bin = os.getenv("GST_LAUNCH_BIN", "gst-launch-1.0")
    cmd = build_gst_command(
        gst_bin=gst_launch_bin,
        golden_sample_path=args.golden_sample_path,
        decoder=args.decoder_plugin,
        video_sink=args.video_sink,
        capssetter_pipeline=args.capssetter_pipeline,
    )
    # The video will be displayed on the real display
    execute_command(cmd)


def main() -> None:
    args = register_arguments()
    play_video_for_av_synchronization_test(args)


if __name__ == "__main__":
    main()
