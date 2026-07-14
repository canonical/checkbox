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

import unittest
from argparse import Namespace
from subprocess import CompletedProcess
from unittest.mock import patch

import socketcan_test


class TestCheckInterfaces(unittest.TestCase):
    @patch("socketcan_test.subprocess.run")
    def test_fails_when_no_can_interfaces(self, mock_run):
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        with self.assertRaises(SystemExit) as context:
            socketcan_test.check_interfaces(Namespace(expected_count=None))

        self.assertEqual(
            str(context.exception), "No CAN interfaces found on this platform"
        )

    @patch("socketcan_test.subprocess.run")
    def test_passes_when_interfaces_exist_without_expected(self, mock_run):
        mock_run.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout="2: can0: <NOARP> mtu 16\n3: can1: <NOARP> mtu 16\n",
            stderr="",
        )

        socketcan_test.check_interfaces(Namespace(expected_count=None))

    @patch("socketcan_test.subprocess.run")
    def test_passes_when_expected_matches_detected(self, mock_run):
        mock_run.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout="2: can0: <NOARP> mtu 16\n3: can1: <NOARP> mtu 16\n",
            stderr="",
        )

        socketcan_test.check_interfaces(Namespace(expected_count=2))

    @patch("socketcan_test.subprocess.run")
    def test_fails_when_expected_does_not_match_detected(self, mock_run):
        mock_run.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout="2: can0: <NOARP> mtu 16\n3: can1: <NOARP> mtu 16\n",
            stderr="",
        )

        with self.assertRaises(SystemExit) as context:
            socketcan_test.check_interfaces(Namespace(expected_count=3))

        self.assertEqual(
            str(context.exception),
            "Expected 3 CAN interfaces, found 2",
        )


if __name__ == "__main__":
    unittest.main()
