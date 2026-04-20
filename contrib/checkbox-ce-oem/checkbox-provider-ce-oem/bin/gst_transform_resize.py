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
    GST_LAUNCH_BIN,
    PipelineInterface,
    GStreamerEncodePlugins,
    MetadataValidator,
    generate_artifact_name,
    compare_psnr,
    delete_file,
    execute_command,
    get_test_file_path_by_params,
    manage_test_file_by_params,
)

logging.basicConfig(level=logging.INFO)


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
            width_from=args.width_from,
            height_from=args.height_from,
            width_to=args.width_to,
            height_to=args.height_to,
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
        width_from: int,
        height_from: int,
        width_to: int,
        height_to: int,
        framerate: int,
    ):
        self._platform = platform
        self._codec = codec
        self._width_from = width_from
        self._height_from = height_from
        self._width_to = width_to
        self._height_to = height_to
        self._framerate = framerate
        self._codec_parser_map = {
            GStreamerEncodePlugins.V4L2H264ENC.value: "h264parse"
        }
        # This sample video file will be consumed by any gstreamer piple as
        # input video.
        self._golden_sample = get_test_file_path_by_params(
            self._width_from, self._height_from, self._framerate
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
        golden_reference = get_test_file_path_by_params(
            self._width_to, self._height_to, self._framerate
        )
        if not os.path.exists(golden_reference):
            raise SystemExit(
                "Error: Golden PSNR reference '{}' doesn't exist".format(
                    golden_reference
                )
            )

        return golden_reference

    def build_pipeline(self) -> str:
        """
        Build the GStreamer commands based on the platform and codec.
        Returns:
            str: A GStreamer command based on the platform and
            codec.
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


def main() -> None:
    args = register_arguments()
    with manage_test_file_by_params(
        args.width_from, args.height_from, args.framerate, args.encoder_plugin
    ):
        with manage_test_file_by_params(
            args.width_to, args.height_to, args.framerate, args.encoder_plugin
        ):
            p = project_factory(args)
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
            logging.info("\nStep 3: Comparing PSNR...")
            compare_psnr(
                golden_reference_file=p.psnr_reference_file,
                artifact_file=p.artifact_file,
            )
            delete_file(file_path=p.artifact_file)


if __name__ == "__main__":
    main()
