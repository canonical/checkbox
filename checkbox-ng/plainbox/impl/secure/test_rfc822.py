# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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

"""
plainbox.impl.secure.test_rfc822
================================

Test definitions for plainbox.impl.secure.rfc822 module
"""

from io import StringIO
from unittest import TestCase

from plainbox.impl.secure.origin import FileTextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.origin import UnknownTextSource
from plainbox.impl.secure.rfc822 import RFC822Record
from plainbox.impl.secure.rfc822 import RFC822SyntaxError
from plainbox.impl.secure.rfc822 import load_rfc822_records
from plainbox.impl.secure.rfc822 import normalize_rfc822_value


class NormalizationTests(TestCase):
    """
    Tests for normalize_rfc822_value()
    """

    def test_smoke(self):
        n = normalize_rfc822_value
        self.assertEqual(n("foo"), "foo")
        self.assertEqual(n(" foo"), "foo")
        self.assertEqual(n("foo "), "foo")
        self.assertEqual(n(" foo "), "foo")
        self.assertEqual(n("  foo\n"
                           "  bar\n"),
                         ("foo\n"
                          "bar"))

    def test_dot_handling(self):
        n = normalize_rfc822_value
        # single leading dot is stripped
        self.assertEqual(n("foo\n"
                           ".\n"
                           "bar\n"),
                         ("foo\n"
                          "\n"
                          "bar"))
        # the dot is stripped even if whitespace is present
        self.assertEqual(n("  foo\n"
                           "  .\n"
                           "  bar\n"),
                         ("foo\n"
                          "\n"
                          "bar"))
        # Two dots don't invoke the special behaviour though
        self.assertEqual(n("  foo\n"
                           "  ..\n"
                           "  bar\n"),
                         ("foo\n"
                          "..\n"
                          "bar"))
        # Regardless of whitespace
        self.assertEqual(n("foo\n"
                           "..\n"
                           "bar\n"),
                         ("foo\n"
                          "..\n"
                          "bar"))


class RFC822RecordTests(TestCase):

    def setUp(self):
        self.raw_data = {'key': ' value'}
        self.data = {'key': 'value'}
        self.origin = Origin(FileTextSource('file.txt'), 1, 1)
        self.record = RFC822Record(self.data, self.origin, self.raw_data)

    def test_raw_data(self):
        self.assertEqual(self.record.raw_data, self.raw_data)

    def test_data(self):
        self.assertEqual(self.record.data, self.data)

    def test_origin(self):
        self.assertEqual(self.record.origin, self.origin)

    def test_equality(self):
        # Equality is compared by normalized data, the raw data doesn't count
        other_raw_data = {'key': 'value '}
        # This other raw data is actually different to the one we're going to
        # test against
        self.assertNotEqual(other_raw_data, self.raw_data)
        # Let's make another record with different raw data
        other_record = RFC822Record(self.data, self.origin, other_raw_data)
        # The normalized data is identical
        self.assertEqual(other_record.data, self.record.data)
        # The raw data is not
        self.assertNotEqual(other_record.raw_data, self.record.raw_data)
        # The origin is the same (just a sanity check)
        self.assertEqual(other_record.origin, self.record.origin)
        # Let's look at the whole object, they should be equal
        self.assertTrue(other_record == self.record)
        self.assertTrue(not(other_record != self.record))


class RFC822ParserTests(TestCase):

    loader = load_rfc822_records

    def test_empty(self):
        with StringIO("") as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 0)

    def test_parsing_strings_preserves_newlines(self):
        """
        Ensure that the special behavior, when a string is passed instead of a
        stream, is parsed the same way as regular streams are, that is, that
        newlines are preserved.
        """
        text = ("key:\n"
                " line1\n"
                " line2\n")
        records_str = type(self).loader(text)
        with StringIO(text) as stream:
            records_stream = type(self).loader(stream)
        self.assertEqual(records_str, records_stream)

    def test_preserves_whitespace1(self):
        with StringIO("key: value ") as stream:
            records = type(self).loader(stream)
        self.assertEqual(records[0].data, {'key': 'value'})
        self.assertEqual(records[0].raw_data, {'key': 'value '})

    def test_preserves_whitespace2(self):
        with StringIO("key:\n value ") as stream:
            records = type(self).loader(stream)
        self.assertEqual(records[0].data, {'key': 'value'})
        self.assertEqual(records[0].raw_data, {'key': 'value '})

    def test_strips_newlines1(self):
        with StringIO("key: value \n") as stream:
            records = type(self).loader(stream)
        self.assertEqual(records[0].data, {'key': 'value'})
        self.assertEqual(records[0].raw_data, {'key': 'value \n'})

    def test_strips_newlines2(self):
        with StringIO("key:\n value \n") as stream:
            records = type(self).loader(stream)
        self.assertEqual(records[0].data, {'key': 'value'})
        self.assertEqual(records[0].raw_data, {'key': 'value \n'})

    def test_single_record(self):
        with StringIO("key:value") as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': 'value'})
        self.assertEqual(records[0].raw_data, {'key': 'value'})

    def test_comments(self):
        """
        Ensure that comments are stripped and don't break multi-line handling
        """
        text = (
            "# this is a comment\n"
            "key:\n"
            " multi-line value\n"
            "# this is a comment\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': 'multi-line value'})
        self.assertEqual(records[0].raw_data, {'key': 'multi-line value\n'})

    def test_dot_escape(self):
        """
        Ensure that the dot is not processed in any way

        This part of the code is now handled by another layer.
        """
        text = (
            "key: something\n"
            " .\n"
            " .this\n"
            " ..should\n"
            " ...work\n"
        )
        expected_value = (
            "something\n"
            "\n"
            ".this\n"
            "..should\n"
            "...work"
        )
        expected_raw_value = (
            "something\n"
            ".\n"
            ".this\n"
            "..should\n"
            "...work\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': expected_value})
        self.assertEqual(records[0].raw_data, {'key': expected_raw_value})

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
        self.assertEqual(records[0].raw_data, {'key1': 'value1\n'})
        self.assertEqual(records[1].raw_data, {'key2': 'value2\n'})
        self.assertEqual(records[2].raw_data, {'key3': 'value3\n'})

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
        self.assertEqual(records[0].raw_data, {'key1': 'value1\n'})
        self.assertEqual(records[1].raw_data, {'key2': 'value2\n'})
        self.assertEqual(records[2].raw_data, {'key3': 'value3\n'})

    def test_multiline_value(self):
        text = (
            "key:\n"
            " longer\n"
            " value\n"
        )
        expected_value = (
            "longer\n"
            "value"
        )
        expected_raw_value = (
            "longer\n"
            "value\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': expected_value})
        self.assertEqual(records[0].raw_data, {'key': expected_raw_value})

    def test_multiline_value_with_space(self):
        text = (
            "key:\n"
            " longer\n"
            " .\n"
            " value\n"
        )
        expected_value = (
            "longer\n"
            "\n"
            "value"
        )
        expected_raw_value = (
            "longer\n"
            ".\n"
            "value\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': expected_value})
        self.assertEqual(records[0].raw_data, {'key': expected_raw_value})

    def test_multiline_value_with_space__deep_indent(self):
        """
        Ensure that equally indented spaces are removed, even if multiple
        spaces are used (more than one that is typically removed). The raw
        value should have just the one space removed
        """
        text = (
            "key:\n"
            "       longer\n"
            "       .\n"
            "       value\n"
        )
        expected_value = (
            "longer\n"
            "\n"
            "value"
        )
        # HINT: exactly as the original above but one space shorter
        expected_raw_value = (
            "      longer\n"
            "      .\n"
            "      value\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': expected_value})
        self.assertEqual(records[0].raw_data, {'key': expected_raw_value})

    def test_multiline_value_with_period(self):
        """
        Ensure that the dot is not processed in any way

        This part of the code is now handled by another layer.
        """
        text = (
            "key:\n"
            " longer\n"
            " ..\n"
            " value\n"
        )
        expected_value = (
            "longer\n"
            "..\n"
            "value"
        )
        expected_raw_value = (
            "longer\n"
            "..\n"
            "value\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': expected_value})
        self.assertEqual(records[0].raw_data, {'key': expected_raw_value})

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
        expected_value1 = (
            "initial\n"
            "longer\n"
            "value 1"
        )
        expected_value2 = (
            "longer\n"
            "value 2"
        )
        expected_raw_value1 = (
            "initial\n"
            "longer\n"
            "value 1\n"
        )
        expected_raw_value2 = (
            "longer\n"
            "value 2\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].data, {'key1': expected_value1})
        self.assertEqual(records[1].data, {'key2': expected_value2})
        self.assertEqual(records[0].raw_data, {'key1': expected_raw_value1})
        self.assertEqual(records[1].raw_data, {'key2': expected_raw_value2})

    def test_proper_parsing_nested_multiline(self):
        text = (
            "key:\n"
            " nested: stuff\n"
            " even:\n"
            "  more\n"
            "  text\n"
        )
        expected_value = (
            "nested: stuff\n"
            "even:\n"
            " more\n"
            " text"
        )
        expected_raw_value = (
            "nested: stuff\n"
            "even:\n"
            " more\n"
            " text\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': expected_value})
        self.assertEqual(records[0].raw_data, {'key': expected_raw_value})

    def test_proper_parsing_nested_multiline__deep_indent(self):
        text = (
            "key:\n"
            "        nested: stuff\n"
            "        even:\n"
            "           more\n"
            "           text\n"
        )
        expected_value = (
            "nested: stuff\n"
            "even:\n"
            "   more\n"
            "   text"
        )
        # HINT: exactly as the original above but one space shorter
        expected_raw_value = (
            "       nested: stuff\n"
            "       even:\n"
            "          more\n"
            "          text\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': expected_value})
        self.assertEqual(records[0].raw_data, {'key': expected_raw_value})

    def test_irrelevant_whitespace(self):
        text = "key :  value  "
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': 'value'})
        self.assertEqual(records[0].raw_data, {'key': 'value  '})

    def test_relevant_whitespace(self):
        text = (
            "key:\n"
            " value\n"
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': 'value'})
        self.assertEqual(records[0].raw_data, {'key': 'value\n'})

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
        self.assertEqual(
            call.exception.msg,
            "Unexpected non-empty line: 'garbage'")

    def test_syntax_error(self):
        text = "key1 = value1"
        with StringIO(text) as stream:
            with self.assertRaises(RFC822SyntaxError) as call:
                type(self).loader(stream)
        self.assertEqual(
            call.exception.msg,
            "Unexpected non-empty line: 'key1 = value1'")

    def test_duplicate_error(self):
        text = (
            "key1: value1\n"
            "key1: value2\n"
        )
        with StringIO(text) as stream:
            with self.assertRaises(RFC822SyntaxError) as call:
                type(self).loader(stream)
            self.assertEqual(call.exception.msg, (
                "Job has a duplicate key 'key1' with old value 'value1\\n'"
                " and new value 'value2\\n'"))

    def test_origin_from_stream_is_Unknown(self):
        """
        verify that gen_rfc822_records() uses origin instances with source
        equal to UnknownTextSource, when no explicit source is provided and the
        stream has no name to infer a FileTextSource() from.
        """
        expected_origin = Origin(UnknownTextSource(), 1, 1)
        with StringIO("key:value") as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': 'value'})
        self.assertEqual(records[0].origin, expected_origin)

    def test_origin_from_filename_is_filename(self):
        # If the test's origin has a filename, we need a valid origin
        # with proper data.
        # We're faking the name by using a StringIO subclass with a
        # name property, which is how rfc822 gets that data.
        expected_origin = Origin(FileTextSource("file.txt"), 1, 1)
        with NamedStringIO("key:value",
                           fake_filename="file.txt") as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].data, {'key': 'value'})
        self.assertEqual(records[0].origin, expected_origin)

    def test_field_offset_map_is_computed(self):
        text = (
            "a: value-a\n"  # offset 0
            "b: value-b\n"  # offset 1
            "# comment\n"   # offset 2
            "c:\n"          # offset 3
            " value-c.1\n"  # offset 4
            " value-c.2\n"  # offset 5
            "\n"
            "d: value-d\n"  # offset 0
        )
        with StringIO(text) as stream:
            records = type(self).loader(stream)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].data, {
            'a': 'value-a',
            'b': 'value-b',
            'c': 'value-c.1\nvalue-c.2',
        })
        self.assertEqual(records[0].field_offset_map, {
            'a': 0,
            'b': 1,
            'c': 4,
        })
        self.assertEqual(records[1].data, {
            'd': 'value-d',
        })
        self.assertEqual(records[1].field_offset_map, {
            'd': 0,
        })


class NamedStringIO(StringIO):
    """
     Subclass of StringIO with a name attribute.
     Use only for testing purposes, it's not guaranteed to be 100%
     compatible with StringIO.
    """
    def __init__(self, string, fake_filename=None):
        super(NamedStringIO, self).__init__(string)
        self._fake_filename = fake_filename

    @property
    def name(self):
        return(self._fake_filename)


class RFC822WriterTests(TestCase):
    """
    Tests for the :meth:`RFC822Record.dump()` method.
    """

    def test_single_record(self):
        with StringIO() as stream:
            RFC822Record({'key': 'value'}).dump(stream)
            self.assertEqual(stream.getvalue(), "key: value\n\n")

    def test_multiple_record(self):
        with StringIO() as stream:
            RFC822Record({'key1': 'value1', 'key2': 'value2'}).dump(stream)
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
            RFC822Record({'key': 'longer\nvalue'}).dump(stream)
            self.assertEqual(stream.getvalue(), text)

    def test_multiline_value_with_space(self):
        text = (
            "key:\n"
            " longer\n"
            " .\n"
            " value\n\n"
        )
        with StringIO() as stream:
            RFC822Record({'key': 'longer\n\nvalue'}).dump(stream)
            self.assertEqual(stream.getvalue(), text)

    def test_multiline_value_with_period(self):
        text = (
            "key:\n"
            " longer\n"
            " ..\n"
            " value\n\n"
        )
        with StringIO() as stream:
            RFC822Record({'key': 'longer\n.\nvalue'}).dump(stream)
            self.assertEqual(stream.getvalue(), text)

    def test_type_error(self):
        with StringIO() as stream:
            with self.assertRaises(AttributeError):
                RFC822Record(['key', 'value']).dump(stream)


class RFC822SyntaxErrorTests(TestCase):
    """
    Tests for RFC822SyntaxError class
    """

    def test_hash(self):
        """
        verify that RFC822SyntaxError is hashable
        """
        self.assertEqual(
            hash(RFC822SyntaxError("file.txt", 10, "msg")),
            hash(RFC822SyntaxError("file.txt", 10, "msg")))
