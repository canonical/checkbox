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
"""Hardware-free tests for hdmirx_utils (the platform-independent core).

Every test is designed to be able to fail: the ioctl-number and
verify_* cases assert both the pass and the mismatch paths, so a
hard-coded implementation would be caught.
"""

import ctypes
import unittest
from unittest.mock import patch

import hdmirx_utils as U  # noqa: N812 (short test alias)
from hdmirx_utils import (
    AbiMismatch,
    AudioInfo,
    Event,
    IoctlCharBackend,
    IoctlCmd,
    VideoInfo,
)


class _FakeStruct(ctypes.Structure):
    _fields_ = [("x", ctypes.c_uint32)]  # sizeof == 4


class _FakeBackend(IoctlCharBackend):
    name = "fake"
    MAGIC = "H"
    DEVICE_PATH = "/dev/fake"
    MODULE_NAME = "fake_mod"
    UEVENT_KEY = "SWITCH_NOTIFY"
    DEVPATH_FILTER = "fake"
    EVENT_MAP = {0: Event.PWR_5V_CHANGE, 11: Event.PLUG_IN}
    COMMANDS = {
        "vid_info": IoctlCmd(1, "wr", _FakeStruct),
        "aud_info": IoctlCmd(2, "wr", _FakeStruct),
        "enable": IoctlCmd(3, "w", ctypes.c_uint),
        "dev_info": IoctlCmd(4, "wr", _FakeStruct),
    }
    EXPECTED_SIZES = {"vid_info": 4, "dev_info": 4, "aud_info": 4}

    def _map_device_info(self, raw):
        return raw

    def _map_video_info(self, raw):
        return raw

    def _map_audio_info(self, raw):
        return raw


class TestIocNumbers(unittest.TestCase):
    def test_iowr_matches_asm_generic(self):
        # dir=3<<30 | size=4<<16 | type='H'<<8 | nr=1
        self.assertEqual(U._IOWR("H", 1, 4), 0xC0044801)

    def test_iow_and_ior(self):
        self.assertEqual(U._IOW("H", 3, 4), 0x40044803)
        self.assertEqual(U._IOR("V", 63, 132), 0x8084563F)

    def test_direction_bits_differ(self):
        # A read/write command must not encode the same as write-only.
        self.assertNotEqual(U._IOWR("H", 1, 4), U._IOW("H", 1, 4))


class TestRequestEncoding(unittest.TestCase):
    def setUp(self):
        self.backend = _FakeBackend()

    def test_request_uses_command_direction_and_size(self):
        self.assertEqual(self.backend._request("vid_info"), 0xC0044801)
        self.assertEqual(self.backend._request("enable"), 0x40044803)

    def test_abi_selfcheck_passes_when_sizes_match(self):
        self.assertIsNone(self.backend.abi_selfcheck())

    def test_abi_selfcheck_raises_on_size_drift(self):
        self.backend.EXPECTED_SIZES = {"vid_info": 999}
        with self.assertRaises(AbiMismatch):
            self.backend.abi_selfcheck()


class TestBackendPlumbing(unittest.TestCase):
    def setUp(self):
        self.backend = _FakeBackend()

    def test_module_present_checks_sysfs(self):
        with patch("hdmirx_utils.os.path.isdir", return_value=True) as m:
            self.assertTrue(self.backend.module_present())
        m.assert_called_once_with("/sys/module/fake_mod")
        with patch("hdmirx_utils.os.path.isdir", return_value=False):
            self.assertFalse(self.backend.module_present())

    def test_is_available_checks_device_node(self):
        with patch("hdmirx_utils.os.path.exists", return_value=True):
            self.assertTrue(self.backend.is_available())
        with patch("hdmirx_utils.os.path.exists", return_value=False):
            self.assertFalse(self.backend.is_available())

    def test_set_enabled_issues_enable_ioctl(self):
        captured = {}

        def fake_ioctl(fd, request, arg):
            captured["request"] = request
            captured["value"] = arg.value

        with patch("hdmirx_utils.os.open", return_value=7), patch(
            "hdmirx_utils.os.close"
        ), patch("hdmirx_utils.fcntl.ioctl", side_effect=fake_ioctl):
            self.backend.set_enabled(True)
        self.assertEqual(captured["request"], 0x40044803)
        self.assertEqual(captured["value"], 1)

    def test_ioctl_failure_wraps_as_ioctlerror(self):
        with patch("hdmirx_utils.os.open", return_value=7), patch(
            "hdmirx_utils.os.close"
        ), patch("hdmirx_utils.fcntl.ioctl", side_effect=OSError(22, "bad")):
            with self.assertRaises(U.IoctlError):
                self.backend.get_video_info()


class _FakePoll:
    def __init__(self, ready):
        self._ready = list(ready)

    def register(self, *args):
        pass

    def poll(self, timeout_ms):
        return self._ready.pop(0) if self._ready else []


class _FakeSocket:
    def __init__(self, datagrams):
        self._datagrams = list(datagrams)

    def bind(self, addr):
        pass

    def recv(self, size):
        return self._datagrams.pop(0) if self._datagrams else b""

    def close(self):
        pass


def _dgram(code, devpath="/devices/platform/soc/hdmirx"):
    return b"\0".join(
        [
            b"change@" + devpath.encode(),
            b"SWITCH_NOTIFY=" + str(code).encode(),
            b"DEVPATH=" + devpath.encode(),
        ]
    )


class TestUeventWait(unittest.TestCase):
    EVENT_MAP = {
        0: Event.PWR_5V_CHANGE,
        1: Event.TIMING_LOCK,
        3: Event.AUD_LOCK,
        11: Event.PLUG_IN,
    }

    def _run(self, datagrams, ready, devpath_filter="hdmirx"):
        sock = _FakeSocket(datagrams)
        poll = _FakePoll(ready)
        with patch("hdmirx_utils.socket.socket", return_value=sock), patch(
            "hdmirx_utils.select.poll", return_value=poll
        ), patch("hdmirx_utils.time.monotonic", return_value=0.0):
            return U.uevent_wait(
                "SWITCH_NOTIFY",
                self.EVENT_MAP,
                5.0,
                devpath_filter=devpath_filter,
            )

    def test_collects_plug_burst(self):
        got = self._run(
            [_dgram(0), _dgram(11), _dgram(1), _dgram(3)],
            ready=[[1], [1], [1], [1], []],
        )
        self.assertEqual(
            got,
            {
                Event.PWR_5V_CHANGE,
                Event.PLUG_IN,
                Event.TIMING_LOCK,
                Event.AUD_LOCK,
            },
        )

    def test_timeout_returns_empty(self):
        self.assertEqual(self._run([], ready=[[]]), set())

    def test_devpath_filter_rejects_other_subsystem(self):
        got = self._run(
            [_dgram(11, devpath="/devices/platform/other")], ready=[[1], []]
        )
        self.assertEqual(got, set())

    def test_unknown_code_is_ignored(self):
        got = self._run([_dgram(99)], ready=[[1], []])
        self.assertEqual(got, set())


class TestDecodeEvent(unittest.TestCase):
    def test_known_code(self):
        self.assertEqual(
            U._decode_event(b"11", {11: Event.PLUG_IN}), Event.PLUG_IN
        )

    def test_unknown_and_garbage(self):
        self.assertIsNone(U._decode_event(b"99", {}))
        self.assertIsNone(U._decode_event(b"xx", {}))


class TestExpectedEventSet(unittest.TestCase):
    def test_plug_and_unplug_sets(self):
        self.assertEqual(
            U.expected_event_set("plug"),
            {
                Event.PWR_5V_CHANGE,
                Event.PLUG_IN,
                Event.TIMING_LOCK,
                Event.AUD_LOCK,
            },
        )
        self.assertEqual(
            U.expected_event_set("unplug"),
            {
                Event.AUD_UNLOCK,
                Event.TIMING_UNLOCK,
                Event.PWR_5V_CHANGE,
                Event.PLUG_OUT,
            },
        )

    def test_zapper_drops_physical_events(self):
        got = U.expected_event_set("plug", with_zapper=True)
        self.assertEqual(got, {Event.TIMING_LOCK, Event.AUD_LOCK})
        self.assertNotIn(Event.PLUG_IN, got)

    def test_invalid_kind(self):
        with self.assertRaises(ValueError):
            U.expected_event_set("nonsense")


class TestVerifyEvents(unittest.TestCase):
    def test_all_present_passes(self):
        self.assertEqual(
            U.verify_events(U.expected_event_set("plug"), "plug"), []
        )

    def test_missing_event_reported(self):
        partial = {Event.PWR_5V_CHANGE, Event.PLUG_IN}
        reasons = U.verify_events(partial, "plug")
        self.assertEqual(len(reasons), 1)
        self.assertIn("HDMI_RX_TIMING_LOCK", reasons[0])
        self.assertIn("HDMI_RX_AUD_LOCK", reasons[0])

    def test_zapper_ignores_physical_events(self):
        # Only lock events are required with a zapper.
        got = {Event.TIMING_LOCK, Event.AUD_LOCK}
        self.assertEqual(U.verify_events(got, "plug", with_zapper=True), [])


class TestVerifyVideo(unittest.TestCase):
    def _info(self, h=1920, v=1080, r=60):
        return VideoInfo(hactive=h, vactive=v, frame_rate=r)

    def test_match_passes(self):
        self.assertEqual(U.verify_video(self._info(), 1920, 1080, 60), [])

    def test_each_field_mismatch_reported(self):
        self.assertEqual(
            len(U.verify_video(self._info(h=1280), 1920, 1080, 60)), 1
        )
        self.assertEqual(
            len(U.verify_video(self._info(v=720), 1920, 1080, 60)), 1
        )
        self.assertEqual(
            len(U.verify_video(self._info(r=30), 1920, 1080, 60)), 1
        )

    def test_string_expectations_are_coerced(self):
        self.assertEqual(
            U.verify_video(self._info(), "1920", "1080", "60"), []
        )


class TestVerifyAudio(unittest.TestCase):
    def _info(self, b=24, c=2, f=48.0):
        return AudioInfo(bit_depth=b, channels=c, sample_freq_khz=f)

    def test_match_passes(self):
        self.assertEqual(U.verify_audio(self._info(), 24, 2, 48.0), [])

    def test_mismatches_reported(self):
        self.assertEqual(len(U.verify_audio(self._info(b=16), 24, 2, 48.0)), 1)
        self.assertEqual(len(U.verify_audio(self._info(c=8), 24, 2, 48.0)), 1)
        self.assertEqual(
            len(U.verify_audio(self._info(f=44.1), 24, 2, 48.0)), 1
        )

    def test_frequency_tolerance(self):
        # Within 0.01 kHz is accepted; outside is not.
        self.assertEqual(U.verify_audio(self._info(f=48.005), 24, 2, 48.0), [])
        self.assertEqual(
            len(U.verify_audio(self._info(f=48.5), 24, 2, 48.0)), 1
        )


if __name__ == "__main__":
    unittest.main()
