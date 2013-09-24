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

from plainbox.abc import IJobResult
from plainbox.testing_utils import resource_json
from plainbox.impl.exporter.xml import XMLSessionStateExporter, XMLValidator
from plainbox.testing_utils.testcases import TestCaseWithParameters


class XMLSessionStateExporterTests(TestCaseWithParameters):

    parameter_names = ('dump_with',)
    parameter_values = (('io_log',),
                        ('comments',),
                        ('text_attachment',),
                        ('binary_attachment',),
                        ('hardware_info',))

    def setUp(self):
        self.stream = io.BytesIO()

    def test_dump(self):
        exporter = XMLSessionStateExporter(
            system_id="DEADBEEF",
            timestamp="2012-12-21T12:00:00",
            client_version="1.0",
            client_name="plainbox")
        basename = "test-data/xml-exporter/test_dump_with_"
        data = resource_json(
            "plainbox",
            "{0}{1}.json".format(basename, self.parameters.dump_with))
        expected = resource_string(
            "plainbox",
            "{0}{1}.xml".format(basename, self.parameters.dump_with)
        )  # resource_string unintuitively returns bytes
        exporter.dump(data, self.stream)
        actual = self.stream.getvalue()
        self.assertEqual(actual, expected)


class XMLExporterStatusMappingTests(TestCaseWithParameters):

    parameter_names = ('checkbox_status',)
    parameter_values = [(outcome, ) for outcome in IJobResult.ALL_OUTCOME_LIST]

    def test_status_mapping(self):
        """
        Ensure that all possible plainbox statuses are mapped to
        one of the possible ALLOWED_STATUS permitted by checkbox
        legacy infrastructure.
        """
        pb_outcome = self.parameters.checkbox_status
        self.assertIn(pb_outcome, XMLSessionStateExporter._STATUS_MAP)
        mapped_status = XMLSessionStateExporter._STATUS_MAP[pb_outcome]
        self.assertIn(mapped_status,
                      XMLSessionStateExporter._ALLOWED_STATUS)


class XMLExporterTests(TestCase):

    def setUp(self):
        data = resource_json(
            "plainbox", "test-data/xml-exporter/example-data.json",
            exact=True)
        exporter = XMLSessionStateExporter(
            system_id="",
            timestamp="2012-12-21T12:00:00",
            client_version="1.0")
        stream = io.BytesIO()
        exporter.dump(data, stream)
        self.actual_result = stream.getvalue()  # This is bytes
        self.assertIsInstance(self.actual_result, bytes)

    def test_perfect_match(self):
        expected_result = resource_string(
            "plainbox", "test-data/xml-exporter/example-data.xml"
        )  # unintuitively, resource_string returns bytes
        self.assertEqual(self.actual_result, expected_result)

    def test_result_is_valid(self):
        validator = XMLValidator()
        # XXX: we need to pass bytes to the validator as it
        # reads the header to interpret the encoding= argument
        # there.
        self.assertTrue(
            validator.validate_text(
                self.actual_result))
