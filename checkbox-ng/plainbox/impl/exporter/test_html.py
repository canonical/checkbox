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
from unittest import TestCase
import io

from plainbox.testing_utils import resource_json
from plainbox.impl.exporter.html import HTMLSessionStateExporter


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
        # A pretty simplistic test since we just validate the output
        # appears to be HTML. Looking at the exporter's code, it's mostly
        # boilerplate use of lxml and etree, so let's not fall into testing
        # an external library.
        self.assertIn(b"<html>",
                      self.actual_result)
        self.assertIn(b"<title>System Testing Report</title>",
                      self.actual_result)
