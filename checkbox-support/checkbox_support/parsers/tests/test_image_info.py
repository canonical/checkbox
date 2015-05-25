# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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

"""Tests for the image_info parsers."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from io import StringIO
from unittest import TestCase

from checkbox_support.parsers.image_info import (
    BuildstampParser,
    ImageInfoResult)


class TestBuildstampParser(TestCase):

    """Tests for Buildstamp parser class."""

    def _bogus_test(self, string):
        """
        Helper to test for bogus data.

        It checks that the given string does NOT produce a valid buildstamp.
        """
        stream = StringIO(string)
        self.parser = BuildstampParser(stream)
        result = ImageInfoResult()
        self.parser.run(result)
        self.assertNotIn("buildstamp", result.image_info)

    def test_one_line(self):
        """A one-line attachment is bogus, no result."""
        self._bogus_test("bogus\n")

    def test_two_lines_bogus(self):
        """A two-line attachment (empty second line) is bogus, no result."""
        self._bogus_test("bogus\n\n")

    def test_three_lines(self):
        """A three-line attachment is bogus, no result."""
        self._bogus_test("bogus\nwith-tree\nlines")

    def test_many_lines_empty_line(self):
        """Attachment with some empty lines is mostly good, get a result."""
        stream = StringIO("bogus\nwith-tree\n\n\n")
        self.parser = BuildstampParser(stream)
        result = ImageInfoResult()
        self.parser.run(result)
        self.assertIn("buildstamp", result.image_info)

    def test_two_lines_good(self):
        """A three-line attachment is good, check expected value."""
        stream = StringIO("kakaduplum Tue, 12 May 2015 06:46:55 +0000\n"
                          "somerville-trusty-amd64-osp1-20150512-0")
        self.parser = BuildstampParser(stream)
        result = ImageInfoResult()
        self.parser.run(result)
        self.assertIn("buildstamp", result.image_info)
        self.assertEqual("somerville-trusty-amd64-osp1-20150512-0",
                         result.image_info["buildstamp"])
