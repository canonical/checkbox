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
"""Hardware-free tests for the hdmirx_tool CLI orchestration.

The backend is faked, so these check the CLI contract: exit status 0
on pass / 1 on fail, the disable-then-enable poll loop, and JSON shape.
"""

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import hdmirx_tool
from hdmirx_tool import NoBackendError, detect
from hdmirx_utils import (
    AbiMismatch,
    AudioInfo,
    DeviceInfo,
    VideoInfo,
    expected_event_set,
)


class FakeBackend(object):
    name = "fake"

    def __init__(
        self, module=True, device=None, video=None, audio=None, events=None
    ):
        self._module = module
        self._device = device
        self._video = video
        self._audio = audio
        self._events = events if events is not None else set()
        self.enabled = None

    def is_available(self):
        return True

    def module_present(self):
        return self._module

    def get_device_info(self):
        return self._device

    def get_video_info(self):
        return self._video

    def get_audio_info(self):
        return self._audio

    def set_enabled(self, on):
        self.enabled = on

    def wait_for_events(self, kind, timeout):
        return self._events


class FlipBackend(FakeBackend):
    """get_device_info tracks the last set_enabled call."""

    def __init__(self):
        super(FlipBackend, self).__init__()
        self.enabled = True

    def get_device_info(self):
        state = bool(self.enabled)
        return DeviceInfo(
            connected=state,
            power_5v=state,
            hpd=state,
            video_locked=state,
            audio_locked=state,
            hdcp_version=0,
        )


def _connected(state=True):
    return DeviceInfo(
        connected=state,
        power_5v=state,
        hpd=state,
        video_locked=state,
        audio_locked=state,
        hdcp_version=1,
    )


def _run(argv, backend):
    buf = io.StringIO()
    with patch("hdmirx_tool.detect", return_value=backend), redirect_stdout(
        buf
    ):
        rc = hdmirx_tool.main(argv)
    return rc, buf.getvalue()


class TestDetect(unittest.TestCase):
    def test_first_available_wins(self):
        class Avail(object):
            name = "avail"

            def is_available(self):
                return True

        class Unavail(object):
            name = "unavail"

            def is_available(self):
                return False

        with patch("hdmirx_tool.BACKENDS", [Unavail, Avail]):
            self.assertIsInstance(detect(), Avail)

    def test_preferred_forces_backend(self):
        class Avail(object):
            name = "avail"

            def is_available(self):
                return False

        with patch("hdmirx_tool.BACKENDS", [Avail]):
            self.assertIsInstance(detect("avail"), Avail)

    def test_unknown_preferred_raises(self):
        class Avail(object):
            name = "avail"

            def is_available(self):
                return True

        with patch("hdmirx_tool.BACKENDS", [Avail]):
            with self.assertRaises(NoBackendError):
                detect("nope")

    def test_none_available_raises(self):
        class Unavail(object):
            name = "unavail"

            def is_available(self):
                return False

        with patch("hdmirx_tool.BACKENDS", [Unavail]):
            with self.assertRaises(NoBackendError):
                detect()


class TestModuleCheck(unittest.TestCase):
    def test_pass(self):
        rc, _ = _run(["module-check"], FakeBackend(module=True))
        self.assertEqual(rc, 0)

    def test_fail(self):
        rc, out = _run(["module-check"], FakeBackend(module=False))
        self.assertEqual(rc, 1)
        self.assertIn("FAIL", out)


class TestCable(unittest.TestCase):
    def test_connected_passes(self):
        rc, _ = _run(["cable"], FakeBackend(device=_connected(True)))
        self.assertEqual(rc, 0)

    def test_disconnected_fails(self):
        rc, _ = _run(["cable"], FakeBackend(device=_connected(False)))
        self.assertEqual(rc, 1)


class TestVideoInfo(unittest.TestCase):
    def _backend(self, h=1920, v=1080, r=60):
        return FakeBackend(video=VideoInfo(hactive=h, vactive=v, frame_rate=r))

    def test_match_passes(self):
        rc, _ = _run(
            ["video-info", "-rh", "1920", "-rv", "1080", "-rr", "60"],
            self._backend(),
        )
        self.assertEqual(rc, 0)

    def test_mismatch_fails(self):
        rc, _ = _run(
            ["video-info", "-rh", "1920", "-rv", "1080", "-rr", "60"],
            self._backend(h=1280),
        )
        self.assertEqual(rc, 1)

    def test_no_expectation_just_reports(self):
        rc, _ = _run(["video-info"], self._backend())
        self.assertEqual(rc, 0)


class TestAudioInfo(unittest.TestCase):
    def _backend(self, b=24, c=2, f=48.0):
        return FakeBackend(
            audio=AudioInfo(bit_depth=b, channels=c, sample_freq_khz=f)
        )

    def test_match_passes(self):
        rc, _ = _run(
            ["audio-info", "-ab", "24", "-ac", "2", "-asf", "48.0"],
            self._backend(),
        )
        self.assertEqual(rc, 0)

    def test_mismatch_fails(self):
        rc, _ = _run(
            ["audio-info", "-ab", "24", "-ac", "2", "-asf", "48.0"],
            self._backend(c=8),
        )
        self.assertEqual(rc, 1)


class TestWaitEvent(unittest.TestCase):
    def test_full_set_passes(self):
        rc, _ = _run(
            ["wait-event", "plug"],
            FakeBackend(events=expected_event_set("plug")),
        )
        self.assertEqual(rc, 0)

    def test_partial_set_fails(self):
        rc, out = _run(
            ["wait-event", "plug"],
            FakeBackend(events=set(list(expected_event_set("plug"))[:1])),
        )
        self.assertEqual(rc, 1)
        self.assertIn("missing", out)


class TestDisableThenEnable(unittest.TestCase):
    def test_flip_passes_and_reenables(self):
        backend = FlipBackend()
        rc, _ = _run(["disable-then-enable"], backend)
        self.assertEqual(rc, 0)
        self.assertTrue(backend.enabled)


class TestAbiSelfcheck(unittest.TestCase):
    def test_backend_without_selfcheck_skips(self):
        rc, _ = _run(["abi-selfcheck"], FakeBackend())
        self.assertEqual(rc, 0)

    def test_selfcheck_failure_fails(self):
        backend = FakeBackend()

        def boom():
            raise AbiMismatch("size drift")

        backend.abi_selfcheck = boom
        rc, out = _run(["abi-selfcheck"], backend)
        self.assertEqual(rc, 1)
        self.assertIn("size drift", out)


class TestErrorHandling(unittest.TestCase):
    def test_not_implemented_is_reported(self):
        backend = FakeBackend()

        def raise_ni():
            raise NotImplementedError("no audio here")

        backend.get_audio_info = raise_ni
        rc, out = _run(
            ["audio-info", "-ab", "24", "-ac", "2", "-asf", "48.0"], backend
        )
        self.assertEqual(rc, 1)
        self.assertIn("not supported", out)

    def test_no_backend_exits_nonzero(self):
        buf = io.StringIO()
        with patch(
            "hdmirx_tool.detect", side_effect=NoBackendError("none")
        ), redirect_stdout(buf):
            rc = hdmirx_tool.main(["module-check"])
        self.assertEqual(rc, 1)


class TestJsonOutput(unittest.TestCase):
    def test_json_shape(self):
        rc, out = _run(["--json", "module-check"], FakeBackend(module=True))
        payload = json.loads(out)
        self.assertEqual(rc, 0)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["command"], "module-check")
        self.assertEqual(payload["backend"], "fake")
        self.assertEqual(payload["reasons"], [])


if __name__ == "__main__":
    unittest.main()
