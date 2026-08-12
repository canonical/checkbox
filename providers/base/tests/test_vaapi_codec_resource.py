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
import unittest as ut
from unittest.mock import MagicMock, patch, call

import vaapi_codec_resource as m

VAINFO_SAMPLE = "\n".join(
    [
        "libva info: VA-API version 1.23.0",
        "libva info: Found init function __vaDriverInit_1_23",
        "vainfo: VA-API version: 1.23 (libva 2.23.0)",
        "vainfo: Supported profile and entrypoints",
        "      VAProfileNone                   :\tVAEntrypointVideoProc",
        "      VAProfileH264High               :\tVAEntrypointVLD",
        "      VAProfileH264High               :\tVAEntrypointEncSlice",
        "      VAProfileMPEG2Main              :\tVAEntrypointVLD",
        "      VAProfileAV1Profile0            :\tVAEntrypointVLD",
    ]
)


class TestParseVainfo(ut.TestCase):
    def test_parses_known_pairs_with_numeric_ids(self):
        records = list(m.parse_vainfo(VAINFO_SAMPLE))
        self.assertIn(
            {
                "profile": "VAProfileH264High",
                "profile_id": 7,
                "entrypoint": "VAEntrypointVLD",
                "entrypoint_id": 1,
            },
            records,
        )
        self.assertIn(
            {
                "profile": "VAProfileH264High",
                "profile_id": 7,
                "entrypoint": "VAEntrypointEncSlice",
                "entrypoint_id": 6,
            },
            records,
        )

    def test_includes_profile_none_video_proc(self):
        # VAProfileNone has no numeric id but is still emitted so the
        # resource stays informative.
        records = list(m.parse_vainfo(VAINFO_SAMPLE))
        none_records = [r for r in records if r["profile"] == "VAProfileNone"]
        self.assertEqual(len(none_records), 1)
        self.assertEqual(none_records[0]["profile_id"], "")
        self.assertEqual(none_records[0]["entrypoint_id"], 10)

    def test_ignores_headers_and_log_noise(self):
        records = list(m.parse_vainfo(VAINFO_SAMPLE))
        # 4 profile/entrypoint lines in the sample.
        self.assertEqual(len(records), 5)

    def test_unknown_profile_gets_empty_id(self):
        text = "      VAProfileFuture999           :\tVAEntrypointVLD"
        record = list(m.parse_vainfo(text))[0]
        self.assertEqual(record["profile_id"], "")
        self.assertEqual(record["entrypoint_id"], 1)

    def test_empty_input_yields_nothing(self):
        self.assertEqual(list(m.parse_vainfo("")), [])


class TestGetVainfoOutput(ut.TestCase):
    @patch("subprocess.run")
    def test_returns_stdout_on_success(self, mock_run: MagicMock):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = VAINFO_SAMPLE
        self.assertEqual(
            m.get_vainfo_output("/dev/dri/renderD128"), VAINFO_SAMPLE
        )

    @patch("subprocess.run")
    def test_returns_none_on_failure(self, mock_run: MagicMock):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = "vaInitialize failed"
        self.assertIsNone(m.get_vainfo_output("/dev/dri/renderD128"))

    @patch("subprocess.run", side_effect=OSError("no vainfo"))
    def test_returns_none_when_vainfo_missing(self, mock_run: MagicMock):
        self.assertIsNone(m.get_vainfo_output("/dev/dri/renderD128"))


class TestMain(ut.TestCase):
    @patch("builtins.print")
    @patch("vaapi_codec_resource.get_vainfo_output")
    def test_prints_records(
        self, mock_output: MagicMock, mock_print: MagicMock
    ):
        mock_output.return_value = VAINFO_SAMPLE
        m.main()
        mock_print.assert_has_calls(
            [
                call("profile: VAProfileH264High"),
                call("profile_id: 7"),
                call("entrypoint: VAEntrypointVLD"),
                call("entrypoint_id: 1"),
                call(),
            ]
        )

    @patch("builtins.print")
    @patch("vaapi_codec_resource.get_vainfo_output")
    def test_prints_nothing_when_vainfo_unavailable(
        self, mock_output: MagicMock, mock_print: MagicMock
    ):
        mock_output.return_value = None
        m.main()
        mock_print.assert_not_called()


if __name__ == "__main__":
    ut.main()
