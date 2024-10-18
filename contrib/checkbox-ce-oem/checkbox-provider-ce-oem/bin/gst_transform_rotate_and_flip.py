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

from enum import Enum
from typing import Any

from gst_utils import (
    GST_LAUNCH_BIN,
    VIDEO_CODEC_TESTING_DATA,
    SAMPLE_2_FOLDER,
    PipelineInterface,
    GStreamerEncodePlugins,
    MetadataValidator,
    get_big_bug_bunny_golden_sample,
    generate_artifact_name,
    compare_psnr,
    delete_file,
    execute_command,
)


logging.basicConfig(level=logging.INFO)


class Actions(Enum):
    ROTATE_90 = "rotate_90"
    ROTATE_180 = "rotate_180"
    ROTATE_270 = "rotate_270"
    VERTICAL_FLIP = "vertical_flip"
    HORIZONTAL_FLIP = "horizontal_flip"

    def __str__(self):
        return self.value


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Script helps verify the gst_transform_rotate_and_flip scenario"
        ),
    )

    parser.add_argument(
        "-p",
        "--platform",
        required=True,
        type=str,
        help="JSON file name which is also the platform e.g. genio-1200",
    )

    parser.add_argument(
        "-ep",
        "--encoder_plugin",
        required=True,
        type=str,
        help="Encoder plugin be used in gstreamer pipeline e.g. v4l2h264enc",
    )

    parser.add_argument(
        "-a",
        "--action",
        type=Actions,
        required=True,
        choices=list(Actions),
        help="Supported transform operation of rotation or flip",
    )

    parser.add_argument(
        "-wi",
        "--width",
        type=int,
        default=1920,
        help="Value of width of the golden sample",
    )

    parser.add_argument(
        "-hi",
        "--height",
        type=int,
        default=1080,
        help="Value of height of the golden sample",
    )

    parser.add_argument(
        "-f",
        "--framerate",
        type=int,
        default=0,
        help="Value of framerate. e.g. 60, 30",
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
            action=args.action,
            width=args.width,
            height=args.height,
            framerate=args.framerate,
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
        action: str,
        width: int,
        height: int,
        framerate: int,
    ):
        self._platform = platform
        self._codec = codec
        self._action = action
        self._width = width
        self._height = height
        self._framerate = framerate
        self._codec_parser_map = {
            GStreamerEncodePlugins.V4L2H264ENC.value: "h264parse"
        }
        self._actions_map = {
            Actions.ROTATE_90: "rotate=90",
            Actions.ROTATE_180: "rotate=180",
            Actions.ROTATE_270: "rotate=270",
            Actions.HORIZONTAL_FLIP: "horizontal_flip=1",
            Actions.VERTICAL_FLIP: "vertical_flip=1",
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
            self._artifact_file = generate_artifact_name(extension="mp4")
        return self._artifact_file

    @property
    def psnr_reference_file(self) -> str:
        """
        A golden reference which has been transformed in advance. It's used to
        be the compared reference file for PSNR.
        """
        golden_reference = "big_bug_bunny_{}x{}_{}fps_{}.mp4".format(
            self._width, self._height, self._framerate, self._action
        )

        full_path = os.path.join(
            VIDEO_CODEC_TESTING_DATA, SAMPLE_2_FOLDER, golden_reference
        )
        if not os.path.exists(full_path):
            raise SystemExit(
                "Error: Golden PSNR reference '{}' doesn't exist".format(
                    full_path
                )
            )

        return full_path

    def build_pipeline(self) -> str:
        """
        Build the GStreamer commands based on the platform and codec.

        Returns:
            str: A GStreamer command based on the platform and
            codec.
        """
        pipeline = (
            "{} filesrc location={} ! decodebin ! v4l2convert "
            "extra-controls='cid,{}'"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._actions_map.get(self._action),
        )

        if self._action in [Actions.ROTATE_90, Actions.ROTATE_270]:
            pipeline = (
                "{} ! video/x-raw,width={},height={},"
                "pixel-aspect-ratio='(fraction)1/1'"
            ).format(pipeline, self._height, self._width)

        pipeline = ("{} ! {} ! {} ! mp4mux ! filesink location={}").format(
            pipeline,
            self._codec,
            self._codec_parser_map.get(self._codec),
            self.artifact_file,
        )
        return pipeline


def main() -> None:
    args = register_arguments()
    p = project_factory(args)
    logging.info("Step 1: Generating artifact...")
    cmd = p.build_pipeline()
    # execute command
    execute_command(cmd=cmd)
    logging.info("\nStep 2: Checking metadata...")
    # Assign the expected width and height for validation
    # If you are verifying rotate 90 or 270 degree, the height and width
    # should be exchanged.
    expeted_width = args.width
    expeted_height = args.height
    if args.action in [Actions.ROTATE_90, Actions.ROTATE_270]:
        expeted_width = args.height
        expeted_height = args.width
    mv = MetadataValidator(file_path=p.artifact_file)
    mv.validate("width", expeted_width).validate(
        "height", expeted_height
    ).validate("frame_rate", args.framerate).validate(
        "codec", args.encoder_plugin
    ).is_valid()
    logging.info("\nStep 3: Comparing PSNR...")
    compare_psnr(
        golden_reference_file=p.psnr_reference_file,
        artifact_file=p.artifact_file,
    )
    delete_file(file_path=p.artifact_file)


if __name__ == "__main__":
    main()
