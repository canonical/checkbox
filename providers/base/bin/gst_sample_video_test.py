#!/usr/bin/env python3
"""Display a GStreamer test video using a sink suited to the session."""

import argparse
import os
import subprocess
import sys

SINKS = {
    "wayland": ["waylandsink", "glimagesink"],
    "x11": ["xvimagesink", "glimagesink"],
}


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError(
            "expected a positive integer, got {}".format(value)
        )
    return number


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "timeout",
        type=positive_int,
        help="Seconds to display the video for",
    )
    return parser.parse_args(argv)


def element_exists(name: str) -> bool:
    return (
        subprocess.call(
            ["gst-inspect-1.0", "--exists", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        == 0
    )


def pick_sink() -> str:
    session_type = os.environ.get("XDG_SESSION_TYPE", "")
    if session_type not in SINKS:
        raise SystemExit(
            f"Not in a graphical session! XDG_SESSION_TYPE={session_type!r}"
        )
    for sink in SINKS[session_type]:
        if element_exists(sink):
            return sink
    raise SystemExit(
        f"None of {SINKS[session_type]} is available for a {session_type} session"
    )


def main(argv=None) -> int:
    args = parse_args(argv)
    pipeline = ["videotestsrc", "!", "videoconvert", "!", pick_sink()]
    print(
        f"Running GStreamer pipeline for {args.timeout} seconds".center(80, "-")
    )
    print("Pipeline:", " ".join(pipeline))
    sys.stdout.flush()
    try:
        return subprocess.call(
            ["gst-launch-1.0", "-v"] + pipeline, timeout=args.timeout
        )
    except subprocess.TimeoutExpired:
        # the pipeline never ends by itself, reaching the timeout is a pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
