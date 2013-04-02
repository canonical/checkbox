# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
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
plainbox.impl.exporter.test_json
================================

Test definitions for plainbox.impl.exporter.json module
"""

from unittest import TestCase
from io import BytesIO

from plainbox.impl.exporter.json import JSONSessionStateExporter


class JSONSessionStateExporterTests(TestCase):

    # It's kind of long to type over and over
    exporter_cls = JSONSessionStateExporter

    def test_supported_option_list(self):
        self.assertIn(self.exporter_cls.OPTION_MACHINE_JSON,
                      self.exporter_cls.supported_option_list)

    def test_default_dump(self):
        exporter = self.exporter_cls()
        data = {'foo': 'bar'}
        stream = BytesIO()
        exporter.dump(data, stream)
        self.assertEqual(stream.getvalue(), (
            '{\n'
            '    "foo": "bar"\n'
            '}').encode('utf-8'))

    def test_machine_dump(self):
        exporter = self.exporter_cls(option_list=[
            self.exporter_cls.OPTION_MACHINE_JSON])
        data = {'foo': 'bar'}
        stream = BytesIO()
        exporter.dump(data, stream)
        self.assertEqual(stream.getvalue(), '{"foo":"bar"}'.encode('utf-8'))
