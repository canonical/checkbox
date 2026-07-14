#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2022 Canonical Ltd.
#
# Authors:
#     Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
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
#
"""Tests for `verify_junit_report.py`"""

import tempfile
import unittest

import verify_junit_report


class TestMain(unittest.TestCase):
    def test_verifying_passing_case_is_found(self):
        with tempfile.NamedTemporaryFile() as xml_file:
            xml_file.write(SAMPLE_REPORT.encode())
            xml_file.flush()

            args = [xml_file.name, PASSING_TEST_CASE, PASSING_TEST_NAME]
            verify_junit_report.main(args)

    def test_verifying_failing_case_raises_assertion_error(self):
        with tempfile.NamedTemporaryFile() as xml_file:
            xml_file.write(SAMPLE_REPORT.encode())
            xml_file.flush()

            args = [xml_file.name, FAILING_TEST_CASE, FAILING_TEST_NAME]
            with self.assertRaises(AssertionError):
                verify_junit_report.main(args)

    def test_verifying_missing_case_raises_key_error(self):
        with tempfile.NamedTemporaryFile() as xml_file:
            xml_file.write(SAMPLE_REPORT.encode())
            xml_file.flush()

            args = [xml_file.name, "missing.case", "missing_test"]
            with self.assertRaises(KeyError):
                verify_junit_report.main(args)


PASSING_TEST_CASE = "tests.integration.test_dss1"
PASSING_TEST_NAME = "test_status_before_initialize[cpu]"
FAILING_TEST_CASE = "tests.integration.test_dss2"
FAILING_TEST_NAME = "test_status_after_initialize[cpu]"
FAIURE_CONTENT = "ERROR TRACEBACK"

SAMPLE_REPORT = f"""\
<?xml version="1.0" encoding="utf-8" ?>
<testsuites><testsuite
        name="pytest"
        errors="0"
        failures="1"
        skipped="0"
        tests="2"
        time="1.251"
        timestamp="2025-10-16T09:27:45.227389"
        hostname="checkbox"
    ><testcase
            classname="{PASSING_TEST_CASE}"
            name="{PASSING_TEST_NAME}"
            time="0.497"
        /><testcase
            classname="{FAILING_TEST_CASE}"
            name="{FAILING_TEST_NAME}"
            time="0.558"
        ><failure message="failure-message">{FAIURE_CONTENT}</failure>
        </testcase>
    </testsuite>
</testsuites>
"""
