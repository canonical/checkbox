# Copyright 2024 Canonical Ltd.
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

from unittest.mock import MagicMock, patch

from cpuid import cpuid_to_human_friendly, main


class CpuidTests(unittest.TestCase):
    def test_hygon_dhyana_plus(self):
        self.assertEquals(
            cpuid_to_human_friendly("0x900f22"), "Hygon Dhyana Plus"
        )

    def test_unknown_throws(self):
        with self.assertRaises(ValueError):
            cpuid_to_human_friendly("0xdeadbeef")


class CpuidMainTests(unittest.TestCase):
    @patch("builtins.print")
    @patch("subprocess.check_output")
    @patch("cpuid.CPUID")
    def test_hygon_dhyana_plus(self, cpuid_mock, co_mock, print_mock):
        #import pdb; pdb.set_trace()
        call_mock = MagicMock()
        call_mock.return_value = [0x900f22, 0x0, 0x0, 0x0]
        cpuid_mock.return_value = call_mock
        co_mock.return_value = ""
        main()
        expected_msg = "CPUID: {} which appears to be a {} processor".format(
            "0x900f22", "Hygon Dhyana Plus"
        )
        print_mock.assert_called_with(expected_msg)

    @patch("subprocess.check_output")
    @patch("cpuid.CPUID")
    def test_unknown_cpu(self, cpuid_mock, co_mock):
        #import pdb; pdb.set_trace()
        call_mock = MagicMock()
        call_mock.return_value = [0xdeadbeef, 0x0, 0x0, 0x0]
        cpuid_mock.return_value = call_mock
        co_mock.return_value = ""
        with self.assertRaises(SystemExit):
            main()