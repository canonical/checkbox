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
"""Hardware-free tests for the Genio ioctl backend.

The struct-size and ioctl-number assertions pin the ABI; the mapper
tests read a hand-filled ctypes struct and check the decoded field --
each with a second value so a hard-coded return would fail.
"""

import ctypes
import unittest
from unittest.mock import patch

from hdmirx_utils import Colorspace
from hdmirx_genio import (
    GenioIoctlBackend,
    HDMIRX_AUD_INFO,
    HDMIRX_DEV_INFO,
    HDMIRX_VID_PARA,
    _decode_word_len_bits,
)


class TestStructSizes(unittest.TestCase):
    def test_abi_struct_sizes(self):
        self.assertEqual(ctypes.sizeof(HDMIRX_VID_PARA), 40)
        self.assertEqual(ctypes.sizeof(HDMIRX_DEV_INFO), 12)
        self.assertEqual(ctypes.sizeof(HDMIRX_AUD_INFO), 28)


class TestIoctlNumbers(unittest.TestCase):
    def setUp(self):
        self.backend = GenioIoctlBackend()

    def test_request_numbers(self):
        self.assertEqual(self.backend._request("vid_info"), 0xC0284801)
        self.assertEqual(self.backend._request("aud_info"), 0xC01C4802)
        self.assertEqual(self.backend._request("enable"), 0x40044803)
        self.assertEqual(self.backend._request("dev_info"), 0xC00C4804)

    def test_abi_selfcheck_passes(self):
        self.assertIsNone(self.backend.abi_selfcheck())

    def test_identity(self):
        self.assertEqual(self.backend.name, "genio")
        self.assertEqual(self.backend.MODULE_NAME, "mtk_hdmirx")
        self.assertEqual(self.backend.DEVICE_PATH, "/dev/hdmirx")


class TestVideoMapper(unittest.TestCase):
    def setUp(self):
        self.backend = GenioIoctlBackend()

    def _raw(
        self, hactive=1920, vactive=1080, frame_rate=60, cs=0, dp=1, is_pscan=1
    ):
        raw = HDMIRX_VID_PARA()
        raw.hactive = hactive
        raw.vactive = vactive
        raw.frame_rate = frame_rate
        raw.cs = cs
        raw.dp = dp
        raw.is_pscan = is_pscan
        return raw

    def test_decodes_1080p60(self):
        info = self.backend._map_video_info(self._raw())
        self.assertEqual(info.hactive, 1920)
        self.assertEqual(info.vactive, 1080)
        self.assertEqual(info.frame_rate, 60)
        self.assertEqual(info.colorspace, Colorspace.RGB)
        self.assertEqual(info.bit_depth, 10)
        self.assertFalse(info.interlaced)

    def test_fields_are_read_not_hardcoded(self):
        info = self.backend._map_video_info(
            self._raw(hactive=1280, vactive=720, frame_rate=50, cs=2)
        )
        self.assertEqual(info.hactive, 1280)
        self.assertEqual(info.vactive, 720)
        self.assertEqual(info.frame_rate, 50)
        self.assertEqual(info.colorspace, Colorspace.YUV422)

    def test_interlaced_flag(self):
        info = self.backend._map_video_info(self._raw(is_pscan=0))
        self.assertTrue(info.interlaced)


class TestDeviceMapper(unittest.TestCase):
    def setUp(self):
        self.backend = GenioIoctlBackend()

    def _raw(self, hpd=1, hdmirx5v=1, vid=1, aud=1, hdcp=2):
        raw = HDMIRX_DEV_INFO()
        raw.hpd = hpd
        raw.hdmirx5v = hdmirx5v
        raw.vid_locked = vid
        raw.aud_locked = aud
        raw.hdcp_version = hdcp
        return raw

    def test_connected_when_hpd_and_5v(self):
        info = self.backend._map_device_info(self._raw())
        self.assertTrue(info.connected)
        self.assertTrue(info.power_5v)
        self.assertTrue(info.hpd)
        self.assertEqual(info.hdcp_version, 2)

    def test_not_connected_without_5v(self):
        info = self.backend._map_device_info(self._raw(hdmirx5v=0))
        self.assertFalse(info.connected)
        self.assertFalse(info.power_5v)


class TestAudioMapper(unittest.TestCase):
    def setUp(self):
        self.backend = GenioIoctlBackend()

    def _raw(self, sample_freq=0x2, channel_count=1, word_len=0x0B):
        raw = HDMIRX_AUD_INFO()
        raw.caps.SampleFreq = sample_freq
        raw.caps.AudInf.info.AudioChannelCount = channel_count
        raw.caps.AudChStat.WordLen = word_len
        return raw

    def test_decodes_24bit_2ch_48khz(self):
        info = self.backend._map_audio_info(self._raw())
        self.assertEqual(info.bit_depth, 24)
        self.assertEqual(info.channels, 2)
        self.assertEqual(info.sample_freq_khz, 48.0)

    def test_fields_are_read_not_hardcoded(self):
        info = self.backend._map_audio_info(
            self._raw(sample_freq=0x3, channel_count=5, word_len=0x02)
        )
        self.assertEqual(info.channels, 6)
        self.assertEqual(info.sample_freq_khz, 32.0)
        self.assertEqual(info.bit_depth, 16)

    def test_unknown_sample_freq_is_zero(self):
        info = self.backend._map_audio_info(self._raw(sample_freq=0x7))
        self.assertEqual(info.sample_freq_khz, 0.0)


class TestWordLenDecode(unittest.TestCase):
    def test_known_and_unknown(self):
        self.assertEqual(_decode_word_len_bits(0x0B), 24)
        self.assertEqual(_decode_word_len_bits(0x02), 16)
        self.assertEqual(_decode_word_len_bits(0x00), 0)


class TestGetVideoInfoIntegration(unittest.TestCase):
    """Exercise the base-class _ioctl path with a mocked device."""

    def test_get_video_info_reads_through_ioctl(self):
        backend = GenioIoctlBackend()

        def fake_ioctl(fd, request, arg):
            self.assertEqual(request, 0xC0284801)
            arg.hactive = 3840
            arg.vactive = 2160
            arg.frame_rate = 30
            arg.cs = 1
            arg.dp = 0
            arg.is_pscan = 1

        with patch("hdmirx_utils.os.open", return_value=9), patch(
            "hdmirx_utils.os.close"
        ), patch("hdmirx_utils.fcntl.ioctl", side_effect=fake_ioctl):
            info = backend.get_video_info()
        self.assertEqual(info.hactive, 3840)
        self.assertEqual(info.vactive, 2160)
        self.assertEqual(info.frame_rate, 30)
        self.assertEqual(info.colorspace, Colorspace.YUV444)
        self.assertEqual(info.bit_depth, 8)


if __name__ == "__main__":
    unittest.main()
