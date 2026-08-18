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

from codec_platforms import codec_factory
from gst_utils import (
    GStreamerTransformActions,
    MetadataValidator,
    compare_psnr,
    delete_file,
    execute_command,
)

logging.basicConfig(level=logging.INFO)


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
    # The platform's pipelines live in its codec_<family>.py module,
    # resolved the same way every other scenario resolves them.
    module = codec_factory(args.platform)
    if module is None or not hasattr(
        module, "create_transform_rotate_and_flip_project"
    ):
        raise SystemExit(
            "Error: Cannot get the implementation for '{}'".format(
                args.platform
            )
        )
    p = module.create_transform_rotate_and_flip_project(args)
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
