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
    RecoveryInfoParser,
    BtoParser,
    BtoInfoResult,
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


class TestRecoveryInfoParser(TestCase):

    """Tests for Recovery Info parser class."""

    def _result_for(self, string):
        """Helper to run string through the parser and return result."""
        stream = StringIO(string)
        self.parser = RecoveryInfoParser(stream)
        result = ImageInfoResult()
        self.parser.run(result)
        return result

    def test_bad_data(self):
        """A bad attachment is bogus, no result."""
        result = self._result_for("bogus\nlorem\nreally bad\n")
        self.assertNotIn("image_version", result.image_info)
        self.assertNotIn("bto_version", result.image_info)

    def test_tricky_data(self):
        """A validly-formatted attachment with wrong keys. No result."""
        result = self._result_for("key: value\nkey2: value2")
        self.assertNotIn("image_version", result.image_info)
        self.assertNotIn("bto_version", result.image_info)

    def test_empty_data(self):
        """Attachment with good keys but no data. No result."""
        result = self._result_for("image_version: \nbto_version:   \n")
        self.assertNotIn("image_version", result.image_info)
        self.assertNotIn("bto_version", result.image_info)

    def test_good_data(self):
        """A good and complete attachment, check expected value."""
        result = self._result_for(
            "image_version: somerville-trusty-amd64-osp1-20150512-0\n"
            "bto_version: "
            "A00_dell-bto-trusty-miramar-15-17-X01-iso-20150521-0.iso")
        self.assertIn("image_version", result.image_info)
        self.assertEqual("somerville-trusty-amd64-osp1-20150512-0",
                         result.image_info["image_version"])
        self.assertIn("bto_version", result.image_info)
        self.assertEqual(
            "A00_dell-bto-trusty-miramar-15-17-X01-iso-20150521-0.iso",
            result.image_info["bto_version"])

    def test_good_partial_data_image(self):
        """A good attachment with only image_version, check expected value."""
        result = self._result_for(
            "image_version: somerville-trusty-amd64-osp1-20150512-0\n"
            "bogus: chogus.iso")
        self.assertIn("image_version", result.image_info)
        self.assertEqual("somerville-trusty-amd64-osp1-20150512-0",
                         result.image_info["image_version"])
        self.assertNotIn("bto_version", result.image_info)

    def test_good_partial_data_bto(self):
        """A good attachment with only bto_version, check expected value."""
        result = self._result_for(
            "bogus: bogon\n"
            "bto_version: "
            "A00_dell-bto-trusty-miramar-15-17-X01-iso-20150521-0.iso")
        self.assertNotIn("image_version", result.image_info)
        self.assertIn("bto_version", result.image_info)
        self.assertEqual(
            "A00_dell-bto-trusty-miramar-15-17-X01-iso-20150521-0.iso",
            result.image_info["bto_version"])


BTO1 = """\
<?xml version="1.0" encoding="utf-8"?><bto>
  <date>2015-05-21</date>
  <versions>
    <os/>
    <iso>A00_dell-bto-trusty-miramar-15-17-X01-iso-20150521-0.iso</iso>
    <generator>1.24.3~somerville11</generator>
    <bootstrap>1.36~somerville3</bootstrap>
    <ubiquity>2.18.8.8kittyhawk1somerville3</ubiquity>
  </versions>
  <base>somerville-trusty-amd64-osp1-iso-20150512-0.iso</base>
  <fid>
    <git_tag/>
    <deb_archive/>
  </fid>
  <fish>
    <driver md5="ed884782d541974e2a887d6523778656">libcuda1-346_346.59-0ubuntu1somerville1_amd64.deb</driver>
    <driver md5="f536d125300b29ccd4d17f585fc9a20d">nvidia-libopencl1-346_346.59-0ubuntu1somerville1_amd64.deb</driver>
  </fish>
  <logs>
    <syslog>blah</syslog>
  </logs>
</bto>
"""

BTO2 = """\
<?xml version="1.0" encoding="utf-8"?><bto>
  <date>2015-05-21</date>
  <versions>
    <os/>
  </versions>
  <foo>
    <bar>baz</bar>
  </foo>
</bto>
"""

BTO3 = """\
<?xml version="1.0" encoding="utf-8"?><bto>
  <date>2015-05-21</date>
  <versions>
    <os/>
    <iso></iso>
    <generator>1.24.3~somerville11</generator>
  </versions>
  <base/>
  <fish>
    <driver/>
    <driver md5="f536d125300b29ccd4d17f585fc9a20d">boo.deb</driver>
    <driver md5="f536d125300b29ccd4d17f585fc9a20a">choo.deb</driver>
  </fish>
</bto>
"""


class TestBtoParser(TestCase):

    """Tests for BTO data parser class."""

    def _result_for(self, string):
        """Helper to run string through the parser and return result."""
        stream = StringIO(string)
        self.parser = BtoParser(stream)
        result = BtoInfoResult()
        self.parser.run(result)
        return result

    def test_bad_data(self):
        """A bad attachment is bogus, no result."""
        result = self._result_for("bogus\nlorem\nreally bad\n")
        self.assertEqual({}, result.bto_info)

    def test_bogus_xml(self):
        """A xml with values we don't want is bogus, no result."""
        result = self._result_for(BTO2)
        self.assertEqual({}, result.bto_info)

    def test_tricky_xml(self):
        """A xml with mix of keys we want and empty values, partial result."""
        result = self._result_for(BTO3)
        self.assertDictEqual(
            {'generator': '1.24.3~somerville11',
             'driver': ['boo.deb', 'choo.deb']},
            result.bto_info)

    def test_good_data(self):
        """A good and complete xml, check expected value."""
        result = self._result_for(BTO1)
        expected_dict = {
            'base': 'somerville-trusty-amd64-osp1-iso-20150512-0.iso',
            'bootstrap': '1.36~somerville3',
            'driver': [
                'libcuda1-346_346.59-0ubuntu1somerville1_amd64.deb',
                'nvidia-libopencl1-346_346.59-0ubuntu1somerville1_amd64.deb'],
            'generator': '1.24.3~somerville11',
            'iso': 'A00_dell-bto-trusty-miramar-15-17-X01-iso-20150521-0.iso',
            'ubiquity': '2.18.8.8kittyhawk1somerville3'}
        self.assertDictEqual(expected_dict, result.bto_info)
