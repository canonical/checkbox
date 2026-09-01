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
from codec_platforms import create_scenario_project
from gst_utils import (
    VIDEO_CODEC_TESTING_DATA,
    GST_LAUNCH_BIN,
    GStreamerEncodePlugins,
    GStreamerTransformActions,
    MetadataValidator,
    get_codec_short_name,
    compare_psnr,
    delete_file,
    execute_command,
    get_test_file_name_by_params,
    manage_test_file_by_name,
    manage_test_file_by_params,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s - %(module)-10s: %(funcName)s "
    + "%(lineno)-4d - %(message)s",
)

logger = logging.getLogger(__name__)


class GenericTransformRotateAndFlipProject(BaseCodecProject):
    """
    Generic rotate/flip transform pipeline built on the v4l2convert
    element, used when the platform's codec module does not provide its
    own create_transform_rotate_and_flip_project.
    """

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(
            platform=args.platform,
            codec=args.encoder_plugin,
            width=args.width,
            height=args.height,
            framerate=args.framerate,
        )
        self._action = args.action
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
        golden_file = get_test_file_name_by_params(
            width=self._width,
            height=self._height,
            framerate=self._framerate,
            plugin_name=args.encoder_plugin,
        )
        self._golden_sample = os.path.join(
            VIDEO_CODEC_TESTING_DATA, golden_file
        )
        self._pipeline_builders = {
            GStreamerEncodePlugins.V4L2H264ENC.value: (
                self._transform_pipeline_builder
            ),
        }

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
    with manage_test_file_by_params(
        args.width, args.height, args.framerate, args.encoder_plugin
    ):
        # Platforms with their own transform pipeline provide a
        # create_transform_rotate_and_flip_project in their codec_<family>.py
        # module; everyone else uses the generic v4l2convert pipeline.
        p = create_scenario_project(
            args.platform,
            "create_transform_rotate_and_flip_project",
            GenericTransformRotateAndFlipProject,
            args,
        )
        logging.info("Step 1: Generating artifact...")
        cmd = p.build_pipeline()
        # execute command
        execute_command(cmd=cmd)
        logging.info("\nStep 2: Checking metadata...")
        # Assign the expected width and height for validation
        # If you are verifying rotate 90 or 270 degree, the height and width
        # should be exchanged.
        expected_width = args.width
        expected_height = args.height
        if args.action in [
            GStreamerTransformActions.ROTATE_90,
            GStreamerTransformActions.ROTATE_270,
        ]:
            expected_width = args.height
            expected_height = args.width
        mv = MetadataValidator(file_path=p.artifact_file)
        mv.validate("width", expected_width).validate(
            "height", expected_height
        ).validate("frame_rate", args.framerate).validate(
            "codec", args.encoder_plugin
        ).is_valid()

        # For example, the golden reference file is named as:
        # 1080p_60fps_h264_rotate_180.mp4
        # reference_file_name = "{}x{}_{}fps_{}_{}.mp4".format(
        #     args.width,
        #     args.height,
        #     args.framerate,
        #     get_codec_short_name(args.encoder_plugin),
        #     args.action,
        # )
        # with manage_test_file_by_name(
        #     file_name=reference_file_name
        # ) as reference_file_path:
        #     logging.info("\nStep 3: Comparing PSNR...")
        #     compare_psnr(
        #         golden_reference_file=reference_file_path,
        #         artifact_file=p.artifact_file,
        #     )
        delete_file(file_path=p.artifact_file)


if __name__ == "__main__":
    main()
