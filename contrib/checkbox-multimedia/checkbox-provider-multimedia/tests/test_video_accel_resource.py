#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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

import os
import unittest
from unittest.mock import patch

import video_accel_resource
from video_accel_resource import (
    generate_decode_resources,
    generate_encode_resources,
    parse_profiles,
    slugify,
)

DECODE_MAP = {
    "fluster_decoders": {
        "va-api": {
            "ffmpeg": {
                "H.264": "FFmpeg-H.264-VAAPI",
                "H.265": "FFmpeg-H.265-VAAPI",
                "VP9": "FFmpeg-VP9-VAAPI",
                "AV1": "FFmpeg-AV1-VAAPI",
            },
            "gstreamer": {
                "H.264": "GStreamer-H.264-VAAPI-Gst1.0",
                "H.265": "GStreamer-H.265-VAAPI-Gst1.0",
            },
        },
        "vdpau": {
            "ffmpeg": {
                "H.264": "FFmpeg-H.264-VDPAU",
            },
        },
        "nvdec": {
            "ffmpeg": {
                "H.264": "FFmpeg-H.264-CUDA",
                "AV1": "FFmpeg-AV1-CUDA",
            },
        },
    },
    "test_suites": {
        "H.264": {
            "Constrained Baseline": ["JVT-AVC_V1"],
            "Main": ["JVT-AVC_V1"],
            "High": ["JVT-AVC_V1", "JVT-FR-EXT"],
        },
        "H.265": {
            "Main": ["JCT-VC-HEVC_V1"],
            "Main 10": ["JCT-VC-RExt"],
        },
        "AV1": {
            "Main": ["AV1-TEST-VECTORS"],
        },
    },
    "encode_profiles": {
        "va-api": {
            "h264_vaapi": {
                "codec": "H.264",
                "profiles": [
                    "Constrained Baseline",
                    "Main",
                    "High",
                ],
            },
            "hevc_vaapi": {
                "codec": "H.265",
                "profiles": ["Main", "Main 10"],
            },
            "av1_vaapi": {"codec": "AV1", "profiles": ["Main"]},
        },
        "nvenc": {
            "h264_nvenc": {
                "codec": "H.264",
                "profiles": ["Main", "High"],
            },
            "av1_nvenc": {"codec": "AV1", "profiles": ["Main"]},
        },
    },
}


class TestParseProfiles(unittest.TestCase):
    def test_basic_parsing(self):
        result = parse_profiles("H.264:Main,High;H.265:Main")
        self.assertEqual(
            result, [("H.264", ["Main", "High"]), ("H.265", ["Main"])]
        )

    def test_empty_string(self):
        result = parse_profiles("")
        self.assertEqual(result, [])

    def test_whitespace_handling(self):
        result = parse_profiles(" H.264 : Main , High ; H.265 : Main 10 ")
        self.assertEqual(
            result,
            [("H.264", ["Main", "High"]), ("H.265", ["Main 10"])],
        )

    def test_single_codec(self):
        result = parse_profiles("AV1:Main")
        self.assertEqual(result, [("AV1", ["Main"])])

    def test_missing_colon_skipped(self):
        result = parse_profiles("H.264;H.265:Main")
        self.assertEqual(result, [("H.265", ["Main"])])

    def test_trailing_semicolon(self):
        result = parse_profiles("H.264:Main;")
        self.assertEqual(result, [("H.264", ["Main"])])


class TestSlugify(unittest.TestCase):
    def test_lowercase(self):
        self.assertEqual(slugify("Main"), "main")

    def test_spaces_to_hyphens(self):
        self.assertEqual(slugify("Main 10"), "main-10")

    def test_special_chars(self):
        self.assertEqual(
            slugify("Constrained Baseline"), "constrained-baseline"
        )

    def test_multiple_spaces(self):
        self.assertEqual(slugify("High 4:2:2"), "high-4-2-2")


class TestGenerateDecodeResources(unittest.TestCase):
    def test_vaapi_ffmpeg_h264_main(self):
        env = {"HW_VIDEO_ACCEL_VAAPI_DECODE": "H.264:Main"}
        resources = generate_decode_resources(env, DECODE_MAP, ["ffmpeg"])
        self.assertEqual(len(resources), 1)
        r = resources[0]
        self.assertEqual(r["scenario"], "fluster-decode")
        self.assertEqual(r["decoder"], "FFmpeg-H.264-VAAPI")
        self.assertEqual(r["test_suite"], "JVT-AVC_V1")
        self.assertEqual(r["codec"], "H.264")
        self.assertEqual(r["profile"], "Main")

    def test_vaapi_ffmpeg_h264_high_two_suites(self):
        env = {"HW_VIDEO_ACCEL_VAAPI_DECODE": "H.264:High"}
        resources = generate_decode_resources(env, DECODE_MAP, ["ffmpeg"])
        self.assertEqual(len(resources), 2)
        suite_names = [r["test_suite"] for r in resources]
        self.assertIn("JVT-AVC_V1", suite_names)
        self.assertIn("JVT-FR-EXT", suite_names)

    def test_vaapi_gstreamer_h264(self):
        env = {"HW_VIDEO_ACCEL_VAAPI_DECODE": "H.264:Main"}
        resources = generate_decode_resources(env, DECODE_MAP, ["gstreamer"])
        self.assertEqual(len(resources), 1)
        self.assertEqual(
            resources[0]["decoder"], "GStreamer-H.264-VAAPI-Gst1.0"
        )

    def test_vaapi_both_backends(self):
        env = {"HW_VIDEO_ACCEL_VAAPI_DECODE": "H.264:Main"}
        resources = generate_decode_resources(
            env, DECODE_MAP, ["ffmpeg", "gstreamer"]
        )
        self.assertEqual(len(resources), 2)
        decoders = [r["decoder"] for r in resources]
        self.assertIn("FFmpeg-H.264-VAAPI", decoders)
        self.assertIn("GStreamer-H.264-VAAPI-Gst1.0", decoders)

    def test_unknown_backend(self):
        env = {"HW_VIDEO_ACCEL_VAAPI_DECODE": "H.264:Main"}
        resources = generate_decode_resources(env, DECODE_MAP, ["vulkan"])
        self.assertEqual(len(resources), 0)

    def test_unknown_codec(self):
        env = {"HW_VIDEO_ACCEL_VAAPI_DECODE": "VC-1:Main"}
        resources = generate_decode_resources(env, DECODE_MAP, ["ffmpeg"])
        self.assertEqual(len(resources), 0)

    def test_nvdec_ffmpeg(self):
        env = {"HW_VIDEO_ACCEL_NVDEC_DECODE": "H.264:Main;AV1:Main"}
        resources = generate_decode_resources(env, DECODE_MAP, ["ffmpeg"])
        self.assertEqual(len(resources), 2)
        codecs = {r["codec"] for r in resources}
        self.assertEqual(codecs, {"H.264", "AV1"})

    def test_vdpau_ffmpeg(self):
        env = {"HW_VIDEO_ACCEL_VDPAU_DECODE": "H.264:Main"}
        resources = generate_decode_resources(env, DECODE_MAP, ["ffmpeg"])
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["decoder"], "FFmpeg-H.264-VDPAU")

    def test_no_matching_profile_in_suites(self):
        env = {"HW_VIDEO_ACCEL_VAAPI_DECODE": "H.264:Unknown"}
        resources = generate_decode_resources(env, DECODE_MAP, ["ffmpeg"])
        self.assertEqual(len(resources), 0)

    def test_empty_env(self):
        env = {}
        resources = generate_decode_resources(env, DECODE_MAP, ["ffmpeg"])
        self.assertEqual(len(resources), 0)


class TestGenerateEncodeResources(unittest.TestCase):
    def test_vaapi_encode_h264(self):
        env = {"HW_VIDEO_ACCEL_VAAPI_ENCODE": "H.264:Main,High"}
        resources = generate_encode_resources(env, DECODE_MAP)
        self.assertEqual(len(resources), 2)
        for r in resources:
            self.assertEqual(r["scenario"], "encode")
        encoders = [r["encoder"] for r in resources]
        self.assertIn("h264_vaapi", encoders)
        for r in resources:
            self.assertIn("ffmpeg_encoder", r)
            self.assertEqual(r["ffmpeg_encoder"], r["encoder"])

    def test_vaapi_encode_profile_opts(self):
        env = {"HW_VIDEO_ACCEL_VAAPI_ENCODE": "H.264:Main"}
        resources = generate_encode_resources(env, DECODE_MAP)
        self.assertEqual(len(resources), 1)
        self.assertEqual(
            resources[0]["ffmpeg_profile_opts"], "-profile:v main"
        )

    def test_nvenc_encode(self):
        env = {"HW_VIDEO_ACCEL_NVENC_ENCODE": "H.264:Main;AV1:Main"}
        resources = generate_encode_resources(env, DECODE_MAP)
        self.assertEqual(len(resources), 2)
        encoders = [r["encoder"] for r in resources]
        self.assertIn("h264_nvenc", encoders)
        self.assertIn("av1_nvenc", encoders)

    def test_profile_not_in_data_file(self):
        env = {"HW_VIDEO_ACCEL_VAAPI_ENCODE": "H.264:Unknown"}
        resources = generate_encode_resources(env, DECODE_MAP)
        self.assertEqual(len(resources), 0)

    def test_codec_not_in_data_file(self):
        env = {"HW_VIDEO_ACCEL_VAAPI_ENCODE": "VC-1:Main"}
        resources = generate_encode_resources(env, DECODE_MAP)
        self.assertEqual(len(resources), 0)

    def test_empty_env(self):
        env = {}
        resources = generate_encode_resources(env, DECODE_MAP)
        self.assertEqual(len(resources), 0)


class TestMainIntegration(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "HW_VIDEO_ACCEL_VAAPI_DECODE": "H.264:Main",
            "HW_VIDEO_ACCEL_VAAPI_ENCODE": "H.264:Main",
            "PLAINBOX_PROVIDER_DATA": "/tmp/mock-data",
        },
    )
    def test_main_produces_output(self):
        with patch.object(
            video_accel_resource,
            "load_decoder_map",
            return_value=DECODE_MAP,
        ):
            with patch("sys.argv", ["video_accel_resource.py"]):
                import io
                from contextlib import redirect_stdout

                output = io.StringIO()
                with redirect_stdout(output):
                    video_accel_resource.main()
                text = output.getvalue()
                self.assertIn("scenario: fluster-decode", text)
                self.assertIn("scenario: encode", text)
                self.assertIn("decoder: FFmpeg-H.264-VAAPI", text)
                self.assertIn("ffmpeg_encoder: h264_vaapi", text)


if __name__ == "__main__":
    unittest.main()
