#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
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

import argparse
import logging
import os
import sys
import time

from contextlib import contextmanager
from genio_hdmirx_runner import HdmiRxToolRunner
# zapper has been remove from checkbox support
# Therefore, import it from checkbux support will have problem.
# This is the workaround to handle this issue, I still keep the logic of
# handling zapper in this script
# from checkbox_support.scripts.zapper_proxy import zapper_run

logging.basicConfig(level=logging.INFO)


@contextmanager
def disable_then_enable_ctx():
    """
    The default state of the HDMI RX feature is enabled. This function handles
    the disable and enable steps using a context manager. It ensures that the
    program takes recovery actions (enables HDMI RX feature) when unexpected
    situations occur.
    """
    try:
        hdmirx_tool = HdmiRxToolRunner()
        logging.info("Disable the HDMI RX feature ...")
        hdmirx_tool.disable_hdmi()
        logging.info("Checking the HDMI connection state ...")
        output = hdmirx_tool.check_cable()
        success = True
        if "hdmi disconnected" not in output:
            logging.info(output)
            logging.error(
                "Expect 'hdmi disconnected' but got 'hdmi connected' after "
                "disabling the HDMI RX feature"
            )
            success = False
        yield
    finally:
        logging.info("Enable the HDMI RX feature ...")
        hdmirx_tool.enable_hdmi()
        logging.info("Checking the HDMI connection state ...")
        output = hdmirx_tool.check_cable()
        if "hdmi connected" not in output:
            logging.info(output)
            logging.error(
                "Expect 'hdmi connected' but got 'hdmi disconnected' after "
                "enabling the HDMI RX feature"
            )
            success = False

        if not success:
            logging.error("Verify Failed")
            raise SystemExit(1)
        logging.info("Verify PASS")


def verify_disable_then_enable():
    """
    Check if the features of disable and enable are working.
    """
    # Call Context Manager function in order to recover the original setting.
    with disable_then_enable_ctx():
        # Do nothing since all verification logics are implemented in the
        # disable_then_enable_ctx function
        pass


def verify_check_cable_output(expected_str: str):
    if expected_str not in ["hdmi disconnected", "hdmi connected"]:
        raise ValueError(
            "Expected string must be either 'hdmi disconnected' or"
            " 'hdmi connected'."
        )

    logging.info("Checking the status of HDMI connection ...")
    outout = HdmiRxToolRunner().check_cable()
    logging.info(outout)
    if expected_str == "hdmi connected":
        if expected_str not in outout:
            raise SystemExit("Verify Failed")
    elif expected_str == "hdmi disconnected":
        if expected_str not in outout:
            raise SystemExit("Verify Failed")
    logging.info("Verify PASS")


def verify_events(action_type: str, has_zapper: bool):
    if action_type not in ["plug", "unplug"]:
        raise ValueError("Action type must be either 'plug' or 'unplug'")

    logging.info("Check the evetns for '{}' action...".format(action_type))
    outout = ""
    expected_events = []
    if has_zapper:
        zapper_host = os.environ.get("ZAPPER_HOST")
        if not zapper_host:
            raise SystemExit("ZAPPER_HOST environment variable not found!")
        with zapper_video_hotplugger_ctx(zapper_host, action_type):
            logging.debug("Before thread safe observin...")
            outout = HdmiRxToolRunner().thread_safe_start_observing(
                timeout=30,
                func=simulate_plug_unplug_behavior,
                fn_kwargs={
                    "zapper_host": zapper_host,
                    "action_type": action_type,
                },
            )
            logging.debug("After thread safe observin...")
    else:
        outout = HdmiRxToolRunner().start_observing()

    logging.info(outout)

    if action_type == "plug":
        expected_events = {
            "HDMI_RX_PWR_5V_CHANGE",
            "HDMI_RX_PLUG_IN",
            "HDMI_RX_TIMING_LOCK",
            "HDMI_RX_AUD_LOCK",
        }
    elif action_type == "unplug":
        expected_events = {
            "HDMI_RX_AUD_UNLOCK",
            "HDMI_RX_TIMING_UNLOCK",
            "HDMI_RX_PWR_5V_CHANGE",
            "HDMI_RX_PLUG_OUT",
        }

    if has_zapper:
        # Ignore the following evevts because they can be detect as the
        # physical HDMI cable be plugged or unplugged. Since we are using
        # zapper, the HDMI cable is always be connected with DUT, we cannot get
        # some events listed below.
        discard_events = {
            "HDMI_RX_PWR_5V_CHANGE",
            "HDMI_RX_PLUG_IN",
            "HDMI_RX_PLUG_OUT",
        }
        expected_events -= discard_events

    success = True
    for event in expected_events:
        logging.info("Checking event '{}' be detected...".format(event))
        if event not in outout:
            success = False
            logging.error("Fail to find '{}' event".format(event))
    if success:
        logging.info("Verify PASS")
    else:
        raise SystemExit("Verify Failed")


def verify_get_video_info_output(
    expected_horizontal: str = "1920",
    expected_vertical: str = "1080",
    expected_refresh_rate: str = "60",
):
    hdmirx_tool = HdmiRxToolRunner()
    logging.info("Checking if the video is locked ...")
    output = hdmirx_tool.check_video_locked()
    if "video unlocked" in output:
        raise SystemExit("The video lock state is 'unlocked'")

    logging.info("Checking the video info ...")
    outout = hdmirx_tool.get_video_info()
    logging.info(outout)

    success = True
    if "v.hactive = {}".format(expected_horizontal) not in outout:
        success = False
        logging.error(
            "The horizontal value doesn't match '{}'".format(
                expected_horizontal
            )
        )
    if "v.vactive = {}".format(expected_vertical) not in outout:
        success = False
        logging.error(
            "The vertical value doesn't match '{}'".format(expected_vertical)
        )
    if "v.frame_rate = {}".format(expected_refresh_rate) not in outout:
        success = False
        logging.error(
            "The refresh rate doesn't match '{}'".format(expected_refresh_rate)
        )

    if success:
        logging.info("Verify PASS")
    else:
        raise SystemExit("Verify Failed")


def verify_get_audio_info_output(
    expected_bits: str = "24",
    expected_channel: str = "2",
    expected_sample_frequency: str = "48.0",
):
    hdmirx_tool = HdmiRxToolRunner()
    logging.info("Checking if the audio is locked ...")
    output = hdmirx_tool.check_video_locked()
    if "audio unlocked" in output:
        raise SystemExit("The audio lock state is 'unlocked'")

    logging.info("Checking the audio info ...")
    outout = hdmirx_tool.get_audio_info()
    logging.info(outout)

    success = True
    if "{} bits".format(expected_bits) not in outout:
        success = False
        logging.error(
            "The Audio Bits value doesn't match '{}'".format(expected_bits)
        )
    if "Channel Number [{}]".format(expected_channel) not in outout:
        success = False
        logging.error(
            "The Audio Channel Info value doesn't match '{}'".format(
                expected_channel
            )
        )
    if "{} kHz".format(expected_sample_frequency) not in outout:
        success = False
        logging.error(
            "The Audio Sample Freq value doesn't match '{}'".format(
                expected_sample_frequency
            )
        )
    if success:
        logging.info("Verify PASS")
    else:
        raise SystemExit("Verify Failed")


@contextmanager
def zapper_video_hotplugger_ctx(
    zapper_host: str = "", action_type: str = "plug"
):
    try:
        logging.info("Setup......")
        if action_type == "plug":
            # We want to test the plug action of HDMI RX port,
            # so we have to make sure the HDMI Video Hotplugger is OFF previous
            simulate_plug_unplug_behavior(zapper_host, "unplug")
        elif action_type == "unplug":
            # We want to test the unplug action of HDMI RX port,
            # so we have to make sure the HDMI Video Hotplugger is ON previous
            simulate_plug_unplug_behavior(zapper_host, "plug")
        yield
    finally:
        logging.info("Tear Down......")
        if action_type == "unplug":
            # Always keep the zapper's video hotplugger HDMI port as ON
            simulate_plug_unplug_behavior(zapper_host, "plug")


def zapper_video_hotplugger_control(
    zapper_host: str = "", port: str = "HDMI", state: str = "ON"
):
    zapper_run(
        zapper_host, "video_hotplugger_set_state", "default", port, state
    )
    # Delay for a while let zapper does change properly
    # and let the Host (PC, Laptop) does detect properly
    time.sleep(5)


def simulate_plug_unplug_behavior(
    zapper_host: str = "", action_type: str = "plug"
):
    if action_type == "plug":
        logging.info("Zapper simulates the plug HDMI action")
        zapper_video_hotplugger_control(zapper_host=zapper_host, state="ON")
    elif action_type == "unplug":
        logging.info("zapper simulates the unplug HDMI action")
        zapper_video_hotplugger_control(zapper_host=zapper_host, state="OFF")


def arg_parser():
    parser = argparse.ArgumentParser(
        description="Veirfy the output of hdmirx tool"
    )

    # Create subparsers
    subparsers = parser.add_subparsers(title="Actions", dest="action")

    # Subparser for verify_check_cable_output
    parser_verify_check_cable_output = subparsers.add_parser(
        "verify_disable_then_enable",
        help="Verify the HDMI is connected after disable then enable it",
    )

    # Subparser for verify_check_cable_output
    parser_verify_check_cable_output = subparsers.add_parser(
        "verify_check_cable_output",
        help="Verify the connection state of HDMI RX via hdmirx tool",
    )
    parser_verify_check_cable_output.add_argument(
        "expected_str",
        choices=["hdmi disconnected", "hdmi connected"],
        help="Options for 'verify_check_cable_output' action",
    )

    # Subparser for verify_events
    parser_verify_events = subparsers.add_parser(
        "verify_events", help="Monitor and verify the plug and unplug events"
    )
    parser_verify_events.add_argument(
        "action_type",
        choices=["plug", "unplug"],
        help="The type of action we are interested in",
    )

    parser_verify_events.add_argument(
        "-wz",
        "--with_zapper",
        action="store_true",
        help="Simulate the plug and unplug actions with Zapper",
    )

    # Subparser for verify_get_video_info_output
    parser_verify_get_video_info_output = subparsers.add_parser(
        "verify_get_video_info_output",
        help="Verify the Video information of Host via hdmirx tool",
    )
    parser_verify_get_video_info_output.add_argument(
        "-rh",
        "--resolution_horizontal",
        default="1920",
        help="The horizontal resolution setting from the host (Default: 1920)",
    )
    parser_verify_get_video_info_output.add_argument(
        "-rv",
        "--resolution_vertical",
        default="1080",
        help="The vertical resolution setting from the host. (Default: 1080)",
    )
    parser_verify_get_video_info_output.add_argument(
        "-rr",
        "--refresh_rate",
        default="60",
        help="The refresh rate setting from the host. (Default: 60)",
    )

    # Subparser for verify_get_audio_info_output
    parser_verify_get_audio_info_output = subparsers.add_parser(
        "verify_get_audio_info_output",
        help="Verify the Audio information of Host via hdmirx tool",
    )
    parser_verify_get_audio_info_output.add_argument(
        "-ab",
        "--audio_bits",
        default="24",
        help="The Audio Bits resolution setting from the host. (Default: 24)",
    )
    parser_verify_get_audio_info_output.add_argument(
        "-ac",
        "--audio_channel",
        default="2",
        help="The Audio Channel setting from the host. (Default: 2)",
    )
    parser_verify_get_audio_info_output.add_argument(
        "-asf",
        "--audio_sample_frequency",
        default="48.0",
        help="The Sample Frequency setting from the host. (Default: 48.0)",
    )

    return parser


def main():
    parser = arg_parser()
    args = parser.parse_args()

    if args.action == "verify_disable_then_enable":
        verify_disable_then_enable()
    elif args.action == "verify_check_cable_output":
        verify_check_cable_output(args.expected_str)
    elif args.action == "verify_events":
        verify_events(args.action_type, args.with_zapper)
    elif args.action == "verify_get_video_info_output":
        verify_get_video_info_output(
            args.resolution_horizontal,
            args.resolution_vertical,
            args.refresh_rate,
        )
    elif args.action == "verify_get_audio_info_output":
        verify_get_audio_info_output(
            args.audio_bits, args.audio_channel, args.audio_sample_frequency
        )
    else:
        sys.exit()


if __name__ == "__main__":
    raise SystemExit(main())
