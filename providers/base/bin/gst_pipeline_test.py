#!/usr/bin/env python3

from argparse import ArgumentParser
import gi
import logging
import re
import os
import sys
import time
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gst        # noqa: E402
from gi.repository import GLib       # noqa: E402
from subprocess import check_output  # noqa: E402


def check_state(device):
    """Checks whether the sink is available for the given device.
    """
    sink_info = check_output(['pactl', 'list', 'sinks'],
                             universal_newlines=True)

    data = sink_info.split("\n")
    try:
        device_name = re.findall(
            r".*Name:\s.*%s.*" % device, sink_info, re.IGNORECASE)[0].lstrip()
        sink = re.findall(
            r".*Name:\s(.*%s.*)" % device, sink_info,
            re.IGNORECASE)[0].lstrip()
        status = data[data.index("\t" + device_name) - 1]
    except (IndexError, ValueError):
        logging.error("Failed to find status for device: %s" % device)
        return False

    os.environ['PULSE_SINK'] = sink
    logging.info("[ Pulse sink ]".center(80, '='))
    logging.info("Device: %s %s" % (device_name.strip(), status.strip()))
    return status


def main():
    parser = ArgumentParser(description='Simple GStreamer pipeline player')
    parser.add_argument(
        'PIPELINE',
        help='Quoted GStreamer pipeline to launch')
    parser.add_argument(
        '-t', '--timeout',
        type=int, required=True,
        help='Timeout for running the pipeline')
    parser.add_argument(
        '-d', '--device',
        type=str,
        help="Device to check for status")
    args = parser.parse_args()

    logging.basicConfig(
        format='%(levelname)s:%(message)s', level=logging.INFO,
        stream=sys.stdout)

    exit_code = 0
    if args.device:
        if not check_state(args.device):
            exit_code = 1

    Gst.init(None)
    try:
        print("Attempting to initialize Gstreamer pipeline: {}".format(
              args.PIPELINE))
        element = Gst.parse_launch(args.PIPELINE)
    except GLib.GError as error:
        print("Specified pipeline couldn't be processed.")
        print("Error when processing pipeline: {}".format(error))
        # Exit harmlessly
        return(2)

    print("Pipeline initialized, now starting playback.")
    element.set_state(Gst.State.PLAYING)

    if args.timeout:
        time.sleep(args.timeout)

    element.set_state(Gst.State.NULL)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
