#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# Written by:
#   Shane McKee <shane.mckee@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Exercise VAAPI hardware video decode/encode with ffmpeg.

The media sample files are provided by the ``media-samples`` snap and are no
longer downloaded at runtime. The base directory holding the samples can be
overridden with the ``MEDIA_SAMPLES_PATH`` environment variable; it defaults
to the snap mount point ``/snap/media-samples/current/media-samples``.

Hardware acceleration is confirmed by enabling the libva tracing facility
(``LIBVA_TRACE``) and inspecting the trace for the expected VAProfile /
VAEntrypoint pair.
"""

import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile

DEFAULT_SAMPLES_PATH = "/snap/media-samples/current/media-samples"
DEFAULT_VAAPI_DEVICE = "/dev/dri/renderD128"
# How many seconds of the input to process; keeps the test short.
DURATION = "5"


def samples_root():
    """Return the directory that contains the media sample files."""
    return os.environ.get("MEDIA_SAMPLES_PATH", DEFAULT_SAMPLES_PATH)


def resolve_sample(relative_path):
    """Resolve a sample path relative to the media-samples directory.

    Absolute paths are returned unchanged so the helper can also be pointed
    at an arbitrary file for local debugging.
    """
    if os.path.isabs(relative_path):
        return relative_path
    return os.path.join(samples_root(), relative_path)


def build_decode_command(input_file, device, output_file):
    """Build the ffmpeg command line for a hardware decode test."""
    return [
        "ffmpeg",
        "-hwaccel",
        "vaapi",
        "-vaapi_device",
        device,
        "-hide_banner",
        "-loglevel",
        "info",
        "-i",
        input_file,
        "-t",
        DURATION,
        "-pix_fmt",
        "yuv420p",
        "-f",
        "rawvideo",
        "-vsync",
        "1",
        "-y",
        output_file,
    ]


def build_encode_command(input_file, device, output_codec, output_file):
    """Build the ffmpeg command line for a hardware encode test.

    The input is decoded in software and uploaded to a VAAPI surface
    (``format=nv12,hwupload``) so the test exercises the hardware *encoder*
    in isolation, independent of whether the input codec can be hardware
    *decoded*. Audio is dropped (``-an``) to avoid an unrelated audio
    transcode.
    """
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-init_hw_device",
        "vaapi=va:{}".format(device),
        "-filter_hw_device",
        "va",
        "-i",
        input_file,
        "-t",
        DURATION,
        "-an",
        "-vf",
        "format=nv12,hwupload",
        "-c:v",
        output_codec,
        "-y",
        output_file,
    ]


def read_trace(trace_prefix):
    """Read and concatenate every libva trace file matching ``trace_prefix``.

    libva appends the pid (and thread id) to the configured trace file name,
    so the real files are ``<prefix>.<pid>...``.
    """
    contents = []
    for path in sorted(glob.glob(trace_prefix + "*")):
        try:
            with open(path, "r", errors="replace") as handle:
                contents.append(handle.read())
        except OSError:
            continue
    return "\n".join(contents)


def hw_acceleration_used(trace_text, profile, entrypoint):
    """Return True if the trace shows the expected profile and entrypoint.

    ``profile`` and ``entrypoint`` are treated as regular expression fragments
    (e.g. ``"7"`` or ``"(6|8)"``). A profile line must be followed shortly
    after by a matching entrypoint line, mirroring the libva trace layout::

        profile = 7
        entrypoint = 1
    """
    profile_re = re.compile(r"profile\s*=\s*(?:{})\b".format(profile))
    entrypoint_re = re.compile(r"entrypoint\s*=\s*(?:{})\b".format(entrypoint))
    lines = trace_text.splitlines()
    for index, line in enumerate(lines):
        if profile_re.search(line):
            for following in lines[index + 1 : index + 4]:
                if entrypoint_re.search(following):
                    return True
    return False


def run_ffmpeg(command, trace_prefix):
    """Run ffmpeg with libva tracing enabled and return the exit code."""
    env = dict(os.environ)
    env["LIBVA_TRACE"] = trace_prefix
    print("+ {}".format(" ".join(command)))
    result = subprocess.run(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    if result.stdout:
        print(result.stdout)
    return result.returncode


def _silent_remove(path, is_dir=False):
    try:
        if is_dir:
            os.rmdir(path)
        else:
            os.remove(path)
    except OSError:
        pass


def perform_test(args):
    """Run one decode/encode test and return 0 on success, 1 on failure."""
    input_file = resolve_sample(args.input)
    if not os.path.exists(input_file):
        print("[FAIL] input sample not found: {}".format(input_file))
        return 1

    workdir = tempfile.mkdtemp(prefix="media_hw_codec_")
    trace_prefix = os.path.join(workdir, "libva.trace")

    if args.operation == "decode":
        output_file = os.path.join(workdir, "out.yuv")
        command = build_decode_command(input_file, args.device, output_file)
    else:
        output_file = os.path.join(
            workdir, "out.{}".format(args.output_container)
        )
        command = build_encode_command(
            input_file, args.device, args.output_codec, output_file
        )

    try:
        ffmpeg_status = run_ffmpeg(command, trace_prefix)
        trace_text = read_trace(trace_prefix)
        hw_used = hw_acceleration_used(
            trace_text, args.profile, args.entrypoint
        )
    finally:
        for path in glob.glob(trace_prefix + "*"):
            _silent_remove(path)
        _silent_remove(output_file)
        _silent_remove(workdir, is_dir=True)

    if hw_used:
        print("---- [PASS] using HW {}".format(args.operation))
    else:
        print(
            "---- [FAIL] not using HW {} (expected profile={} "
            "entrypoint={})".format(
                args.operation, args.profile, args.entrypoint
            )
        )

    if ffmpeg_status != 0:
        print("---- [FAIL] ffmpeg returned {}".format(ffmpeg_status))
    else:
        print("---- [PASS] ffmpeg command completed successfully")

    if not hw_used or ffmpeg_status != 0:
        return 1
    return 0


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Test VAAPI hardware video decode/encode with ffmpeg."
    )
    parser.add_argument(
        "operation",
        choices=("decode", "encode"),
        help="whether to test hardware decode or encode",
    )
    parser.add_argument(
        "input",
        help="sample file, relative to MEDIA_SAMPLES_PATH or absolute",
    )
    parser.add_argument(
        "--profile",
        required=True,
        help="expected VAProfile value (regex fragment, e.g. '7' or '(6|8)')",
    )
    parser.add_argument(
        "--entrypoint",
        required=True,
        help="expected VAEntrypoint value (regex fragment)",
    )
    parser.add_argument(
        "--output-codec",
        help="ffmpeg output codec for encode (e.g. h264_vaapi)",
    )
    parser.add_argument(
        "--output-container",
        default="mp4",
        help="output container extension for encode (default: mp4)",
    )
    parser.add_argument(
        "--device",
        default=os.environ.get("VAAPI_DEVICE", DEFAULT_VAAPI_DEVICE),
        help="VAAPI DRM render node (default: {})".format(
            DEFAULT_VAAPI_DEVICE
        ),
    )
    args = parser.parse_args(argv)
    if args.operation == "encode" and not args.output_codec:
        parser.error("--output-codec is required for encode")
    return args


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return perform_test(args)


if __name__ == "__main__":
    sys.exit(main())
