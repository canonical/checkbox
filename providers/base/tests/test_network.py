#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
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
from unittest.mock import patch, mock_open

from network import IPerfPerformanceTest


class IPerfPerfomanceTestTests(unittest.TestCase):

    def test_find_numa_reports_node(self):
        with patch("builtins.open", mock_open(read_data="1")) as mo:
            returned = IPerfPerformanceTest.find_numa(None, "device")
            self.assertEqual(returned, 1)

    def test_find_numa_minus_one_from_sysfs(self):
        with patch("builtins.open", mock_open(read_data="-1")) as mo:
            returned = IPerfPerformanceTest.find_numa(None, "device")
            self.assertEqual(returned, -1)

    def test_find_numa_numa_node_not_found(self):
        with patch("builtins.open", mock_open()) as mo:
            mo.side_effect = FileNotFoundError
            returned = IPerfPerformanceTest.find_numa(None, "device")
            self.assertEqual(returned, -1)
