# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
from checkbox_ng.utils import newline_join, set_all_loggers_level

"""Tests for checkbox_ng.utils"""


class TestNewlineJoin(unittest.TestCase):
    def test_newline_join_with_empty_head(self):
        head = ""
        tail = ["line 1", "line 2", "line 3"]
        expected_result = "line 1\nline 2\nline 3"
        self.assertEqual(newline_join(head, *tail), expected_result)

    def test_newline_join_with_nonempty_head(self):
        head = "header"
        tail = ["line 1", "line 2", "line 3"]
        expected_result = "header\nline 1\nline 2\nline 3"
        self.assertEqual(newline_join(head, *tail), expected_result)

    def test_newline_join_with_single_argument(self):
        head = "header"
        expected_result = "header"
        self.assertEqual(newline_join(head), expected_result)

    def test_newline_join_with_no_arguments(self):
        expected_result = ""
        self.assertEqual(newline_join(""), expected_result)


class TestSetAllLoggersLevel(unittest.TestCase):
    @unittest.mock.patch("checkbox_ng.utils.logging")
    def test_set_all_loggers_level(self, logging_mock):
        class FakeLogger:
            def __init__(self, name, level):
                self.name = name
                self.level = level

            def setLevel(self, level):
                self.level = level

        logging_mock.root.manager.loggerDict = {
            "some": FakeLogger("some", 10),
            "other": FakeLogger("other", 230),
        }
        set_all_loggers_level(0)
        self.assertTrue(
            all(
                x.level == 0
                for x in logging_mock.root.manager.loggerDict.values()
            )
        )
