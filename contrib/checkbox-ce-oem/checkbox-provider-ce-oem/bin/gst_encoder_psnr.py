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

from typing import Any
from gst_utils import (
    VIDEO_CODEC_TESTING_DATA,
    SAMPLE_2_FOLDER,
    GST_LAUNCH_BIN,
    PipelineInterface,
    GStreamerMuxerType,
    GStreamerEncodePlugins,
    MetadataValidator,
    get_big_bug_bunny_golden_sample,
    generate_artifact_name,
    compare_psnr,
    delete_file,
    execute_command,
)


logging.basicConfig(level=logging.DEBUG)


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
        type=int,
        default=3840,
        help="Value of width of resolution",
    )

    parser.add_argument(
        "-hi",
        "--height",
        type=int,
        default=2160,
        help="Value of height of resolution",
    )

    parser.add_argument(
        "-f",
        "--framerate",
        type=int,
        default=0,
        help="Value of framerate. e.g. 60, 30",
    )

    parser.add_argument(
        "-m",
        "--mux",
        type=str,
        default="",
        help="Value of gstreamer mux. e.g. mp4mux, avimux",
    )

    args = parser.parse_args()
    return args


def project_factory(args: argparse.Namespace) -> Any:
    """
    Factory function to create a project instance based on the platform
    specified in the argparse arguments.

    Args:
        args (argparse.Namespace): A parsed argument object that contains the
            project parameters.

    Returns:
        Any: An instance of the project class (e.g., `GenioProject`) created
            with the specified parameters.

    Raises:
        SystemExit: If the platform is not recognized or supported.
    """
    if "genio" in args.platform:
        return GenioProject(
            platform=args.platform,
            codec=args.encoder_plugin,
            color_space=args.color_space,
            width=args.width,
            height=args.height,
            framerate=args.framerate,
            mux=args.mux,
        )
    else:
        raise SystemExit(
            "Error: Cannot get the implementation for '{}'".format(
                args.platform
            )
        )


class GenioProject(PipelineInterface):
    """
    Genio project manages platforms and codecs, and handles
    building.

    Spec: https://download.mediatek.com/aiot/download/release-note/v24.0/v24.0_IoT_Yocto_Feature_Table_v1.0.pdf     # noqa: E501
    """

    def __init__(
        self,
        platform: str,
        codec: str,
        color_space: str,
        width: int,
        height: int,
        framerate: int,
        mux: str,
    ) -> None:
        self._platform = platform
        self._codec = codec
        self._color_space = color_space
        self._width = width
        self._height = height
        self._framerate = framerate
        self._mux = mux
        self._codec_parser_map = {
            GStreamerEncodePlugins.V4L2H264ENC.value: "h264parse",
            GStreamerEncodePlugins.V4L2H265ENC.value: "h265parse",
        }
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_big_bug_bunny_golden_sample(
            width=self._width, height=self._height, framerate=self._framerate
        )
        self._artifact_file = ""

    @property
    def artifact_file(self) -> str:
        if not self._artifact_file:
            if self._codec == GStreamerEncodePlugins.V4L2JPEGENC.value:
                self._artifact_file = generate_artifact_name(extension="jpg")
            else:
                self._artifact_file = generate_artifact_name(
                    extension=GStreamerMuxerType.get_extension(
                        mux_type=self._mux.upper()
                    )
                )
        return self._artifact_file

    @property
    def psnr_reference_file(self) -> str:
        if self._codec == GStreamerEncodePlugins.V4L2JPEGENC.value:
            return os.path.join(
                VIDEO_CODEC_TESTING_DATA,
                SAMPLE_2_FOLDER,
                "big_bug_bunny_{}x{}.jpg".format(self._width, self._height),
            )
        else:
            return self._golden_sample

    def _264_265_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for H264 and H265 encoder
        """
        base_pipeline = (
            "{} filesrc location={} ! decodebin ! videoconvert !"
            " video/x-raw,format={} ! {}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._color_space,
            self._codec,
        )

        if self._mux.upper() in (
            GStreamerMuxerType.MP4MUX.name,
            GStreamerMuxerType.MATROSKAMUX.name,
        ):
            encode_parser = self._codec_parser_map.get(self._codec)
            final_pipeline = "{} ! {} ! {} ! filesink location={}".format(
                base_pipeline,
                encode_parser,
                self._mux,
                self.artifact_file,
            )
        elif self._mux.upper() == GStreamerMuxerType.AVIMUX.name:
            final_pipeline = "{} ! {} ! filesink location={}".format(
                base_pipeline, self._mux, self.artifact_file
            )
        else:
            raise SystemExit(
                "Error: Pipeline for '{}' mux not implemented.".format(
                    self._mux
                )
            )

        return final_pipeline

    def _v4l2jpegenc_pipeline_builder(self) -> str:
        """
        Build gstreamer pipeline for JPEG encoder
        """
        if self._platform == "genio-350":
            raise SystemExit(
                "Genio 350 platform doesn't support v4l2jpegenc codec"
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
            self.artifact_file,
        )
        return final_pipeline

    def build_pipeline(self) -> str:
        """
        Build the GStreamer commands based on the platform and codec.

        Returns:
            str: A GStreamer command based on the platform and
            codec.
        """
        if self._codec in (
            GStreamerEncodePlugins.V4L2H264ENC.value,
            GStreamerEncodePlugins.V4L2H265ENC.value,
        ):
            return self._264_265_pipeline_builder()
        elif self._codec == GStreamerEncodePlugins.V4L2JPEGENC.value:
            return self._v4l2jpegenc_pipeline_builder()
        else:
            raise SystemExit(
                "Error: unknow encoder '{}' be used".format(self._codec)
            )


def main() -> None:
    args = register_arguments()
    p = project_factory(args)
    logging.info("Step 1: Generating artifact...")
    cmd = p.build_pipeline()
    # execute command
    execute_command(cmd=cmd)
    logging.info("\nStep 2: Checking metadata...")
    mv = MetadataValidator(file_path=p.artifact_file)
    mv.validate("width", args.width).validate("height", args.height).validate(
        "frame_rate", args.framerate
    ).validate("codec", args.encoder_plugin).is_valid()
    logging.info("\nStep 3: Comparing PSNR...")
    compare_psnr(
        golden_reference_file=p.psnr_reference_file,
        artifact_file=p.artifact_file,
    )
    delete_file(file_path=p.artifact_file)


if __name__ == "__main__":
    main()
