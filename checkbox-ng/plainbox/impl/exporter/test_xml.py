# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
plainbox.impl.exporter.test_xml
================================

Test definitions for plainbox.impl.exporter.xml module
"""
from unittest import TestCase
import io

from pkg_resources import resource_string

from plainbox.testing_utils import resource_json
from plainbox.impl.exporter.xml import XMLSessionStateExporter, XMLValidator


class XMLSessionStateExporterTests(TestCase):

    def setUp(self):
        self.stream = io.StringIO()

    def test_dump_with_io_log(self):
        exporter = XMLSessionStateExporter(
            system_id="DEADBEEF",
            timestamp="2012-12-21T12:00:00",
            client_version="1.0",
            client_name="plainbox")
        data = resource_json(
            "plainbox", "test-data/xml-exporter/test_dump_with_io_log.json")
        exporter.dump(data, self.stream)
        actual = self.stream.getvalue()
        expected = resource_string(
            "plainbox", "test-data/xml-exporter/test_dump_with_io_log.xml"
        ).decode("UTF-8")
        self.assertEqual(actual, expected)

    def test_dump_with_comments(self):
        exporter = XMLSessionStateExporter(
            system_id="DEADBEEF",
            timestamp="2012-12-21T12:00:00",
            client_version="1.0",
            client_name="plainbox")
        data = resource_json(
            "plainbox", "test-data/xml-exporter/test_dump_with_comments.json")
        expected = resource_string(
            "plainbox", "test-data/xml-exporter/test_dump_with_comments.xml"
        ).decode("UTF-8")
        exporter.dump(data, self.stream)
        actual = self.stream.getvalue()
        self.assertEqual(actual, expected)


class XMLExporterTests(TestCase):

    def setUp(self):
        data = resource_json(
            "plainbox", "test-data/xml-exporter/example-data.json",
            exact=True)
        exporter = XMLSessionStateExporter(
            system_id="TBD", timestamp="2012-12-21T12:00:00",
            client_version="1.0")
        stream = io.StringIO('wt')
        exporter.dump(data, stream)
        self.actual_result = stream.getvalue()
        self.assertIsInstance(self.actual_result, str)

    def test_perfect_match(self):
        expected_result = resource_string(
            "plainbox", "test-data/xml-exporter/example-data.xml"
        ).decode("UTF-8")
        self.assertEqual(self.actual_result, expected_result)

    def test_result_is_valid(self):
        validator = XMLValidator()
        # XXX: we need to pass bytes to the validator as it
        # reads the header to interpret the encoding= argument
        # there.
        self.assertTrue(
            validator.validate_text(
                self.actual_result.encode("UTF-8")))
