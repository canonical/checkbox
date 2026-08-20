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

from codec_base import BaseCodecProject
from codec_platforms import codec_factory
from gst_utils import (
    VIDEO_CODEC_TESTING_DATA,
    SAMPLE_2_FOLDER,
    GST_LAUNCH_BIN,
    GStreamerEncodePlugins,
    GStreamerTransformActions,
    MetadataValidator,
    compare_psnr,
    delete_file,
    execute_command,
    get_big_bug_bunny_golden_sample,
)

logging.basicConfig(level=logging.INFO)


class GenericTransformRotateAndFlipProject(BaseCodecProject):
    """
    Generic rotate/flip transform pipeline built on the v4l2convert
    element, used when the platform's codec module does not provide its
    own create_transform_rotate_and_flip_project.
    """

    def __init__(
        self,
        platform: str,
        codec: str,
        action: GStreamerTransformActions,
        width: int,
        height: int,
        framerate: int,
    ) -> None:
        super().__init__(
            platform=platform,
            codec=codec,
            width=width,
            height=height,
            framerate=framerate,
        )
        self._action = action
        self._codec_parser_map = {
            GStreamerEncodePlugins.V4L2H264ENC.value: "h264parse"
        }
        self._actions_map = {
            GStreamerTransformActions.ROTATE_90: "rotate=90",
            GStreamerTransformActions.ROTATE_180: "rotate=180",
            GStreamerTransformActions.ROTATE_270: "rotate=270",
            GStreamerTransformActions.HORIZONTAL_FLIP: "horizontal_flip=1",
            GStreamerTransformActions.VERTICAL_FLIP: "vertical_flip=1",
        }
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_big_bug_bunny_golden_sample(
            width=self._width, height=self._height, framerate=self._framerate
        )
        self._pipeline_builders = {
            GStreamerEncodePlugins.V4L2H264ENC.value: (
                self._transform_pipeline_builder
            ),
        }

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

    def _transform_pipeline_builder(self) -> str:
        """
        Build the gstreamer pipeline performing the rotate/flip action.
        """
        pipeline = (
            "{} filesrc location={} ! decodebin ! v4l2convert "
            "extra-controls='cid,{}'"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._actions_map.get(self._action),
        )

        if self._action in [
            GStreamerTransformActions.ROTATE_90,
            GStreamerTransformActions.ROTATE_270,
        ]:
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
        type=GStreamerTransformActions,
        required=True,
        choices=list(GStreamerTransformActions),
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


def main() -> None:
    args = register_arguments()
    # Platforms with their own transform pipeline provide a
    # create_transform_rotate_and_flip_project in their codec_<family>.py
    # module; everyone else uses the generic v4l2convert pipeline.
    module = codec_factory(args.platform)
    creator = (
        getattr(module, "create_transform_rotate_and_flip_project", None)
        if module
        else None
    )
    if creator:
        p = creator(args)
    else:
        p = GenericTransformRotateAndFlipProject(
            platform=args.platform,
            codec=args.encoder_plugin,
            action=args.action,
            width=args.width,
            height=args.height,
            framerate=args.framerate,
        )
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
    if args.action in [
        GStreamerTransformActions.ROTATE_90,
        GStreamerTransformActions.ROTATE_270,
    ]:
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
