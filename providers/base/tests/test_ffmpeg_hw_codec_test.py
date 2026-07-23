#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# Written by:
#   Shane McKee <shane.mckee@canonical.com>
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

import os
import unittest
from unittest.mock import patch, MagicMock

import ffmpeg_hw_codec_test as m


class TestSampleResolution(unittest.TestCase):
    def test_default_samples_root(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(m.samples_root(), m.DEFAULT_SAMPLES_PATH)

    def test_samples_root_env_override(self):
        with patch.dict(os.environ, {"MEDIA_SAMPLES_PATH": "/tmp/x"}):
            self.assertEqual(m.samples_root(), "/tmp/x")

    def test_resolve_relative(self):
        with patch.dict(os.environ, {"MEDIA_SAMPLES_PATH": "/base"}):
            self.assertEqual(
                m.resolve_sample("av1/foo.mkv"), "/base/av1/foo.mkv"
            )

    def test_resolve_absolute_unchanged(self):
        self.assertEqual(m.resolve_sample("/abs/foo.mkv"), "/abs/foo.mkv")


class TestCommandBuilders(unittest.TestCase):
    def test_decode_command(self):
        cmd = m.build_decode_command("in.mkv", "/dev/dri/renderD128", "o.yuv")
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("-hwaccel", cmd)
        self.assertIn("vaapi", cmd)
        self.assertIn("in.mkv", cmd)
        self.assertEqual(cmd[-1], "o.yuv")
        self.assertIn("-vaapi_device", cmd)

    def test_encode_command(self):
        cmd = m.build_encode_command(
            "in.mp4", "/dev/dri/renderD128", "h264_vaapi", "o.mp4"
        )
        self.assertIn("-hwaccel_output_format", cmd)
        self.assertIn("h264_vaapi", cmd)
        self.assertIn("-c:v", cmd)
        self.assertEqual(cmd[-1], "o.mp4")


class TestHwAccelerationUsed(unittest.TestCase):
    def test_matching_profile_and_entrypoint(self):
        trace = "    profile = 7\n    entrypoint = 1\n"
        self.assertTrue(m.hw_acceleration_used(trace, "7", "1"))

    def test_regex_profile_group(self):
        trace = "profile = 20\nentrypoint = 8\n"
        self.assertTrue(m.hw_acceleration_used(trace, "(19|20|21|22)", "8"))

    def test_word_boundary_prevents_partial_match(self):
        # profile 19 must not satisfy an expected profile of "1"
        trace = "profile = 19\nentrypoint = 1\n"
        self.assertFalse(m.hw_acceleration_used(trace, "1", "1"))

    def test_entrypoint_must_follow_profile(self):
        trace = "entrypoint = 1\nprofile = 7\n"
        self.assertFalse(m.hw_acceleration_used(trace, "7", "1"))

    def test_no_match_empty_trace(self):
        self.assertFalse(m.hw_acceleration_used("", "7", "1"))


class TestReadTrace(unittest.TestCase):
    def test_reads_and_concatenates(self):
        import tempfile

        d = tempfile.mkdtemp()
        prefix = os.path.join(d, "libva.trace")
        with open(prefix + ".111", "w") as f:
            f.write("a")
        with open(prefix + ".222", "w") as f:
            f.write("b")
        try:
            text = m.read_trace(prefix)
            self.assertIn("a", text)
            self.assertIn("b", text)
        finally:
            for p in (prefix + ".111", prefix + ".222"):
                os.remove(p)
            os.rmdir(d)

    def test_missing_files_returns_empty(self):
        self.assertEqual(m.read_trace("/nonexistent/libva.trace"), "")


class TestArgParsing(unittest.TestCase):
    def test_encode_requires_output_codec(self):
        with self.assertRaises(SystemExit):
            m.parse_args(
                ["encode", "in.mp4", "--profile", "7", "--entrypoint", "1"]
            )

    def test_decode_ok(self):
        args = m.parse_args(
            ["decode", "in.mkv", "--profile", "32", "--entrypoint", "1"]
        )
        self.assertEqual(args.operation, "decode")
        self.assertEqual(args.profile, "32")

    def test_device_default(self):
        with patch.dict(os.environ, {}, clear=True):
            args = m.parse_args(
                ["decode", "in.mkv", "--profile", "7", "--entrypoint", "1"]
            )
            self.assertEqual(args.device, m.DEFAULT_VAAPI_DEVICE)


class TestPerformTest(unittest.TestCase):
    def _args(self, **kw):
        base = dict(
            operation="decode",
            input="av1/foo.mkv",
            profile="32",
            entrypoint="1",
            output_codec=None,
            output_container="mp4",
            device="/dev/dri/renderD128",
        )
        base.update(kw)
        return MagicMock(**base)

    def test_missing_input_fails(self):
        with patch.object(m.os.path, "exists", return_value=False):
            self.assertEqual(m.perform_test(self._args()), 1)

    @patch("ffmpeg_hw_codec_test.read_trace")
    @patch("ffmpeg_hw_codec_test.run_ffmpeg")
    @patch("ffmpeg_hw_codec_test.os.path.exists", return_value=True)
    def test_pass_when_hw_used_and_ffmpeg_ok(
        self, _exists, run_ffmpeg, read_trace
    ):
        run_ffmpeg.return_value = 0
        read_trace.return_value = "profile = 32\nentrypoint = 1\n"
        self.assertEqual(m.perform_test(self._args()), 0)

    @patch("ffmpeg_hw_codec_test.read_trace")
    @patch("ffmpeg_hw_codec_test.run_ffmpeg")
    @patch("ffmpeg_hw_codec_test.os.path.exists", return_value=True)
    def test_fail_when_hw_not_used(self, _exists, run_ffmpeg, read_trace):
        run_ffmpeg.return_value = 0
        read_trace.return_value = "nothing here"
        self.assertEqual(m.perform_test(self._args()), 1)

    @patch("ffmpeg_hw_codec_test.read_trace")
    @patch("ffmpeg_hw_codec_test.run_ffmpeg")
    @patch("ffmpeg_hw_codec_test.os.path.exists", return_value=True)
    def test_fail_when_ffmpeg_errors(self, _exists, run_ffmpeg, read_trace):
        run_ffmpeg.return_value = 1
        read_trace.return_value = "profile = 32\nentrypoint = 1\n"
        self.assertEqual(m.perform_test(self._args()), 1)

    @patch("ffmpeg_hw_codec_test.read_trace")
    @patch("ffmpeg_hw_codec_test.run_ffmpeg")
    @patch("ffmpeg_hw_codec_test.os.path.exists", return_value=True)
    def test_encode_uses_output_container(
        self, _exists, run_ffmpeg, read_trace
    ):
        run_ffmpeg.return_value = 0
        read_trace.return_value = "profile = 7\nentrypoint = 8\n"
        args = self._args(
            operation="encode",
            input="h264/foo.mp4",
            output_codec="h264_vaapi",
            output_container="mp4",
            profile="(6|7|13)",
            entrypoint="(6|8)",
        )
        self.assertEqual(m.perform_test(args), 0)
        built = run_ffmpeg.call_args[0][0]
        self.assertIn("h264_vaapi", built)


class TestRunFfmpeg(unittest.TestCase):
    @patch("ffmpeg_hw_codec_test.subprocess.run")
    def test_sets_libva_trace_env(self, sp_run):
        sp_run.return_value = MagicMock(returncode=0, stdout="out")
        rc = m.run_ffmpeg(["ffmpeg", "-i", "x"], "/tmp/libva.trace")
        self.assertEqual(rc, 0)
        env = sp_run.call_args[1]["env"]
        self.assertEqual(env["LIBVA_TRACE"], "/tmp/libva.trace")


if __name__ == "__main__":
    unittest.main()
