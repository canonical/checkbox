#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
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
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
#
import argparse
import logging
import os
import subprocess
import sys
import tempfile

logging.basicConfig(level=logging.INFO)

GST_LAUNCH = "gst-launch-1.0"

ENCODER_MAP = {
    "h264": "vah264enc",
    "h265": "vah265enc",
    "vp8": "vavp8enc",
    "vp9": "vavp9enc",
    "av1": "vaav1enc",
    "jpeg": "jpegenc",
    "mpeg4": "vampl4enc",
}

SUPPORTED_CODECS = sorted(ENCODER_MAP.keys())


def register_arguments():
    parser = argparse.ArgumentParser(
        description="Encode a test pattern using a GStreamer encoder "
        "and validate the output.",
    )
    parser.add_argument(
        "--codec",
        required=True,
        choices=SUPPORTED_CODECS,
        help="Codec to test",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1920,
        help="Video width (default: 1920)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=1080,
        help="Video height (default: 1080)",
    )
    parser.add_argument(
        "--framerate",
        type=int,
        default=30,
        help="Frame rate in fps (default: 30)",
    )
    parser.add_argument(
        "--num-buffers",
        type=int,
        default=60,
        help="Number of video frames to encode (default: 60)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Output file path (default: temp file)",
    )
    return parser.parse_args()


def build_pipeline(codec, width, height, framerate, num_buffers, output_file):
    encoder = ENCODER_MAP[codec]
    caps = "video/x-raw,width={},height={},framerate={}/1".format(
        width, height, framerate
    )

    if codec == "jpeg":
        return (
            "{} videotestsrc num-buffers={} ! {} ! videorate !"
            " video/x-raw,framerate=1/1 ! videoconvert !"
            " {} ! filesink location={}"
        ).format(GST_LAUNCH, 1, caps, encoder, output_file)
    elif codec == "av1":
        pipeline = (
            "{} videotestsrc num-buffers={} ! {} ! videoconvert !"
            " {} ! filesink location={}"
        ).format(GST_LAUNCH, num_buffers, caps, encoder, output_file)
    else:
        pipeline = (
            "{} videotestsrc num-buffers={} ! {} ! videoconvert !"
            " {} ! filesink location={}"
        ).format(GST_LAUNCH, num_buffers, caps, encoder, output_file)

    return pipeline


def validate_output(file_path):
    if not os.path.exists(file_path):
        logging.error("Output file does not exist: %s", file_path)
        return False
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        logging.error("Output file is empty: %s", file_path)
        return False
    logging.info("Output file created: %s (%d bytes)", file_path, file_size)
    return True


def main():
    args = register_arguments()
    output_file = args.output or tempfile.mktemp(
        suffix=".{}".format("jpg" if args.codec == "jpeg" else "mkv")
    )
    pipeline = build_pipeline(
        args.codec,
        args.width,
        args.height,
        args.framerate,
        args.num_buffers,
        output_file,
    )
    logging.info("Running pipeline: %s", pipeline)
    result = subprocess.run(
        pipeline, shell=True, capture_output=True, text=True
    )
    if result.returncode != 0:
        logging.error(
            "GStreamer pipeline failed:\n%s\n%s",
            result.stdout,
            result.stderr,
        )
        sys.exit(result.returncode)

    if not validate_output(output_file):
        sys.exit(1)

    logging.info("Encoder test passed for %s", args.codec)
    if not args.output:
        os.unlink(output_file)


if __name__ == "__main__":
    main()
