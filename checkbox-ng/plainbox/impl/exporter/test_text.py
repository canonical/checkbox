# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Daniel Manrique  <roadmr@ubuntu.com>
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
plainbox.impl.exporter.test_text
================================

Test definitions for plainbox.impl.exporter.text module
"""

from io import BytesIO
from unittest import TestCase

from plainbox.impl.exporter.text import TextSessionStateExporter
from plainbox.vendor import mock


class TextSessionStateExporterTests(TestCase):

    def test_default_dump(self):
        exporter = TextSessionStateExporter(color=False)
        # Text exporter expects this data format
        result = mock.Mock(result='fail', is_hollow=False)
        result.tr_outcome.return_value = 'fail'
        job = mock.Mock(id='job_id')
        job.tr_summary.return_value = 'job name'
        data = mock.Mock(
            run_list=[job],
            job_state_map={
                job.id: mock.Mock(result=result, job=job, result_history=())
            }
        )
        stream = BytesIO()
        exporter.dump(data, stream)
        expected_bytes = '     fail      : job name\n'.encode('UTF-8')
        self.assertEqual(stream.getvalue(), expected_bytes)
