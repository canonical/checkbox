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

import json
import os
import tempfile
import unittest

from fluster_runner import get_vectors_for_profile, parse_junit_xml

JUNIT_ALL_PASS = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="JVT-AVC_V1" tests="10" failures="0" errors="0">
    <testcase name="AUD_MW_E" classname="FFmpeg-H.264-VAAPI"/>
  </testsuite>
</testsuites>
"""

JUNIT_SOME_FAIL = """\
<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="JVT-AVC_V1" tests="10" failures="2" errors="1">
    <testcase name="AUD_MW_E" classname="FFmpeg-H.264-VAAPI"/>
    <testcase name="BA1_FT_C" classname="FFmpeg-H.264-VAAPI">
      <failure message="checksum mismatch"/>
    </testcase>
    <testcase name="CABA1_Sony_D" classname="FFmpeg-H.264-VAAPI">
      <error message="decoder error"/>
    </testcase>
  </testsuite>
</testsuites>
"""

TEST_SUITE_JSON = {
    "name": "JVT-AVC_V1",
    "codec": "H.264",
    "test_vectors": [
        {
            "name": "AUD_MW_E",
            "profile": "Constrained Baseline",
            "input_file": "AUD_MW_E.264",
            "output_format": "yuv420p",
            "result": "abc123",
        },
        {
            "name": "BA1_FT_C",
            "profile": "Constrained Baseline",
            "input_file": "BA1_FT_C.264",
            "output_format": "yuv420p",
            "result": "def456",
        },
        {
            "name": "CABA1_Sony_D",
            "profile": "Main",
            "input_file": "CABA1_Sony_D.jsv",
            "output_format": "yuv420p",
            "result": "ghi789",
        },
        {
            "name": "CAMA1_Sony_C",
            "profile": "Main",
            "input_file": "CAMA1_Sony_C.jsv",
            "output_format": "yuv420p",
            "result": "jkl012",
        },
        {
            "name": "ADB10_I",
            "profile": "High",
            "input_file": "ADB10_I.264",
            "output_format": "yuv420p",
            "result": "mno345",
        },
    ],
}


class TestGetVectorsForProfile(unittest.TestCase):
    def test_main_profile(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(TEST_SUITE_JSON, f)
            path = f.name

        vectors = get_vectors_for_profile(path, "Main")
        self.assertEqual(vectors, ["CABA1_Sony_D", "CAMA1_Sony_C"])
        os.unlink(path)

    def test_baseline_profile(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(TEST_SUITE_JSON, f)
            path = f.name

        vectors = get_vectors_for_profile(path, "Constrained Baseline")
        self.assertEqual(vectors, ["AUD_MW_E", "BA1_FT_C"])
        os.unlink(path)

    def test_unknown_profile(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(TEST_SUITE_JSON, f)
            path = f.name

        vectors = get_vectors_for_profile(path, "High 10")
        self.assertEqual(vectors, [])
        os.unlink(path)


class TestParseJunitXml(unittest.TestCase):
    def test_all_pass_above_threshold(self):
        result = parse_junit_xml(JUNIT_ALL_PASS, 0.9)
        self.assertTrue(result)

    def test_all_pass_threshold_one(self):
        result = parse_junit_xml(JUNIT_ALL_PASS, 1.0)
        self.assertTrue(result)

    def test_some_fail_below_threshold(self):
        result = parse_junit_xml(JUNIT_SOME_FAIL, 0.9)
        self.assertFalse(result)

    def test_some_fail_above_threshold(self):
        result = parse_junit_xml(JUNIT_SOME_FAIL, 0.5)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
