#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Pierre Equoy <pierre.equoy@canonical.com>
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

import subprocess
from unittest import TestCase
from unittest.mock import patch

import networking_http


class NetworkingHTTPTests(TestCase):
    @patch("networking_http.subprocess.run")
    @patch("networking_http.time.sleep")
    def test_http_connect_max_retries(self, mock_sleep, mock_run):
        with self.assertRaises(SystemExit):
            networking_http.http_connect("test", 0)

    @patch("networking_http.subprocess.run")
    @patch("networking_http.time.sleep")
    def test_http_connect_success(self, mock_sleep, mock_run):
        """
        Test that `http_connect` returns safely if the wget command returns 0
        """
        self.assertEqual(networking_http.http_connect("test", 3), None)

    @patch("networking_http.subprocess.run")
    @patch("networking_http.time.sleep")
    def test_http_connect_failure(self, mock_sleep, mock_run):
        """
        Test that if set to 3 retries, the connection command (wget, run
        through subprocess.run) will be called 3 times
        """
        mock_run.side_effect = subprocess.CalledProcessError(1, "")
        with self.assertRaises(SystemExit):
            networking_http.http_connect("test", 3)
        self.assertEqual(mock_run.call_count, 3)

    @patch("networking_http.http_connect")
    def test_main(self, mock_http_connect):
        args = ["test", "--attempts", "6"]
        networking_http.main(args)
        mock_http_connect.assert_called_with("test", 6)
