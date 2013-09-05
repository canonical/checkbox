# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique <daniel.manrique@canonical.com>
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
plainbox.impl.exporter.test_html
================================

Test definitions for plainbox.impl.exporter.html module
"""
from io import StringIO
from string import Template
from unittest import TestCase
import io

from lxml import etree as ET
from pkg_resources import resource_filename
from pkg_resources import resource_string

from plainbox.testing_utils import resource_json
from plainbox.impl.exporter.html import HTMLResourceInliner
from plainbox.impl.exporter.html import HTMLSessionStateExporter


class HTMLInlinerTests(TestCase):
    def setUp(self):
        template_substitutions = {
            'PLAINBOX_ASSETS': resource_filename("plainbox", "data/")}
        test_file_location = "test-data/html-exporter/html-inliner.html"
        test_file = resource_filename("plainbox",
                                      test_file_location)
        with open(test_file) as html_file:
            html_template = Template(html_file.read())
        html_content = html_template.substitute(template_substitutions)
        self.tree = ET.parse(StringIO(html_content), ET.HTMLParser())
        # Now self.tree contains a tree with adequately-substituted
        # paths and resources
        inliner = HTMLResourceInliner()
        self.inlined_tree = inliner.inline_resources(self.tree)

    def test_script_inlining(self):
        """Test that a <script> resource gets inlined."""
        for node in self.inlined_tree.xpath('//script'):
            self.assertTrue(node.text)

    def test_img_inlining(self):
        """
        Test that a <img> gets inlined.
        It should be replaced by a base64 representation of the
        referenced image's data as per RFC2397.
        """
        for node in self.inlined_tree.xpath('//img'):
            # Skip image that purposefully points to a remote
            # resource
            if node.attrib.get('class') != "remote_resource":
                self.assertTrue("base64" in node.attrib['src'])

    def test_css_inlining(self):
        """Test that a <style> resource gets inlined."""
        for node in self.inlined_tree.xpath('//style'):
            # Skip a fake remote_resource node that's purposefully
            # not inlined
            if not 'nonexistent_resource' in node.attrib['type']:
                self.assertTrue("body" in node.text)

    def test_remote_resource_inlining(self):
        """
        Test that a resource with a non-local (i.e. not file://
        url) does NOT get inlined (rather it's replaced by an
        empty string). We use <style> in this test.
        """
        for node in self.inlined_tree.xpath('//style'):
            # The not-inlined remote_resource
            if 'nonexistent_resource' in node.attrib['type']:
                self.assertTrue(node.text == "")

    def test_unfindable_file_inlining(self):
        """
        Test that a resource whose file does not exist does NOT
        get inlined, and is instead replaced by empty string.
        We use <img> in this test.
        """
        for node in self.inlined_tree.xpath('//img'):
            if node.attrib.get('class') == "remote_resource":
                self.assertEqual("", node.attrib['src'])


class HTMLExporterTests(TestCase):

    def setUp(self):
        data = resource_json(
            "plainbox", "test-data/xml-exporter/example-data.json",
            exact=True)
        exporter = HTMLSessionStateExporter(
            system_id="",
            timestamp="2012-12-21T12:00:00",
            client_version="1.0")
        stream = io.BytesIO()
        exporter.dump(data, stream)
        self.actual_result = stream.getvalue()  # This is bytes
        self.assertIsInstance(self.actual_result, bytes)

    def test_html_output(self):
        """
        Test that output from the exporter is HTML (or at least,
        appears to be).
        """
        # A pretty simplistic test since we just validate the output
        # appears to be HTML. Looking at the exporter's code, it's mostly
        # boilerplate use of lxml and etree, so let's not fall into testing
        # an external library.
        self.assertIn(b"<html>",
                      self.actual_result)
        self.assertIn(b"<title>System Testing Report</title>",
                      self.actual_result)

    def test_perfect_match(self):
        """
        Test that output from the exporter exactly matches known
        good HTML output, inlining and everything included.
        """
        expected_result = resource_string(
            "plainbox", "test-data/html-exporter/example-data.html"
        )  # unintuitively, resource_string returns bytes
        self.assertEqual(self.actual_result, expected_result)
