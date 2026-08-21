#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
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

from contextlib import redirect_stdout
from io import StringIO
from subprocess import STDOUT
from unittest import TestCase
from unittest.mock import patch

from va_profile_check import (
    NAMESPACE,
    cmd_forward,
    cmd_reverse,
    cmd_resource,
    entrypoint_to_direction,
    get_supported_features,
    main,
    parse_vainfo_output,
    profile_to_feature_id,
    run_vainfo,
)

VAINFO_OUTPUT = """\
vainfo: VA-API version: 1.20 (libva 2.12.0)
vainfo: Driver version: Intel iHD driver for Intel(R) Gen Graphics - 24.1.0 ()
vainfo: Supported profile and entrypoints
      VAProfileNone                   :	VAEntrypointVideoProc
      VAProfileNone                   :	VAEntrypointStats
      VAProfileMPEG2Simple            :	VAEntrypointVLD
      VAProfileMPEG2Simple            :	VAEntrypointEncSlice
      VAProfileH264Main               :	VAEntrypointVLD
      VAProfileH264Main               :	VAEntrypointEncSlice
      VAProfileH264Main               :	VAEntrypointEncSliceLP
      VAProfileH264High               :	VAEntrypointVLD
      VAProfileH264High               :	VAEntrypointFEI
      VAProfileVC1Advanced            :	VAEntrypointVLD
      VAProfileJPEGBaseline           :	VAEntrypointVLD
      VAProfileJPEGBaseline           :	VAEntrypointEncPicture
      VAProfileHEVCMain               :	VAEntrypointVLD
      VAProfileHEVCMain               :	VAEntrypointEncSlice
      VAProfileHEVCMain10             :	VAEntrypointVLD
      VAProfileVP9Profile0            :	VAEntrypointVLD
      VAProfileAV1Profile0            :	VAEntrypointVLD
      VAProfileAV1Profile0            :	VAEntrypointEncSlice
"""


class TestParseVainfoOutput(TestCase):
    def test_extracts_profile_and_entrypoint(self):
        parsed = parse_vainfo_output(VAINFO_OUTPUT)
        self.assertIn(("VAProfileH264Main", "VAEntrypointEncSlice"), parsed)
        self.assertIn(("VAProfileAV1Profile0", "VAEntrypointEncSlice"), parsed)

    def test_ignores_non_profile_lines(self):
        parsed = parse_vainfo_output(VAINFO_OUTPUT)
        for profile, _ in parsed:
            self.assertTrue(profile.startswith("VAProfile"))

    def test_ignores_line_without_colon(self):
        output = "VAProfileMPEG4Simple\nVAProfileH264Main:VAEntrypointVLD\n"
        parsed = parse_vainfo_output(output)
        self.assertEqual(parsed, [("VAProfileH264Main", "VAEntrypointVLD")])


class TestProfileToFeatureId(TestCase):
    def test_simple_profile(self):
        self.assertEqual(
            profile_to_feature_id("VAProfileH264High"), "h264_high"
        )

    def test_acronym_profile(self):
        self.assertEqual(
            profile_to_feature_id("VAProfileHEVCMain10"), "hevc_main10"
        )

    def test_acronym_with_upper_case_followed_by_lower(self):
        self.assertEqual(
            profile_to_feature_id("VAProfileH264ConstrainedBaseline"),
            "h264_constrained_baseline",
        )

    def test_digit_and_underscore_profile(self):
        self.assertEqual(
            profile_to_feature_id("VAProfileVP8Version0_3"),
            "vp8_version0_3",
        )


class TestEntrypointToDirection(TestCase):
    def test_decoder(self):
        self.assertEqual(entrypoint_to_direction("VAEntrypointVLD"), "decoder")

    def test_encoder(self):
        for entrypoint in (
            "VAEntrypointEncSlice",
            "VAEntrypointEncSliceLP",
            "VAEntrypointEncPicture",
            "VAEntrypointFEI",
        ):
            self.assertEqual(entrypoint_to_direction(entrypoint), "encoder")

    def test_non_codec_entrypoint(self):
        for entrypoint in (
            "VAEntrypointVideoProc",
            "VAEntrypointStats",
            "VAEntrypointProtectedContent",
        ):
            self.assertIsNone(entrypoint_to_direction(entrypoint))


class TestRunVainfo(TestCase):
    def test_invokes_check_output_with_vainfo(self):
        with patch("va_profile_check.check_output") as check_output_mock:
            check_output_mock.return_value = VAINFO_OUTPUT
            self.assertEqual(run_vainfo(), VAINFO_OUTPUT)
        check_output_mock.assert_called_once_with(
            ["vainfo"], universal_newlines=True, stderr=STDOUT
        )


class TestGetSupportedFeatures(TestCase):
    def setUp(self):
        self.features = get_supported_features(VAINFO_OUTPUT)

    def test_deduped_per_profile_and_direction(self):
        self.assertEqual(
            self.features["has_h264_main_decoder"]["entrypoints"],
            ["VAEntrypointVLD"],
        )
        self.assertEqual(
            sorted(self.features["has_h264_main_encoder"]["entrypoints"]),
            ["VAEntrypointEncSlice", "VAEntrypointEncSliceLP"],
        )

    def test_enc_picture_maps_to_encoder(self):
        self.assertIn("has_jpeg_baseline_encoder", self.features)

    def test_video_proc_and_stats_are_skipped(self):
        self.assertNotIn("has_none_decoder", self.features)
        self.assertNotIn("has_none_encoder", self.features)


class TestCmdForward(TestCase):
    def test_declared_feature_succeeds(self):
        with patch(
            "va_profile_check.get_manifest",
            return_value={NAMESPACE + "::has_h264_high_decoder": True},
        ):
            with redirect_stdout(StringIO()):
                self.assertEqual(cmd_forward("has_h264_high_decoder"), 0)

    def test_undeclared_feature_fails(self):
        with patch(
            "va_profile_check.get_manifest",
            return_value={NAMESPACE + "::has_hevc_main_decoder": True},
        ):
            with redirect_stdout(StringIO()):
                self.assertEqual(cmd_forward("has_h264_high_decoder"), 1)


class TestCmdReverse(TestCase):
    def test_all_declared_features_present(self):
        with patch(
            "va_profile_check.run_vainfo",
            return_value=VAINFO_OUTPUT,
        ):
            with patch(
                "va_profile_check.get_manifest",
                return_value={
                    NAMESPACE + "::has_h264_main_decoder": True,
                    NAMESPACE + "::has_h264_main_encoder": True,
                },
            ):
                with redirect_stdout(StringIO()):
                    self.assertEqual(cmd_reverse(), 0)

    def test_declared_feature_missing_fails(self):
        with patch(
            "va_profile_check.run_vainfo",
            return_value=VAINFO_OUTPUT,
        ):
            with patch(
                "va_profile_check.get_manifest",
                return_value={
                    NAMESPACE + "::has_h264_main_decoder": True,
                    NAMESPACE + "::has_hevc_main10_encoder": True,
                },
            ):
                with redirect_stdout(StringIO()):
                    self.assertEqual(cmd_reverse(), 1)

    def test_non_codec_manifest_keys_are_ignored(self):
        with patch(
            "va_profile_check.run_vainfo",
            return_value=VAINFO_OUTPUT,
        ):
            with patch(
                "va_profile_check.get_manifest",
                return_value={
                    NAMESPACE + "::has_va_api": True,
                    NAMESPACE + "::has_h264_main_decoder": True,
                    "com.canonical.certification::other_key": True,
                },
            ):
                with redirect_stdout(StringIO()):
                    self.assertEqual(cmd_reverse(), 0)

    def test_false_declared_features_are_ignored(self):
        with patch(
            "va_profile_check.run_vainfo",
            return_value=VAINFO_OUTPUT,
        ):
            with patch(
                "va_profile_check.get_manifest",
                return_value={
                    NAMESPACE + "::has_h264_main_decoder": False,
                    NAMESPACE + "::has_h264_main_encoder": True,
                },
            ):
                with redirect_stdout(StringIO()):
                    self.assertEqual(cmd_reverse(), 0)


class TestCmdResource(TestCase):
    def test_output_contains_resource_fields(self):
        with patch(
            "va_profile_check.run_vainfo",
            return_value=VAINFO_OUTPUT,
        ):
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(cmd_resource(), 0)
            content = output.getvalue()
        self.assertIn("profile: h264_high", content)
        self.assertIn("profile_name: VAProfileH264High", content)
        self.assertIn("direction: encoder", content)
        self.assertIn("feature: has_h264_high_encoder", content)
        self.assertIn("entrypoints: VAEntrypointFEI", content)


class TestMain(TestCase):
    def test_resource(self):
        with patch(
            "va_profile_check.run_vainfo",
            return_value=VAINFO_OUTPUT,
        ):
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["resource"]), 0)

    def test_forward_declared(self):
        with patch(
            "va_profile_check.get_manifest",
            return_value={NAMESPACE + "::has_h264_high_decoder": True},
        ):
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["forward", "has_h264_high_decoder"]), 0)

    def test_forward_undeclared(self):
        with patch(
            "va_profile_check.get_manifest",
            return_value={NAMESPACE + "::has_hevc_main_decoder": True},
        ):
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["forward", "has_h264_high_decoder"]), 1)

    def test_reverse(self):
        with patch(
            "va_profile_check.run_vainfo",
            return_value=VAINFO_OUTPUT,
        ):
            with patch(
                "va_profile_check.get_manifest",
                return_value={
                    NAMESPACE + "::has_h264_main_decoder": True,
                },
            ):
                with redirect_stdout(StringIO()):
                    self.assertEqual(main(["reverse"]), 0)

    def test_unknown_command_raises_system_exit(self):
        with self.assertRaises(SystemExit):
            main(["bogus"])
