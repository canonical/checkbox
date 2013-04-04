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
plainbox.impl.exporter.test_rfc822
==================================

Test definitions for plainbox.impl.exporter.rfc822 module
"""

from io import BytesIO
from unittest import TestCase

from plainbox.impl.exporter.rfc822 import RFC822SessionStateExporter


class RFC822SessionStateExporterTests(TestCase):

    def test_dump(self):
        exporter = RFC822SessionStateExporter()
        # exporter expects this data format
        data = {'result_map': {'job_name': {'outcome': 'fail'}}}
        stream = BytesIO()
        exporter.dump(data, stream)
        expected_bytes = (
            "name: job_name\n"
            "outcome: fail\n"
            "\n"
        ).encode('UTF-8')
        self.assertEqual(stream.getvalue(), expected_bytes)
