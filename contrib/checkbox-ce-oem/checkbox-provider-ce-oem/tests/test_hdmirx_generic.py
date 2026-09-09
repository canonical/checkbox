#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Isaac Yang <isaac.yang@canonical.com>
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.
"""Hardware-free tests for the mainline V4L2 HDMI RX backend."""

import ctypes
import unittest
from unittest.mock import mock_open, patch

import hdmirx_generic as G  # noqa: N812 (short test alias)
from hdmirx_generic import (
    V4L2Backend,
    _frame_rate_hz,
    v4l2_bt_timings,
    v4l2_dv_timings,
)


class TestStructSizes(unittest.TestCase):
    def test_uapi_struct_sizes(self):
        self.assertEqual(ctypes.sizeof(v4l2_bt_timings), 124)
        self.assertEqual(ctypes.sizeof(v4l2_dv_timings), 132)


class TestFrameRate(unittest.TestCase):
    def _bt_1080p60(self):
        bt = v4l2_bt_timings()
        bt.width = 1920
        bt.height = 1080
        bt.hfrontporch, bt.hsync, bt.hbackporch = 88, 44, 148
        bt.vfrontporch, bt.vsync, bt.vbackporch = 4, 5, 36
        bt.pixelclock = 148500000
        return bt

    def test_computes_60hz(self):
        # htotal=2200, vtotal=1125 -> 148.5MHz / 2475000 = 60
        self.assertEqual(_frame_rate_hz(self._bt_1080p60()), 60)

    def test_zero_totals_do_not_divide_by_zero(self):
        self.assertEqual(_frame_rate_hz(v4l2_bt_timings()), 0)

    def test_interlaced_adds_field_blanking(self):
        bt = self._bt_1080p60()
        bt.interlaced = 1
        bt.il_vfrontporch, bt.il_vsync, bt.il_vbackporch = 2, 5, 15
        # vtotal grows by 22 -> 1147; 148.5MHz / (2200*1147) rounds to 59.
        self.assertEqual(_frame_rate_hz(bt), 59)


class TestGetVideoInfo(unittest.TestCase):
    def test_reads_dv_timings(self):
        backend = V4L2Backend(device_path="/dev/video0")

        def fake_ioctl(fd, request, timings):
            timings.u.bt.width = 1920
            timings.u.bt.height = 1080
            timings.u.bt.hfrontporch = 88
            timings.u.bt.hsync = 44
            timings.u.bt.hbackporch = 148
            timings.u.bt.vfrontporch = 4
            timings.u.bt.vsync = 5
            timings.u.bt.vbackporch = 36
            timings.u.bt.pixelclock = 148500000

        with patch("hdmirx_generic.os.open", return_value=5), patch(
            "hdmirx_generic.os.close"
        ), patch("hdmirx_generic.fcntl.ioctl", side_effect=fake_ioctl):
            info = backend.get_video_info()
        self.assertEqual(info.hactive, 1920)
        self.assertEqual(info.vactive, 1080)
        self.assertEqual(info.frame_rate, 60)
        self.assertFalse(info.interlaced)


class TestNodeDiscovery(unittest.TestCase):
    def test_matches_hdmirx_name(self):
        with patch(
            "hdmirx_generic.glob.glob",
            return_value=["/sys/class/video4linux/video3/name"],
        ), patch(
            "hdmirx_generic.open",
            mock_open(read_data="snps-hdmirx\n"),
            create=True,
        ), patch(
            "hdmirx_generic.os.path.exists", return_value=True
        ):
            self.assertEqual(G._find_hdmirx_video_node(), "/dev/video3")

    def test_ignores_non_hdmirx_name(self):
        with patch(
            "hdmirx_generic.glob.glob",
            return_value=["/sys/class/video4linux/video0/name"],
        ), patch(
            "hdmirx_generic.open",
            mock_open(read_data="some-camera\n"),
            create=True,
        ), patch(
            "hdmirx_generic.os.path.exists", return_value=True
        ):
            self.assertIsNone(G._find_hdmirx_video_node())


class TestUnsupportedOperations(unittest.TestCase):
    def setUp(self):
        self.backend = V4L2Backend(device_path="/dev/video0")

    def test_audio_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.backend.get_audio_info()

    def test_enable_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.backend.set_enabled(True)

    def test_events_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.backend.wait_for_events("plug", 5)


if __name__ == "__main__":
    unittest.main()
