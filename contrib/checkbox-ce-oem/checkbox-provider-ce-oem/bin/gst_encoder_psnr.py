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

from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Dict

from checkbox_support.scripts.psnr import get_average_psnr

logging.basicConfig(level=logging.DEBUG)
GST_LAUNCH_BIN = os.getenv("GST_LAUNCH_BIN", "gst-launch-1.0")
OUTPUT_FOLDER = os.getenv("PLAINBOX_SESSION_SHARE", "/var/tmp")
PLAINBOX_SESSION_SHARE = os.getenv("PLAINBOX_SESSION_SHARE", "/var/tmp")
VIDEO_CODEC_TESTING_DATA = os.getenv("VIDEO_CODEC_TESTING_DATA")
if not VIDEO_CODEC_TESTING_DATA or not os.path.exists(
    VIDEO_CODEC_TESTING_DATA
):
    raise SystemExit(
        "Error: Please define the proper path of golden sample folder to "
        "the environment variable 'VIDEO_CODEC_TESTING_DATA'"
    )
# Folder stores the golden samples
SAMPLE_2_FOLDER = "sample_2_big_bug_bunny"


class MuxType(Enum):
    MP4 = "mp4mux"
    AVI = "avimux"
    MATROSKA = "matroskamux"


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Script helps verify the gst_encoder_psnr scenario of specific"
            " encoder."
        ),
    )

    parser.add_argument(
        "-p",
        "--platform",
        required=True,
        type=str,
        help="Json file name which is also the platform e.g. genio-1200",
    )

    parser.add_argument(
        "-ep",
        "--encoder_plugin",
        required=True,
        type=str,
        help="Encoder plugin be used in gstreamer pipeline e.g. v4l2h264enc",
    )

    parser.add_argument(
        "-cs",
        "--color_space",
        type=str,
        default="",
        help="Color space be used in gstreamer format e.g. I420 or NV12",
    )

    parser.add_argument(
        "-wi",
        "--width",
        type=str,
        default="",
        help="Value of width of resolution",
    )

    parser.add_argument(
        "-hi",
        "--height",
        type=str,
        default="",
        help="Value of height of resolution",
    )

    parser.add_argument(
        "-f",
        "--framerate",
        type=str,
        default="",
        help="Value of framerate. e.g. 60, 30",
    )

    parser.add_argument(
        "-m",
        "--mux",
        type=str,
        default="",
        help="Value of mux. e.g. mp4mux, avimux",
    )

    args = parser.parse_args()
    return args


def get_golden_sample(
    width: str = "3840",
    height: str = "2160",
    framerate: str = "60",
    codec: str = "h264",
    container: str = "mp4",
) -> str:
    """
    Idealy, we can consume a h264 mp4 file then encode by any other codecs and
    mux it with specific muxer such as mp4mux into mp4 container.
    Therefore, we only need to adjust the width, height and framerate for
    getting golden sample.

    If you need a golden sample which doesn't exist in our sample pool, please
    contribute it and get it as your requirement.
    """
    golden_sample = "big_bug_bunny_{}x{}_{}fps_{}.{}".format(
        width, height, framerate, codec, container
    )

    full_path = os.path.join(
        VIDEO_CODEC_TESTING_DATA, SAMPLE_2_FOLDER, golden_sample
    )
    logging.debug("Golden Sample: '{}'".format(full_path))
    if not os.path.exists(full_path):
        raise SystemExit(
            "Error: Golden sample '{}' doesn't exist".format(full_path)
        )

    return full_path


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
            timeout=300,
        )
        logging.info(ret.stdout)
        return ret.stdout
    except Exception as e:
        raise SystemExit(e)


def ProjectFactory(**kwargs):
    """
    Factory
    """
    platform = kwargs.get("platform")
    if "genio" in platform:
        return GenioProject(**kwargs)
    else:
        raise SystemExit(
            "Cannot find the implementation for '{}'".format(platform)
        )


class BaseHandler(ABC):
    """Abstract base class for project-specific command handlers."""

    def __init__(self, **kwargs):
        self._platform = kwargs.get("platform")
        self._codec = kwargs.get("encoder_plugin")
        self._color_space = kwargs.get("color_space")
        self._width = kwargs.get("width")
        self._height = kwargs.get("height")
        self._framerate = kwargs.get("framerate")
        self._mux = kwargs.get("mux")
        self._output_file_extension = {
            MuxType.MP4.value: "mp4",
            MuxType.AVI.value: "avi",
            MuxType.MATROSKA.value: "mkv",
        }.get(self._mux, "unknown_format")
        # Default format of name of artifact
        self._output_file_name = "encode_psnr_{}_{}x{}_{}fps_{}.{}".format(
            self._codec,
            self._width,
            self._height,
            self._framerate,
            self._color_space,
            self._output_file_extension,
        )
        # Get the golden sample.
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_golden_sample(
            width=self._width,
            height=self._height,
            framerate=self._framerate,
        )
        # A file be treated as the reference file while doing PSNR
        # Comparision. If you want to use other file as reference while doing
        # PSNR comparison, please reassign the full path to it
        self._psnr_reference_file = self._golden_sample
        self._output_file_full_path = os.path.join(
            PLAINBOX_SESSION_SHARE,
            self._output_file_name,
        )

    @abstractmethod
    def _build_command(self) -> str:
        """
        Execute the command associated with the given method name for a
        platform.

        Returns:
            str: The corresponding command or an error message if the method
            is not found.
        """
        pass

    def execute_encode_command(self) -> None:
        logging.debug("Executing Encode Command...")
        execute_command(self._build_command())

    def compare_psnr(self) -> None:
        logging.info(
            "Compare the PSNR: {} vs {}".format(
                self._psnr_reference_file, self._output_file_full_path
            )
        )
        avg_psnr, _ = get_average_psnr(
            self._psnr_reference_file, self._output_file_full_path
        )
        logging.info("Average PSNR: {}".format(avg_psnr))
        if avg_psnr < 30 and avg_psnr > 0:
            raise SystemExit(
                "Error: The average PSNR value did not reach the acceptable"
                " threshold (30 dB)"
            )
        logging.info("Pass: Average PSNR meets the acceptable threshold")

    def check_metadata(self) -> None:
        logging.debug("Checking metadata...")
        outcome = execute_command(
            cmd="gst-discoverer-1.0 {}".format(self._output_file_full_path)
        )

        # Define the mapping for different Mux. You can add item if your
        # mux isn't included.
        container_map = {
            MuxType.MP4.value: "Quicktime",
            MuxType.AVI.value: "Audio Video Interleave (AVI)",
            MuxType.MATROSKA.value: "Matroska",
        }

        # Define the mapping for different encoders. You can add item if your
        # codec isn't included.
        codec_map = {
            "v4l2h264enc": "H.264",
            "v4l2h265enc": "H.265",
            "v4l2jpegenc": "JPEG",
        }

        # Check the meta
        is_metadata_good = True
        p = self._extract_metadata_property(input=outcome)
        if not p.get("width") or p.get("width") != self._width:
            logging.error(
                "expect width is '{}' but got '{}'".format(
                    self._width, p.get("width")
                )
            )
            is_metadata_good = False
        if not p.get("height") or p.get("height") != self._height:
            logging.error(
                "expect height is '{}' but got '{}'".format(
                    self._height, p.get("height")
                )
            )
            is_metadata_good = False

        # Ignore the codec that capture frame as image file not video.
        # The framerate of image is 0/1.
        if self._codec not in ["v4l2jpegenc"]:
            if not p.get("frame_rate") or p.get("frame_rate") != "{}/1".format(
                self._framerate
            ):
                logging.error(
                    "expect framerate is '{}' but got '{}'".format(
                        self._framerate, p.get("frame_rate")
                    )
                )
                is_metadata_good = False

        if not p.get("video_codec") or codec_map.get(self._codec) not in p.get(
            "video_codec"
        ):
            logging.error(
                "expect video codec is '{}' but got '{}'".format(
                    codec_map.get(self._codec), p.get("video_codec")
                )
            )
            is_metadata_good = False

        # Ignore the codec that capture frame as image file not video.
        # There's no concept of container of any image file.
        if self._codec not in ["v4l2jpegenc"]:
            if not p.get("container") or p.get(
                "container"
            ) != container_map.get(self._mux):
                logging.error(
                    "expect container is '{}' but got '{}'".format(
                        container_map.get(self._mux), p.get("container")
                    )
                )
                is_metadata_good = False

        if not is_metadata_good:
            raise SystemError("Error: Checking metadata failed")

    def _extract_metadata_property(self, input: str) -> Dict:
        properties = {}
        container_pattern = re.compile(r"container #\d+: (.+)")
        video_pattern = re.compile(
            r"video #\d+: (.+)|video\(image\) #\d+: (.+)"
        )
        width_pattern = re.compile(r"Width: (\d+)")
        height_pattern = re.compile(r"Height: (\d+)")
        frame_rate_pattern = re.compile(r"Frame rate: ([\d/]+)")

        properties["container"] = (
            container_pattern.search(input).group(1).replace("\n", " ").strip()
            if container_pattern.search(input)
            else None
        )
        # Check if either video or video(image) pattern matches
        video_match = video_pattern.search(input)
        if video_match:
            properties["video_codec"] = (
                video_match.group(1).strip()
                if video_match.group(1)
                else video_match.group(2).strip()
            )
        properties["width"] = (
            width_pattern.search(input).group(1)
            if width_pattern.search(input)
            else None
        )
        properties["height"] = (
            height_pattern.search(input).group(1)
            if height_pattern.search(input)
            else None
        )
        properties["frame_rate"] = (
            frame_rate_pattern.search(input).group(1)
            if frame_rate_pattern.search(input)
            else None
        )
        logging.debug("Prperties got from meta: {}".format(properties))
        return properties

    def delete_file(self):
        try:
            if os.path.exists(self._output_file_full_path):
                os.remove(self._output_file_full_path)
        except Exception as e:
            logging.warn(
                "Error occurred while deleting file: {}".format(str(e))
            )


class GenioProject(BaseHandler):
    """
    Genio project manages platforms and codecs, and handles
    building.

    Spec: https://download.mediatek.com/aiot/download/release-note/v24.0/v24.0_IoT_Yocto_Feature_Table_v1.0.pdf     # noqa: E501
    """

    def __init__(self, **kwargs):
        """
        Initialize the project with a platform and a codec.

        Args:
            platform (str): The platform name (e.g., 'Platform A').
            codec (str): The codec name (e.g., 'v4l2h264enc').
        """
        super().__init__(**kwargs)
        self._codec_parser_map = {
            "v4l2h264enc": "h264parse",
            "v4l2h265enc": "h265parse",
        }
        self._base_pipeline = (
            "{} filesrc location={} ! decodebin ! videoconvert !"
            " video/x-raw,format={} ! {}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._color_space,
            self._codec,
        )

    def _264_265_command_builder(self) -> List[str]:
        base_pipeline = (
            "{} filesrc location={} ! decodebin ! videoconvert !"
            " video/x-raw,format={} ! {}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._color_space,
            self._codec,
        )

        if self._mux in [MuxType.MP4.value, MuxType.MATROSKA.value]:
            encode_parser = self._codec_parser_map.get(self._codec)
            final_pipeline = "{} ! {} ! {} ! filesink location={}".format(
                base_pipeline,
                encode_parser,
                self._mux,
                self._output_file_full_path,
            )
        elif self._mux == MuxType.AVI.value:
            final_pipeline = "{} ! {} ! filesink location={}".format(
                base_pipeline, self._mux, self._output_file_full_path
            )
        else:
            raise SystemExit(
                "Error: Pipeline for '{}' mux not implemented.".format(
                    self._mux
                )
            )

        return final_pipeline

    def _v4l2jpecenc_command_builder(self) -> List[str]:
        if self._platform == "genio-350":
            raise SystemExit(
                "Genio 350 platform doesn't support v4l2jpecenc codec"
            )
        # Make the name of artifact and its full path
        self._output_file_name = "encode_psnr_{}x{}_{}.jpg".format(
            self._width, self._height, self._color_space
        )
        self._output_file_full_path = os.path.join(
            PLAINBOX_SESSION_SHARE, self._output_file_name
        )
        # Capture the first frame and save it as jpg file
        final_pipeline = (
            "{} filesrc location={} ! decodebin ! videorate !"
            " video/x-raw,framerate=1/1 ! videoconvert ! "
            "video/x-raw,format={} ! {} ! filesink location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._color_space,
            self._codec,
            self._output_file_full_path,
        )
        # Reassign the reference file to be an image file
        self._psnr_reference_file = os.path.join(
            VIDEO_CODEC_TESTING_DATA,
            SAMPLE_2_FOLDER,
            "big_bug_bunny_{}x{}.jpg".format(self._width, self._height),
        )
        return final_pipeline

    def _build_command(self) -> str:
        """
        Build the GStreamer commands based on the platform and codec.

        Returns:
            str: A GStreamer command based on the platform and
            codec.
        """
        if self._codec in ["v4l2h264enc", "v4l2h265enc"]:
            return self._264_265_command_builder()
        elif self._codec == "v4l2jpegenc":
            return self._v4l2jpecenc_command_builder()


def main() -> None:
    args = register_arguments()
    p = ProjectFactory(**vars(args))
    logging.info("Step 1: Generating artifact...")
    p.execute_encode_command()
    logging.info("\nStep 2: Checking metadata...")
    p.check_metadata()
    logging.info("\nStep 3: Comparing PSNR...")
    p.compare_psnr()
    # Release the disk space if no error be observed
    p.delete_file()


if __name__ == "__main__":
    main()
