# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique  <roadmr@ubuntu.com>
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
plainbox.impl.exporter.test_text
================================

Test definitions for plainbox.impl.exporter.text module
"""

from io import BytesIO
from unittest import TestCase

from plainbox.impl.exporter.text import TextSessionStateExporter


class TextSessionStateExporterTests(TestCase):

    def test_default_dump(self):
        exporter = TextSessionStateExporter()
        # Text exporter expects this data format
        data = {'result_map': {'job_name': {'outcome': 'fail'}}}
        stream = BytesIO()
        exporter.dump(data, stream)
        expected_bytes = "job_name: fail".encode('utf-8')
        self.assertEqual(stream.getvalue(), expected_bytes)
