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
from codec_platforms import codec_factory
from gst_utils import (
    GST_LAUNCH_BIN,
    GStreamerMuxerType,
    MetadataValidator,
    compare_psnr,
    delete_file,
    execute_command,
    generate_artifact_name,
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


class GenericEncoderProject(BaseCodecProject):
    """
    Reference encode pipeline used when the platform's codec module does
    not provide its own encoder-PSNR project: decode the golden sample
    with decodebin, convert, encode with the plugin under test and mux.
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
        super().__init__(
            platform=platform,
            codec=codec,
            width=width,
            height=height,
            framerate=framerate,
            color_space=color_space,
            mux=mux or "mp4mux",
        )
        # This sample video file will be consumed by any gstreamer piple
        # as input video.
        self._golden_sample = get_test_file_path_by_params(
            self._width, self._height, self._framerate, self._codec
        )
        self._pipeline_builders = {
            self._codec: self._generic_pipeline_builder,
        }

    @property
    def artifact_file(self) -> str:
        if not self._artifact_file:
            try:
                extension = GStreamerMuxerType.get_extension(
                    mux_type=self._mux.upper()
                )
            except ValueError:
                extension = "mp4"
            self._artifact_file = generate_artifact_name(extension=extension)
        return self._artifact_file

    def _generic_pipeline_builder(self) -> str:
        pipeline = "{} filesrc location={} ! decodebin ! videoconvert".format(
            GST_LAUNCH_BIN, self._golden_sample
        )
        if self._color_space:
            pipeline = "{} ! video/x-raw,format={}".format(
                pipeline, self._color_space
            )
        pipeline = "{} ! {}".format(pipeline, self._codec)
        if "264" in self._codec:
            pipeline = "{} ! h264parse".format(pipeline)
        elif "265" in self._codec:
            pipeline = "{} ! h265parse".format(pipeline)
        return "{} ! {} ! filesink location={}".format(
            pipeline, self._mux, self.artifact_file
        )


def main() -> None:
    args = register_arguments()
    with manage_test_file_by_params(
        args.width, args.height, args.framerate, args.encoder_plugin
    ):
        # Platforms with their own encoder pipeline provide a
        # create_encoder_psnr_project in their codec_<family>.py module;
        # everyone else uses the generic reference pipeline.
        module = codec_factory(args.platform)
        creator = (
            getattr(module, "create_encoder_psnr_project", None)
            if module
            else None
        )
        if creator:
            p = creator(args)
        else:
            p = GenericEncoderProject(
                platform=args.platform,
                codec=args.encoder_plugin,
                color_space=args.color_space,
                width=args.width,
                height=args.height,
                framerate=args.framerate,
                mux=args.mux,
            )
        logging.info("Step 1: Generating artifact...")
        cmd = p.build_pipeline()
        # execute command
        execute_command(cmd=cmd)
        logging.info("\nStep 2: Checking metadata...")
        mv = MetadataValidator(file_path=p.artifact_file)
        mv.validate("width", args.width).validate(
            "height", args.height
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
