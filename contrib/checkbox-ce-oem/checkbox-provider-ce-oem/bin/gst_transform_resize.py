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

from codec_base import BaseCodecProject
from codec_platforms import create_scenario_project
from gst_utils import (
    GST_LAUNCH_BIN,
    GStreamerEncodePlugins,
    MetadataValidator,
    compare_psnr,
    delete_file,
    execute_command,
    get_test_file_path_by_params,
    manage_test_file_by_params,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s - %(module)-10s: %(funcName)s "
    + "%(lineno)-4d - %(message)s",
)

logger = logging.getLogger(__name__)


class GenericTransformResizeProject(BaseCodecProject):
    """
    Generic resize transform pipeline built on the v4l2convert element,
    used when the platform's codec module does not provide its own
    create_transform_resize_project.
    """

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__(
            platform=args.platform,
            codec=args.encoder_plugin,
            width=args.width_from,
            height=args.height_from,
            framerate=args.framerate,
        )
        self._width_to = args.width_to
        self._height_to = args.height_to
        self._codec_parser_map = {
            GStreamerEncodePlugins.V4L2H264ENC.value: "h264parse"
        }
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_test_file_path_by_params(
            self._width, self._height, self._framerate, self._codec
        )
        self._pipeline_builders = {
            GStreamerEncodePlugins.V4L2H264ENC.value: (
                self._resize_pipeline_builder
            ),
        }

    def _resize_pipeline_builder(self) -> str:
        """
        Build the gstreamer pipeline scaling the stream while encoding.
        """
        pipeline = (
            "{} filesrc location={} ! decodebin ! v4l2convert ! "
            "video/x-raw,width={},height={} ! {} ! {} ! mp4mux ! filesink"
            " location={}"
        ).format(
            GST_LAUNCH_BIN,
            self._golden_sample,
            self._width_to,
            self._height_to,
            self._codec,
            self._codec_parser_map.get(self._codec),
            self.artifact_file,
        )
        return pipeline


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
        "-wf",
        "--width_from",
        type=str,
        required=True,
        help="Value of width of the origianl resolution",
    )

    parser.add_argument(
        "-hf",
        "--height_from",
        type=str,
        required=True,
        help="Value of height of the origianl resolution",
    )

    parser.add_argument(
        "-wt",
        "--width_to",
        type=str,
        required=True,
        help="Value of width of the target resolution",
    )

    parser.add_argument(
        "-ht",
        "--height_to",
        type=str,
        required=True,
        help="Value of height of the target resolution",
    )

    parser.add_argument(
        "-f",
        "--framerate",
        type=str,
        default="",
        help="Value of framerate. e.g. 60, 30",
    )

    args = parser.parse_args()
    return args


def main() -> None:
    args = register_arguments()
    logger.info("============ Getting the 'From' file ============")
    with manage_test_file_by_params(
        args.width_from, args.height_from, args.framerate, args.encoder_plugin
    ):
        # Platforms with their own transform pipeline provide a
        # create_transform_resize_project in their codec_<family>.py
        # module; everyone else uses the generic v4l2convert
        # pipeline.
        p = create_scenario_project(
            args.platform,
            "create_transform_resize_project",
            GenericTransformResizeProject,
            args,
        )
        logging.info("Step 1: Generating artifact...")
        cmd = p.build_pipeline()
        # execute command
        execute_command(cmd=cmd)
        logging.info("\nStep 2: Checking metadata...")
        mv = MetadataValidator(file_path=p.artifact_file)
        mv.validate("width", args.width_to).validate(
            "height", args.height_to
        ).validate("frame_rate", args.framerate).validate(
            "codec", args.encoder_plugin
        ).is_valid()
        # logging.info("\nStep 3: Comparing PSNR...")
        # compare_psnr(
        #     golden_reference_file=to_file,
        #     artifact_file=p.artifact_file,
        # )
        delete_file(file_path=p.artifact_file)


if __name__ == "__main__":
    main()
