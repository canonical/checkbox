#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
pulse_active_port_change.py
========================

This script checks if the active port on either sinks (speakers or headphones)
or sources (microphones, webcams) is changed after an appropriate device is
plugged into the DUT. The script is fully automatic and either times out after
30 seconds or returns as soon as the change is detected.

The script monitors pulse audio events with `pactl subscribe`. Any changes to
sinks (or sources, depending on the mode) are treated as a possible match. A
match is verified by running `pactl list sinks` (or `pactl list sources`) and
constructing a set of tuples (sink-source-name, sink-source-active-port,
sink-source-availability). Any change to the computed set, as compared to the
initially computed set, is considered a match.

Due to the algorithm used, it will also detect things like USB headsets, HDMI
monitors/speakers, webcams, etc.

The script depends on:
    python3-checkbox-support
Which depends on:
    python3-pyparsing
"""
import argparse
import os
import pty
import signal
import subprocess

from checkbox_support.parsers.pactl import parse_pactl_output
from checkbox_support.snap_utils.system import in_classic_snap


class AudioPlugDetection:

    def __init__(self, timeout, mode):
        # store parameters
        self.timeout = timeout
        self.mode = mode
        # get the un-localized environment
        env = dict(os.environb)
        env[b"LANG"] = b""
        env[b"LANGUAGE"] = b""
        env[b"LC_ALL"] = b"C.UTF-8"
        if in_classic_snap():
            prp = "/run/user/{}/snap.{}/../pulse".format(
                os.geteuid(), os.getenv("SNAP_NAME")
            )
            env[b"PULSE_RUNTIME_PATH"] = prp
        self.unlocalized_env = env
        # set SIGALRM handler
        signal.signal(signal.SIGALRM, self.on_timeout)

    def get_sound_config(self):
        text = subprocess.check_output(
            ["pactl", "list", self.mode],  # either 'sources' or 'sinks'
            env=self.unlocalized_env,
            universal_newlines=True,
        )
        doc = parse_pactl_output(text)
        cfg = set()
        for record in doc.record_list:
            active_port = None
            port_availability = None
            # We go through the attribute list once to try to find
            # an active port
            for attr in record.attribute_list:
                if attr.name == "Active Port":
                    active_port = attr.value
            # If there is one, we retrieve its availability flag
            if active_port:
                for attr in record.attribute_list:
                    if attr.name == "Ports":
                        for port in attr.value:
                            if port.name == active_port:
                                port_availability = port.availability
                cfg.add((record.name, active_port, port_availability))
        return cfg

    def on_timeout(self, signum, frame):
        print("Time is up")
        raise SystemExit(1)

    @classmethod
    def main(cls):
        parser = argparse.ArgumentParser(
            description=__doc__.split("")[0],
            epilog=__doc__.split("")[1],
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.add_argument(
            "mode",
            choices=["sinks", "sources"],
            help="Monitor either sinks or sources",
        )
        parser.add_argument(
            "-t",
            "--timeout",
            type=int,
            default=30,
            help="Timeout after which the script fails",
        )
        ns = parser.parse_args()
        return cls(ns.timeout, ns.mode).run()

    def run(self):
        found = False
        if self.mode == "sinks":
            look_for = "Event 'change' on sink #"
            look_for2 = "Event 'change' on server #"
        elif self.mode == "sources":
            look_for = "Event 'change' on source #"
            look_for2 = "Event 'change' on server #"
        else:
            assert False
        # Get the initial / baseline configuration
        initial_cfg = self.get_sound_config()
        print("Starting with config: {}".format(initial_cfg))
        print(
            "You have {} seconds to plug the item in".format(self.timeout),
            flush=True,
        )
        # Start the timer
        signal.alarm(self.timeout)
        # run subscribe in a pty as it doesn't fflush() after every event
        pid, master_fd = pty.fork()
        if pid == 0:
            os.execlpe("pactl", "pactl", "subscribe", self.unlocalized_env)
        else:
            child_stream = os.fdopen(master_fd, "rt", encoding="UTF-8")
            try:
                for line in child_stream:
                    if line.startswith(look_for) or line.startswith(look_for2):
                        new_cfg = self.get_sound_config()
                        print("Now using config: {}".format(new_cfg))
                        if new_cfg != initial_cfg:
                            print("It seems to work!")
                            found = True
                            break
            except KeyboardInterrupt:
                pass
            finally:
                os.kill(pid, signal.SIGTERM)
                os.close(master_fd)
        return 0 if found else 1


if __name__ == "__main__":
    raise SystemExit(AudioPlugDetection.main())
