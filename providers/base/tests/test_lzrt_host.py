#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Shane McKee <shane.mckee@canonical.com>
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

import unittest
from unittest.mock import patch

import lzrt_host


class TestMain(unittest.TestCase):
    @patch("sys.argv", ["lzrt_host.py"])
    def test_missing_command_returns_error(self):
        self.assertEqual(lzrt_host.main(), 1)

    @patch("sys.argv", ["lzrt_host.py", "bogus"])
    def test_unknown_command_returns_error(self):
        self.assertEqual(lzrt_host.main(), 1)


if __name__ == "__main__":
    unittest.main()
