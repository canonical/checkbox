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

    def _run_expect(self, action: str = "h", timeout: int = 3):
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
        """
        return self._run_expect(action="1")

    def disable_hdmi(self):
        """Disable HDMI RX Feature
        """
        return self._run_expect(action="2")

    def get_device_info(self):
        """Get device information through HDMI RX
        """
        return self._run_expect(action="3")

    def check_cable(self):
        """Get the connection state of HDMI RX
        """
        return self._run_expect(action="4")

    def get_video_info(self):
        """Get video information through HDMI RX
        """
        return self._run_expect(action="5")

    def check_video_locked(self):
        """Check the lock state of video through HDMI RX
        """
        return self._run_expect(action="6")

    def get_audio_info(self):
        """Get audio information through HDMI RX
        """
        return self._run_expect(action="7")

    def check_audio_locked(self):
        """Check the lock state of audio through HDMI RX
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
