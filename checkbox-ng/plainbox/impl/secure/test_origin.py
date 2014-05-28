# This file is part of Checkbox.
#
# Copyright 2013-2014 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
plainbox.impl.secure.test_origin
================================

Test definitions for plainbox.impl.secure.origin module
"""

from unittest import TestCase
import os

from plainbox.impl.secure.origin import FileTextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.origin import PythonFileTextSource
from plainbox.impl.secure.origin import UnknownTextSource


class UnknownTextSourceTests(TestCase):
    """
    Tests for UnknownTextSource class
    """

    def setUp(self):
        self.src = UnknownTextSource()

    def test_str(self):
        """
        verify how UnknownTextSource. __str__() works
        """
        self.assertEqual(str(self.src), "???")

    def test_repr(self):
        """
        verify how UnknownTextSource.__repr__() works
        """
        self.assertEqual(repr(self.src), "UnknownTextSource()")

    def test_eq(self):
        """
        verify instances of UnknownTextSource are all equal to each other
        but not equal to any other object
        """
        other_src = UnknownTextSource()
        self.assertTrue(self.src == other_src)
        self.assertFalse(self.src == "???")

    def test_eq_others(self):
        """
        verify instances of UnknownTextSource are unequal to instances of other
        classes
        """
        self.assertTrue(self.src != object())
        self.assertFalse(self.src == object())

    def test_gt(self):
        """
        verify that instances of UnknownTextSource are not ordered
        """
        other_src = UnknownTextSource()
        self.assertFalse(self.src < other_src)
        self.assertFalse(other_src < self.src)

    def test_gt_others(self):
        """
        verify that instances of UnknownTextSource are not comparable to other
        objects
        """
        with self.assertRaises(TypeError):
            self.src < object()
        with self.assertRaises(TypeError):
            object() < self.src


class FileTextSourceTests(TestCase):
    """
    Tests for FileTextSource class
    """

    _FILENAME = "filename"
    _CLS = FileTextSource

    def setUp(self):
        self.src = self._CLS(self._FILENAME)

    def test_filename(self):
        """
        verify that FileTextSource.filename works
        """
        self.assertEqual(self._FILENAME, self.src.filename)

    def test_str(self):
        """
        verify that FileTextSource.__str__() works
        """
        self.assertEqual(str(self.src), self._FILENAME)

    def test_repr(self):
        """
        verify that FileTextSource.__repr__() works
        """
        self.assertEqual(
            repr(self.src),
            "{}({!r})".format(self._CLS.__name__, self._FILENAME))

    def test_eq(self):
        """
        verify that FileTextSource compares equal to other instances with the
        same filename and unequal to instances with different filenames.
        """
        self.assertTrue(self._CLS('foo') == self._CLS('foo'))
        self.assertTrue(self._CLS('foo') != self._CLS('bar'))

    def test_eq_others(self):
        """
        verify instances of FileTextSource are unequal to instances of other
        classes
        """
        self.assertTrue(self._CLS('foo') != object())
        self.assertFalse(self._CLS('foo') == object())

    def test_gt(self):
        """
        verify that FileTextSource is ordered by filename
        """
        self.assertTrue(self._CLS("a") < self._CLS("b") < self._CLS("c"))
        self.assertTrue(self._CLS("c") > self._CLS("b") > self._CLS("a"))

    def test_gt_others(self):
        """
        verify that instances of FileTextSource are not comparable to other
        objects
        """
        with self.assertRaises(TypeError):
            self.src < object()
        with self.assertRaises(TypeError):
            object() < self.src

    def test_relative_to(self):
        """
        verify that FileTextSource.relative_to() works
        """
        self.assertEqual(
            self._CLS("/path/to/file.txt").relative_to("/path/to"),
            self._CLS("file.txt"))


class PythonFileTextSourceTests(FileTextSourceTests):
    """
    Tests for PythonFileTextSource class
    """

    _FILENAME = "filename.py"
    _CLS = PythonFileTextSource


class OriginTests(TestCase):
    """
    Tests for Origin class
    """

    def setUp(self):
        self.origin = Origin(FileTextSource("file.txt"), 10, 12)

    def test_smoke(self):
        """
        verify that all three instance attributes actually work
        """
        self.assertEqual(self.origin.source.filename, "file.txt")
        self.assertEqual(self.origin.line_start, 10)
        self.assertEqual(self.origin.line_end, 12)

    def test_repr(self):
        """
        verify that Origin.__repr__() works
        """
        expected = ("<Origin source:FileTextSource('file.txt')"
                    " line_start:10 line_end:12>")
        observed = repr(self.origin)
        self.assertEqual(expected, observed)

    def test_str(self):
        """
        verify that Origin.__str__() works
        """
        expected = "file.txt:10-12"
        observed = str(self.origin)
        self.assertEqual(expected, observed)

    def test_eq(self):
        """
        verify instances of Origin are all equal to other instances with the
        same instance attributes but not equal to instances with different
        attributes
        """
        origin1 = Origin(
            self.origin.source, self.origin.line_start, self.origin.line_end)
        origin2 = Origin(
            self.origin.source, self.origin.line_start, self.origin.line_end)
        self.assertTrue(origin1 == origin2)
        origin_other1 = Origin(
            self.origin.source, self.origin.line_start + 1,
            self.origin.line_end)
        self.assertTrue(origin1 != origin_other1)
        self.assertFalse(origin1 == origin_other1)
        origin_other2 = Origin(
            self.origin.source, self.origin.line_start,
            self.origin.line_end + 1)
        self.assertTrue(origin1 != origin_other2)
        self.assertFalse(origin1 == origin_other2)
        origin_other3 = Origin(
            FileTextSource("unrelated"), self.origin.line_start,
            self.origin.line_end)
        self.assertTrue(origin1 != origin_other3)
        self.assertFalse(origin1 == origin_other3)

    def test_eq_other(self):
        """
        verify instances of UnknownTextSource are unequal to instances of other
        classes
        """
        self.assertTrue(self.origin != object())
        self.assertFalse(self.origin == object())

    def test_gt(self):
        """
        verify that Origin instances are ordered by their constituting
        components
        """
        self.assertTrue(
            Origin(FileTextSource('file.txt'), 1, 1) <
            Origin(FileTextSource('file.txt'), 1, 2) <
            Origin(FileTextSource('file.txt'), 1, 3))
        self.assertTrue(
            Origin(FileTextSource('file.txt'), 1, 10) <
            Origin(FileTextSource('file.txt'), 2, 10) <
            Origin(FileTextSource('file.txt'), 3, 10))
        self.assertTrue(
            Origin(FileTextSource('file1.txt'), 1, 10) <
            Origin(FileTextSource('file2.txt'), 1, 10) <
            Origin(FileTextSource('file3.txt'), 1, 10))

    def test_gt_other(self):
        """
        verify that Origin instances are not comparable to other objects
        """
        with self.assertRaises(TypeError):
            self.origin < object()
        with self.assertRaises(TypeError):
            object() < self.origin

    def test_origin_caller(self):
        """
        verify that Origin.get_caller_origin() uses PythonFileTextSource as the
        origin.source attribute.
        """
        self.assertIsInstance(
            Origin.get_caller_origin().source, PythonFileTextSource)

    def test_origin_source_filename_is_correct(self):
        """
        verify that make_job() can properly trace the filename of the python
        module that called make_job()
        """
        # Pass -1 to get_caller_origin() to have filename point at this file
        # instead of at whatever ends up calling the test method
        self.assertEqual(
            os.path.basename(Origin.get_caller_origin(-1).source.filename),
            "test_origin.py")

    def test_relative_to(self):
        """
        verify how Origin.relative_to() works in various situations
        """
        # if the source does not have relative_to method, nothing is changed
        origin = Origin(UnknownTextSource(), 1, 2)
        self.assertIs(origin.relative_to("/some/path"), origin)
        # otherwise the source is replaced and a new origin is returned
        self.assertEqual(
            Origin(
                FileTextSource("/some/path/file.txt"), 1, 2
            ).relative_to("/some/path"),
            Origin(FileTextSource("file.txt"), 1, 2))
