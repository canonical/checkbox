#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Checkbox Contributors
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

"""
Test FFmpeg hardware-accelerated video encoding.

Generates a short test video using the lavfi testsrc source, then encodes
it with the specified hardware encoder and profile options.  The encoder
name and profile flags are provided by the resource generator, which reads
them from fluster-decoder-map.json.  Reports pass/fail based on whether
FFmpeg completes without error.
"""

import argparse
import subprocess
import sys

INPUT_DURATION = 5
INPUT_FPS = 30
INPUT_WIDTH = 1920
INPUT_HEIGHT = 1080


def _build_ffmpeg_cmd(encoder_name, profile_opts):
    """Build the FFmpeg command list for hwaccel encoding."""
    lavfi = "testsrc=duration={}:rate={}:size={}x{}".format(
        INPUT_DURATION, INPUT_FPS, INPUT_WIDTH, INPUT_HEIGHT
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        lavfi,
    ]
    if profile_opts:
        cmd.extend(profile_opts.split())
    cmd.extend(
        [
            "-c:v",
            encoder_name,
            "-f",
            "null",
            "-",
        ]
    )
    return cmd


def main():
    parser = argparse.ArgumentParser(
        description="Test FFmpeg hardware video encoding"
    )
    parser.add_argument(
        "--encoder",
        required=True,
        help="FFmpeg encoder name (e.g. h264_vaapi, hevc_nvenc)",
    )
    parser.add_argument(
        "--profile-opts",
        default="",
        help="FFmpeg profile options (e.g. '-profile:v main')",
    )
    args = parser.parse_args()
    cmd = _build_ffmpeg_cmd(args.encoder, args.profile_opts)
    print(
        "Encoding with {} {}".format(args.encoder, args.profile_opts).strip()
    )
    print("Command: {}".format(" ".join(cmd)))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("Encoding completed successfully")
        return 0
    print(
        "ERROR: ffmpeg exited with code {}".format(result.returncode),
        file=sys.stderr,
    )
    if result.stderr:
        for line in result.stderr.splitlines():
            print("  {}".format(line), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
