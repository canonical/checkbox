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
#
# This script is used to interact with the mtk_hdmirx_tool. You can find the
# source code of mtk_hdmi_rx from the following link:
#   - https://gitlab.com/mediatek/aiot/bsp/mtk-hdmirx-tool
#
# The following output is the first glance of hdmirx_tool.
# User can choose any action to manipulate with it.
#
#   root@mtk-genio:/home/ubuntu# ./hdmirx_tool
#   hdmirx tool version:   1.0.0
#   hdmirx driver version: 1.0.0
#
#   1) enable hdmi      2) disable hdmi
#   3) get device info  4) check cable
#   5) get video info   6) check video locked
#   7) get audio info   8) check audio locked
#   a) start observing  b) stop observing
#   h) help             q) quit
import argparse
import inspect
import logging
import os
import pexpect
import time

from typing import Callable, Dict


class HdmiRxToolRunner:
    def __init__(self, tool_name: str = "genio-test-tool.hdmi-rx-tool"):
        self._tool_name = tool_name
        self._expected_pattern = "(?i)hdmirx tool version"

    def _run_expect(
        self,
        action: str = "h",
        timeout: int = 3
    ):
        """Execute the specific action which are supported by HDMI RX tool"""
        command_output = pexpect.run(
            self._tool_name,
            events={self._expected_pattern: "{}{}".format(action, os.linesep)},
            timeout=timeout,
            encoding="utf-8",
        )
        return command_output

    def enable_hdmi(self):
        """Enable HDMI RX Feature
        Example Output:
            getchar=1
            hdmi_enable[1]
        """
        return self._run_expect(action="1")

    def disable_hdmi(self):
        """Disable HDMI RX Feature
        Example Output:
            getchar=2
            hdmi_enable[0]
        """
        return self._run_expect(action="2")

    def get_device_info(self):
        """Get device information through HDMI RX
        Example Output:
            getchar=3
            hdmi_get_device_info
            d.hdmirx5v = 1
            d.hpd = 1
            d.power_on = 1
            d.vid_locked = 0
            d.aud_locked = 0
            d.hdcp_version = 0
        """
        return self._run_expect(action="3")

    def check_cable(self):
        """Get the connection state of HDMI RX
        Example Output:
            getchar=4
            hdmi_check_cable
            hdmi_get_device_info
            hdmi connected
        """
        return self._run_expect(action="4")

    def get_video_info(self):
        """Get video information through HDMI RX
        Example Output:
            getchar=5
            hdmi_get_video_info
            v.cs = 0
            v.dp = 0
            v.htotal = 0
            v.vtotal = 0
            v.hactive = 0
            v.vactive = 0
            v.is_pscan = 1
            v.hdmi_mode = 0
            v.frame_rate = 0
            v.pixclk = 0
        """
        return self._run_expect(action="5")

    def check_video_locked(self):
        """Check the lock state of video through HDMI RX
        Example Output:
            getchar=6
            hdmi_check_video_locked
            hdmi_get_device_info
            video unlocked
        """
        return self._run_expect(action="6")

    def get_audio_info(self):
        """Get audio information through HDMI RX
        Example Output:
            getchar=7
            hdmi_get_audio_info
            a.info.is_HBRAudio = 0
            a.info.is_DSDAudio = 0
            a.info.is_RawSDAudio = 0
            a.info.is_PCMMultiCh = 1
            a.caps.SampleFreq = 1
            a.caps.AudInf.info.AudioChannelCount = 0
            a.caps.AudInf.info.SpeakerPlacement = 0
            a.caps.AudChStat.WordLen = 0
            Audio Bits:
                not indicated (default)
            Audio Channel Info:
                Channel Number by Stream Header
                Speaker Placement [0x0]
            Audio Sample Freq:
                Please mapping [1] to HDMI2_AUD_FS manually..
        """
        return self._run_expect(action="7")

    def check_audio_locked(self):
        """Check the lock state of audio through HDMI RX
        Example Output:
            getchar=8
            hdmi_check_audio_locked
            hdmi_get_device_info
            audio unlocked
        """
        return self._run_expect(action="8")

    def start_observing(self, timeout: int = 15):
        """Start observing the event of HDMI RX, such as plug and unplug cable
        By default, monitor events for 15 seconds.
        """
        return self._run_expect(action="a", timeout=timeout)

    def stop_observing(self):
        """Stop observing the event of HDMI RX"""
        return self._run_expect(action="b")

    def thread_safe_start_observing(
        self, timeout: int = 15, func: Callable = None, fn_kwargs: Dict = {}
    ):
        """Execute the specific action using pexpect.spawn"""
        logging.debug("Enter thread_safe_start_observing...")

        with pexpect.spawn(
            self._tool_name, timeout=timeout, encoding="utf-8"
        ) as child:
            try:
                events = []
                start_time = time.time()

                child.expect(self._expected_pattern)
                child.sendline("a")  # a means observe the event
                logging.info("Start observing events...")
                func(**fn_kwargs)

                while time.time() - start_time < timeout:
                    try:
                        # Read a line from the child process output
                        line = child.readline().strip()
                        if line:
                            events.append(line)
                    except (pexpect.EOF, pexpect.TIMEOUT):
                        break

                return "\n".join(events)
            except Exception as e:
                logging.error("Unexpected error occurred: {}".format(str(e)))
                raise
            finally:
                # Ensure the process is terminated properly after the context
                # ends
                child.terminate()

    def show_help(self):
        """Show help message
        Example Output:
            getchar=h
            1) enable hdmi      2) disable hdmi
            3) get device info  4) check cable
            5) get video info   6) check video locked
            7) get audio info   8) check audio locked
            a) start observing  b) stop observing
            h) help             q) quit
        """
        return self._run_expect(action="h")


def get_actions_name_from_hdmi_rx_tool_runner_class():
    """
    Get names of all methods in the HdmiRxToolRunner class that not belong
    to private method.

    Returns:
        list: List of method names.
    """
    prefix = "_"
    return [
        method[0]
        for method in inspect.getmembers(
            HdmiRxToolRunner, predicate=inspect.isfunction
        )
        if not method[0].startswith(prefix)
    ]


def arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=get_actions_name_from_hdmi_rx_tool_runner_class(),
        help="Supported actions from MTK HDMI RX Tool",
    )
    return parser


def main():
    if os.geteuid() != 0:
        raise PermissionError("You have to run this command with sudo")

    parser = arg_parser()
    args = parser.parse_args()

    print(getattr(HdmiRxToolRunner(), "{}".format(args.action))())


if __name__ == "__main__":
    raise SystemExit(main())
