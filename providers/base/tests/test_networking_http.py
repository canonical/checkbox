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
    def test_http_connect_max_retries(self, mock_subprocess_run):
        connection_test = networking_http.HTTPConnection("test", 0)
        with self.assertRaises(SystemExit):
            connection_test.http_connect()

    @patch("networking_http.subprocess.run")
    def test_http_connect(self, mock_subprocess_run):
        """
        Test that if set to 3 retries, the connection command (wget, run
        through subprocess.run) will be called 3 times
        """
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, "")
        connection_test = networking_http.HTTPConnection("test", 3)
        with self.assertRaises(SystemExit):
            connection_test.http_connect()
        self.assertEqual(mock_subprocess_run.call_count, 3)

    @patch("networking_http.HTTPConnection")
    def test_main(self, mock_HTTPConnection):
        args = ["test", "--retries", "5"]
        networking_http.main(args)
        mock_HTTPConnection.assert_called_with("test", 5)
