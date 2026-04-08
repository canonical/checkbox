#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
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

import host_utils


class TestGetArchTriple(unittest.TestCase):
    @patch("sysconfig.get_config_var", return_value="x86_64-linux-gnu")
    def test_returns_multiarch_value(self, _cfg):
        self.assertEqual(host_utils.get_arch_triple(), "x86_64-linux-gnu")

    @patch("sysconfig.get_config_var", return_value=None)
    def test_raises_when_multiarch_is_none(self, _cfg):
        with self.assertRaises(RuntimeError):
            host_utils.get_arch_triple()


if __name__ == "__main__":
    unittest.main()
