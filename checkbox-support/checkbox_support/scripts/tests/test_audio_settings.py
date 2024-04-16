#
# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import re
import unittest

from checkbox_support.scripts.audio_settings import (
    _guess_hdmi_profile,
    volume_pattern,
)
from checkbox_support.parsers.tests.test_pactl import PactlDataMixIn


class SetProfileTest(unittest.TestCase, PactlDataMixIn):

    def test_desktop_precise_xps1340(self):
        """
        Precise system with a Nvidia chipset.
        HDMI is present in the card ports list but not shown in the sinks list.
        The port availability cannot be determined, in that case the expected
        value is the first stereo profile listed in the identified port.
        Meaningful lines:

        Card #0
        [...]
            Ports:
        [...]
                hdmi-output-0: HDMI / DisplayPort (priority 5900)
                    Part of profile(s): output:hdmi-stereo, output:hdmi-stereo+input:analog-stereo, output:hdmi-surround, output:hdmi-surround+input:analog-stereo
        """
        self.assertEqual(
            _guess_hdmi_profile(self.get_text("desktop-precise-xps1340")),
            ("0", "output:hdmi-stereo"),
        )

    def test_desktop_precise_radeon_not_available(self):
        """
        Home-made system running Precise with a Radeon card.
        HDMI is present in the card ports list and shown in the sinks list.
        But the port is "not available", both card and profile should be set
        to None.
        Meaningful lines:

        Sink #0
        [...]
            Ports:
                hdmi-output-0: HDMI / DisplayPort (priority: 5900, not available)
        [...]
        Card #0
        [...]
            Ports:
                hdmi-output-0: HDMI / DisplayPort (priority 5900)
                    Part of profile(s): output:hdmi-stereo
        """
        self.assertEqual(
            _guess_hdmi_profile(self.get_text("desktop-precise-radeon")),
            (None, None),
        )

    def test_desktop_precise_radeon_available(self):
        """
        Home-made system running Precise with a Radeon card.
        HDMI is present in the card ports list, shown in the sinks list and
        marked as "available", in that case the expected value is the first
        stereo profile listed in the identified port.
        Meaningful lines:

        Sink #0
        [...]
            Ports:
                hdmi-output-0: HDMI / DisplayPort (priority: 5900, available)
        [...]
        Card #0
        [...]
            Ports:
                hdmi-output-0: HDMI / DisplayPort (priority 5900)
                    Part of profile(s): output:hdmi-stereo
        """
        self.assertEqual(
            _guess_hdmi_profile(
                self.get_text("desktop-precise-radeon-hdmi-available")
            ),
            ("0", "output:hdmi-stereo"),
        )

    def test_desktop_raring_t430s_not_available(self):
        """
        Raring system with a Mini-DisplayPort.
        DisplayPort is present in the card ports list but marked as
        "not available". Thus both card and profile should be set
        to None.
        Meaningful lines:

        Card #2
        [...]
            Ports:
        [...]
                hdmi-output-0: HDMI / DisplayPort (priority: 5900, latency offset: 0 usec, not available)
                    Properties:
                        device.icon_name = "video-display"
                    Part of profile(s): output:hdmi-stereo, output:hdmi-stereo+input:analog-stereo
                hdmi-output-1: HDMI / DisplayPort 2 (priority: 5800, latency offset: 0 usec, not available)
                    Properties:
                        device.icon_name = "video-display"
                    Part of profile(s): output:hdmi-stereo-extra1, output:hdmi-stereo-extra1+input:analog-stereo, output:hdmi-surround-extra1, output:hdmi-surround-extra1+input:analog-stereo
                hdmi-output-2: HDMI / DisplayPort 3 (priority: 5700, latency offset: 0 usec, not available)
                    Properties:
                        device.icon_name = "video-display"
                    Part of profile(s): output:hdmi-stereo-extra2, output:hdmi-stereo-extra2+input:analog-stereo, output:hdmi-surround-extra2, output:hdmi-surround-extra2+input:analog-stereo
        """
        self.assertEqual(
            _guess_hdmi_profile(self.get_text("desktop-raring-t430s")),
            (None, None),
        )

    def test_desktop_raring_t430s_available(self):
        """
        Raring system with a Mini-DisplayPort.
        DisplayPort is present in the card ports list and marked as
        "available", in that case the expected value is the first stereo
        profile listed in the identified port.
        Meaningful lines:

        Card #2
        [...]
            Ports:
        [...]
                hdmi-output-0: HDMI / DisplayPort (priority: 5900, latency offset: 0 usec, available)
                    Properties:
                        device.icon_name = "video-display"
                    Part of profile(s): output:hdmi-stereo, output:hdmi-stereo+input:analog-stereo
                hdmi-output-1: HDMI / DisplayPort 2 (priority: 5800, latency offset: 0 usec, not available)
                    Properties:
                        device.icon_name = "video-display"
                    Part of profile(s): output:hdmi-stereo-extra1, output:hdmi-stereo-extra1+input:analog-stereo, output:hdmi-surround-extra1, output:hdmi-surround-extra1+input:analog-stereo
                hdmi-output-2: HDMI / DisplayPort 3 (priority: 5700, latency offset: 0 usec, not available)
                    Properties:
                        device.icon_name = "video-display"
                    Part of profile(s): output:hdmi-stereo-extra2, output:hdmi-stereo-extra2+input:analog-stereo, output:hdmi-surround-extra2, output:hdmi-surround-extra2+input:analog-stereo
        """
        self.assertEqual(
            _guess_hdmi_profile(
                self.get_text("desktop-raring-t430s-dp-available")
            ),
            ("2", "output:hdmi-stereo"),
        )

    def test_desktop_bionic_x13(self):
        """
        Bionic system with a Intel UHD Graphics chipset, it's DMIC system.
        HDMI1, HDMI2 and HDMI3 are present in the card ports list, HDMI2 shown in the sinks list.
        DMIC don't use "HDMI / DisplayPort " as keyword, now we use "HDMI" and "DP" keywords to find output port.
        And in profile, there are not "hdmi-stereo" keyword any more, now we use "Hdmi".
            Ports:
        [...]
                [Out] HDMI2: HDMI2/DP2 Output (priority: 400, latency offset: 0 usec, available)
                    Part of profile(s): Hdmi2
        """
        self.assertEqual(
            _guess_hdmi_profile(self.get_text("desktop-bionic-x13")),
            ("0", "Hdmi2"),
        )

    def test_displayport_monitor_hifi(self):
        """
        Displayport profiles can be exposed using Hifi
        """
        self.assertEqual(
            _guess_hdmi_profile(self.get_text("displayport-monitor-hifi")),
            ("0", "HiFi"),
        )


class RegexTest(unittest.TestCase):

    def test_volume_regex_trusty(self):
        """Testing pactl 4.0 output"""
        pactl_volume = "    Volume: 0:  47% 1:  47%"
        volume_regex = re.compile(volume_pattern % "0", re.DOTALL)
        volume = int(volume_regex.search(pactl_volume).group(1).strip())
        self.assertEqual(volume, 47)

    def test_volume_regex_xenial(self):
        """Testing pactl 8.0 output"""
        # See lp:1595380 for more info
        pactl_volume = "    Volume: front-left: 65536 / 100% / 0.00 dB,   front-right: 65536 / 100% / 0.00 dB"
        volume_regex = re.compile(volume_pattern % "front-left", re.DOTALL)
        volume = int(volume_regex.search(pactl_volume).group(1).strip())
        self.assertEqual(volume, 100)
