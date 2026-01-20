# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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


from unittest import TestCase, mock

from checkbox_ng.launcher.translator import (
    split_comment,
    split_string_values,
    Translator,
)


class SplitStringableTests(TestCase):
    def test_no_comment_in_string(self):
        value, comment = split_comment("just some text")
        self.assertEqual(value, "just some text")
        self.assertEqual(comment, "")

    def test_string_is_just_a_comment(self):
        value, comment = split_comment("# this is only a comment")
        self.assertEqual(value, "")
        self.assertEqual(comment, "this is only a comment")

    def test_normal_text_with_comment(self):
        value, comment = split_comment("some text # a comment")
        self.assertEqual(value, "some text")
        self.assertEqual(comment, "a comment")

    def test_fake_comment_in_string_delimiters(self):
        # Double quotes
        value, comment = split_comment('"fake # inside" # real comment')
        self.assertEqual(value, '"fake # inside"')
        self.assertEqual(comment, "real comment")

        # Single quotes
        value, comment = split_comment("'fake # inside' # real comment")
        self.assertEqual(value, "'fake # inside'")
        self.assertEqual(comment, "real comment")

    def test_nested_escaped_delimiters_with_fake_comments(self):
        # Escaped quote inside string, fake comments, real comment at end
        value, comment = split_comment("'it\\'s \"a #fake\" test' # real")
        self.assertEqual(value, "'it\\'s \"a #fake\" test'")
        self.assertEqual(comment, "real")

    def test_string_values(self):
        value, attributes = split_string_values(
            '"bluetooth/bluez-internal-hci-tests_Read Country Code" '
            "certification-status=blocker"
        )
        self.assertEqual(
            value, '"bluetooth/bluez-internal-hci-tests_Read Country Code"'
        )
        self.assertEqual(attributes, "certification-status=blocker")
