#!/usr/bin/env python3
"""Display a GStreamer test video using a sink suited to the session."""

import argparse
import os
import subprocess
import sys

# ffmpegcolorspace is the pre-videoconvert name of the converter
# carried over from the old test
CONVERTERS = ["videoconvert", "ffmpegcolorspace"]
SINKS = {
    "wayland": ["waylandsink", "glimagesink"],
    "x11": ["xvimagesink", "glimagesink"],
}


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError(
            f"expected a positive integer, got {value}"
        )
    return number


def parse_args(argv: "list[str] | None" = None) -> argparse.Namespace:
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


def first_available(candidates: "list[str]") -> str:
    for name in candidates:
        if element_exists(name):
            return name
    raise SystemExit(f"None of {candidates} is available")


def pick_sink() -> str:
    session_type = os.environ.get("XDG_SESSION_TYPE", "")
    if session_type not in SINKS:
        raise SystemExit(
            f"Not in a graphical session! XDG_SESSION_TYPE={session_type!r}"
        )
    return first_available(SINKS[session_type])


def main(argv: "list[str] | None" = None) -> int:
    args = parse_args(argv)
    pipeline = [
        "videotestsrc",
        "!",
        first_available(CONVERTERS),
        "!",
        pick_sink(),
    ]
    print(
        f" Running GStreamer pipeline for {args.timeout} seconds ".center(
            80, "-"
        )
    )
    print("Pipeline:", " ".join(pipeline))
    print(flush=True)  # just to separate out logs from gst logs
    try:
        subprocess.check_call(
            ["gst-launch-1.0", "-v"] + pipeline, timeout=args.timeout
        )
    except subprocess.TimeoutExpired:
        # pipeline won't finish by itself
        # reached timeout -> OK!
        return 0
    except subprocess.CalledProcessError as e:
        # this skips the CalledProcessError call trace
        # because gstreamer already prints all the error lines
        # more call trace is just noise
        return e.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
