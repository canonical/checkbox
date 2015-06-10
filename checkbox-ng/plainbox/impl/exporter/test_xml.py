# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
plainbox.impl.exporter.test_xml
================================

Test definitions for plainbox.impl.exporter.xml module
"""

from lxml import etree
from unittest import TestCase
import io

from pkg_resources import resource_string

from plainbox.impl.exporter.xml import CONTROL_CODE_RE_STR
from plainbox.impl.exporter.xml import XMLSessionStateExporter, XMLValidator
from plainbox.testing_utils import resource_json
from plainbox.testing_utils.testcases import TestCaseWithParameters


class ControlCodeTests(TestCase):

    def test_lower_range__str(self):
        self.assertRegex('\u0000', CONTROL_CODE_RE_STR)
        self.assertRegex('\u001F', CONTROL_CODE_RE_STR)
        # The lower range spans from 0..0x20 (space), exclusive
        self.assertNotRegex('\u0020', CONTROL_CODE_RE_STR)

    def test_higher_range__str(self):
        self.assertNotRegex('\u007E', CONTROL_CODE_RE_STR)
        self.assertRegex('\u007F', CONTROL_CODE_RE_STR)
        self.assertRegex('\u001F', CONTROL_CODE_RE_STR)
        self.assertNotRegex('\u00A0', CONTROL_CODE_RE_STR)

    def test_explicitly_allowed__str(self):
        self.assertNotRegex(' ', CONTROL_CODE_RE_STR)
        self.assertNotRegex('\n', CONTROL_CODE_RE_STR)
        self.assertNotRegex('\r', CONTROL_CODE_RE_STR)
        self.assertNotRegex('\t', CONTROL_CODE_RE_STR)
        self.assertNotRegex('\v', CONTROL_CODE_RE_STR)


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


class XMLExporterTests(TestCase):

    def setUp(self):
        self.prepare_test_exporter()

    def prepare_test_exporter(self, client_name="plainbox",
                              system_id="",
                              option_list=None,
                              timestamp="2012-12-21T12:00:00",
                              client_version="1.0"):
        data = resource_json(
            "plainbox", "test-data/xml-exporter/example-data.json",
            exact=True)
        self.exporter = XMLSessionStateExporter(
            client_name=client_name,
            option_list=option_list,
            system_id=system_id,
            timestamp=timestamp,
            client_version=client_version)
        stream = io.BytesIO()
        self.exporter.dump(data, stream)
        self.actual_result = stream.getvalue()  # This is bytes
        self.assertIsInstance(self.actual_result, bytes)

    def test_exporter_option(self):
        """
        Ensure that the previously-optionless xml exporter can have its
        single accepted 'client-name' option set properly.
        """
        self.prepare_test_exporter(option_list=['client-name=verifythis'])
        self.assertEqual(
            self.exporter.get_option_value('client-name'), "verifythis")

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

    def test_questions_ordered_by_id(self):
        # parse self.actual_result
        root = etree.fromstring(self.actual_result)
        # Tests are called "questions" in xml
        questions = root.find("questions")
        # Ensure we only have one questions element
        self.assertNotIsInstance(questions, list)
        # Flatten each question to just their name attributes
        names = [ques.attrib.get('name', None) for ques in questions]
        # Ensure they are in order
        self.assertEqual(names, sorted(names))

    def test_client_name_option_takes_precedence(self):
        # We use trickery to verify the xml final report has the client name
        # sent in the option string, rather than the constructor parameter.
        # We pass a bogus client-name in the constructor, then the correct
        # expected name in the option, and just check as usual.
        self.prepare_test_exporter(client_name="bogus",
                                   option_list=['client-name=plainbox'])
        expected_result = resource_string(
            "plainbox", "test-data/xml-exporter/example-data.xml"
        )  # unintuitively, resource_string returns bytes
        self.assertEqual(self.actual_result, expected_result)
