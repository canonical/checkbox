# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.test_rfc822
=========================

Test definitions for plainbox.impl.rfc822 module
"""

from io import StringIO
from unittest import TestCase

from plainbox.impl.rfc822 import Origin
from plainbox.impl.rfc822 import RFC822Record
from plainbox.impl.rfc822 import load_rfc822_records
from plainbox.impl.rfc822 import dump_rfc822_records
from plainbox.impl.secure.checkbox_trusted_launcher import RFC822SyntaxError


class OriginTests(TestCase):

    def setUp(self):
        self.origin = Origin("file.txt", 10, 12)

    def test_smoke(self):
        self.assertEqual(self.origin.filename, "file.txt")
        self.assertEqual(self.origin.line_start, 10)
        self.assertEqual(self.origin.line_end, 12)

    def test_repr(self):
        expected = "<Origin filename:'file.txt' line_start:10 line_end:12>"
        observed = repr(self.origin)
        self.assertEqual(expected, observed)

    def test_str(self):
        expected = "file.txt:10-12"
        observed = str(self.origin)
        self.assertEqual(expected, observed)


class RFC822RecordTests(TestCase):

    def test_smoke(self):
        data = {'key': 'value'}
        origin = Origin('file.txt', 1, 1)
        record = RFC822Record(data, origin)
        self.assertEqual(record.data, data)
        self.assertEqual(record.origin, origin)


class RFC822ParserTestsMixIn():

    loader = load_rfc822_records

    def test_empty(self):
        with StringIO("") as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 0)

    def test_single_record(self):
        with StringIO("key:value") as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': 'value'})

    def test_many_newlines(self):
        text = (
            "\n"
            "\n"
            "key1:value1\n"
            "\n"
            "\n"
            "\n"
            "key2:value2\n"
            "\n"
            "\n"
            "key3:value3\n"
            "\n"
            "\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].data, {'key1': 'value1'})
        self.assertEqual(records[1].data, {'key2': 'value2'})
        self.assertEqual(records[2].data, {'key3': 'value3'})

    def test_many_records(self):
        text = (
            "key1:value1\n"
            "\n"
            "key2:value2\n"
            "\n"
            "key3:value3\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].data, {'key1': 'value1'})
        self.assertEqual(records[1].data, {'key2': 'value2'})
        self.assertEqual(records[2].data, {'key3': 'value3'})

    def test_multiline_value(self):
        text = (
            "key:\n"
            " longer\n"
            " value\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': 'longer\nvalue'})

    def test_multiline_value_with_space(self):
        text = (
            "key:\n"
            " longer\n"
            " .\n"
            " value\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': 'longer\n\nvalue'})

    def test_multiline_value_with_period(self):
        text = (
            "key:\n"
            " longer\n"
            " ..\n"
            " value\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': 'longer\n.\nvalue'})

    def test_many_multiline_values(self):
        text = (
            "key1:initial\n"
            " longer\n"
            " value 1\n"
            "\n"
            "key2:\n"
            " longer\n"
            " value 2\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].data, {'key1': 'initial\nlonger\nvalue 1'})
        self.assertEqual(records[1].data, {'key2': 'longer\nvalue 2'})

    def test_irrelevant_whitespace(self):
        text = "key :  value  "
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': 'value'})

    def test_relevant_whitespace(self):
        text = (
            "key:\n"
            " value\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': 'value'})

    def test_bad_multiline(self):
        text = " extra value"
        with StringIO(text) as stream:
            with self.assertRaises(RFC822SyntaxError) as call:
                type(self).loader(stream)
            self.assertEqual(call.exception.msg, "Unexpected multi-line value")

    def test_garbage(self):
        text = "garbage"
        with StringIO(text) as stream:
            with self.assertRaises(RFC822SyntaxError) as call:
                type(self).loader(stream)
            self.assertEqual(call.exception.msg, "Unexpected non-empty line")

    def test_syntax_error(self):
        text = "key1 = value1"
        with StringIO(text) as stream:
            with self.assertRaises(RFC822SyntaxError) as call:
                type(self).loader(stream)
            self.assertEqual(call.exception.msg, "Unexpected non-empty line")

    def test_duplicate_error(self):
        text = (
            "key1: value1\n"
            "key1: value2\n"
        )
        with StringIO(text) as stream:
            with self.assertRaises(RFC822SyntaxError) as call:
                type(self).loader(stream)
            self.assertEqual(call.exception.msg, (
                "Job has a duplicate key 'key1' with old value 'value1'"
                " and new value 'value2'"))


class RFC822ParserTests(TestCase, RFC822ParserTestsMixIn):

    pass


class RFC822WriterTests(TestCase):

    def test_single_record(self):
        with StringIO() as stream:
            dump_rfc822_records({'key': 'value'}, stream)
            self.assertEqual(stream.getvalue(), "key: value\n\n")

    def test_multiple_record(self):
        with StringIO() as stream:
            dump_rfc822_records({'key1': 'value1', 'key2': 'value2'}, stream)
            self.assertIn(
                stream.getvalue(), (
                    "key1: value1\nkey2: value2\n\n",
                    "key2: value2\nkey1: value1\n\n"))

    def test_multiline_value(self):
        text = (
            "key:\n"
            " longer\n"
            " value\n\n"
        )
        with StringIO() as stream:
            dump_rfc822_records({'key': 'longer\nvalue'}, stream)
            self.assertEqual(stream.getvalue(), text)

    def test_multiline_value_with_space(self):
        text = (
            "key:\n"
            " longer\n"
            " .\n"
            " value\n\n"
        )
        with StringIO() as stream:
            dump_rfc822_records({'key': 'longer\n\nvalue'}, stream)
            self.assertEqual(stream.getvalue(), text)

    def test_multiline_value_with_period(self):
        text = (
            "key:\n"
            " longer\n"
            " ..\n"
            " value\n\n"
        )
        with StringIO() as stream:
            dump_rfc822_records({'key': 'longer\n.\nvalue'}, stream)
            self.assertEqual(stream.getvalue(), text)

    def test_type_error(self):
        with StringIO() as stream:
            with self.assertRaises(AttributeError):
                dump_rfc822_records(['key', 'value'], stream)
