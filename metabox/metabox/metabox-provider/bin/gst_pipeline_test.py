#!/usr/bin/env python3

from argparse import ArgumentParser
import gi
import sys
import time
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst        # noqa: E402
from gi.repository import GLib       # noqa: E402


def main():
    parser = ArgumentParser(description='Simple GStreamer pipeline player')
    parser.add_argument(
        'PIPELINE',
        help='Quoted GStreamer pipeline to launch')
    parser.add_argument(
        '-t', '--timeout',
        type=int, required=True,
        help='Timeout for running the pipeline')
    args = parser.parse_args()
    exit_code = 0
    Gst.init(None)
    try:
        print("Attempting to initialize Gstreamer pipeline: {}".format(
              args.PIPELINE))
        element = Gst.parse_launch(args.PIPELINE)
    except GLib.GError as error:
        print("Specified pipeline couldn't be processed.")
        print("Error when processing pipeline: {}".format(error))
        # Exit harmlessly
        return 2
    print("Pipeline initialized, now starting playback.")
    element.set_state(Gst.State.PLAYING)
    if args.timeout:
        time.sleep(args.timeout)
    element.set_state(Gst.State.NULL)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
