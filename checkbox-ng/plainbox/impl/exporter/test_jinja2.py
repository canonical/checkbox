# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
plainbox.impl.exporter.test_jinja2
==================================

Test definitions for plainbox.impl.exporter.jinja2 module
"""

from io import BytesIO
from tempfile import TemporaryDirectory
from textwrap import dedent
from unittest import TestCase
import os

from plainbox.impl.exporter.jinja2 import Jinja2SessionStateExporter
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.unit.exporter import ExporterUnitSupport
from plainbox.impl.unit.job import JobDefinition
from plainbox.vendor import mock


class Jinja2SessionStateExporterTests(TestCase):
    def setUp(self):
        self.prepare_manager_single_job()

    def prepare_manager_single_job(self):
        result = mock.Mock(spec_set=MemoryJobResult, outcome='fail',
                           is_hollow=False)
        result.tr_outcome.return_value = 'fail'
        job = mock.Mock(spec_set=JobDefinition, id='job_id')
        job.tr_summary.return_value = 'job name'
        self.manager_single_job = mock.Mock(state=mock.Mock(
            run_list=[job],
            job_state_map={
                job.id: mock.Mock(result=result, job=job)
            })
        )

    def test_template(self):
        with TemporaryDirectory() as tmp:
            template_filename = 'template.html'
            pathname = os.path.join(tmp, template_filename)
            tmpl = dedent(
                "{% for job in manager.state.job_state_map %}"
                "{{'{:^15}: {}'.format("
                "manager.state.job_state_map[job].result.tr_outcome(),"
                "manager.state.job_state_map[job].job.tr_summary()) }}\n"
                "{% endfor %}")
            data = {"template": template_filename, "extra_paths": [tmp]}
            exporter_unit = mock.Mock(spec_set=ExporterUnitSupport, data=data)
            exporter_unit.data_dir = tmp
            exporter_unit.template = template_filename
            with open(pathname, 'w') as f:
                f.write(tmpl)
            exporter = Jinja2SessionStateExporter(exporter_unit=exporter_unit)
            stream = BytesIO()
            exporter.dump_from_session_manager(self.manager_single_job, stream)
            expected_bytes = '     fail      : job name\n'.encode('UTF-8')
            self.assertEqual(stream.getvalue(), expected_bytes)
