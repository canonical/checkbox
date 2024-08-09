#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# Written by:
#   Pedro Avalos Jimenez <pedro.avalosjimenez@canonical.com>
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

import unittest
from unittest.mock import patch
from subprocess import CalledProcessError, TimeoutExpired

from stress_ng_test import main


class TestMainFunction(unittest.TestCase):
    @patch("stress_ng_test.shutil.which", return_value=None)
    @patch("stress_ng_test.sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_no_stress_ng(self, shutil_which_mock):
        self.assertEqual(main(), 1)

    @patch("stress_ng_test.os.geteuid", return_value=1000)
    @patch("stress_ng_test.shutil.which", return_value="/usr/bin/stress-ng")
    @patch("stress_ng_test.sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_not_root(self, shutil_which_mock, os_geteuid_mock):
        self.assertEqual(main(), 1)

    @patch("stress_ng_test.check_output", side_effect=FileNotFoundError)
    @patch("stress_ng_test.os.geteuid", return_value=0)
    @patch("stress_ng_test.shutil.which", return_value="/usr/bin/stress-ng")
    @patch("stress_ng_test.sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_stress_ng_not_found(
        self, shutil_which_mock, os_geteuid_mock, check_output_mock
    ):
        self.assertEqual(main(), 1)

    @patch("stress_ng_test.check_output", side_effect=TimeoutExpired(b"", 1))
    @patch("stress_ng_test.os.geteuid", return_value=0)
    @patch("stress_ng_test.shutil.which", return_value="/usr/bin/stress-ng")
    @patch("stress_ng_test.sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_timeout(
        self, shutil_which_mock, os_geteuid_mock, check_output_mock
    ):
        self.assertEqual(main(), 1)

    @patch("stress_ng_test.check_output", side_effect=KeyboardInterrupt)
    @patch("stress_ng_test.os.geteuid", return_value=0)
    @patch("stress_ng_test.shutil.which", return_value="/usr/bin/stress-ng")
    @patch("stress_ng_test.sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_keyboard_interrupt(
        self, shutil_which_mock, os_geteuid_mock, check_output_mock
    ):
        self.assertEqual(main(), 1)

    @patch("stress_ng_test.check_output", side_effect=CalledProcessError(1, b"", b""))
    @patch("stress_ng_test.os.geteuid", return_value=0)
    @patch("stress_ng_test.shutil.which", return_value="/usr/bin/stress-ng")
    @patch("stress_ng_test.sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_stress_ng_error(
        self, shutil_which_mock, os_geteuid_mock, check_output_mock
    ):
        self.assertEqual(main(), 1)

    @patch("stress_ng_test.check_output")
    @patch("stress_ng_test.os.geteuid", return_value=0)
    @patch("stress_ng_test.shutil.which", return_value="/usr/bin/stress-ng")
    @patch("stress_ng_test.sys.argv", ["stress_ng_test.py", "cpu"])
    def test_main_stress_cpu_success(
        self, shutil_which_mock, os_geteuid_mock, check_output_mock
    ):
        self.assertEqual(main(), 0)
