# This file is part of Checkbox.
#
# Copyright 2018 Canonical Ltd.
# Authors:
#     Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`checkbox-ng.launcher.merge_reports` -- merge-reports sub-command
======================================================================
"""
import json
import os
import tarfile
from tempfile import TemporaryDirectory

from plainbox.impl.ctrl import gen_rfc822_records_from_io_log
from plainbox.impl.providers.special import get_exporters
from plainbox.impl.resource import Resource
from plainbox.impl.result import IOLogRecord
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.session import SessionManager
from plainbox.impl.unit.category import CategoryUnit
from plainbox.impl.unit.job import JobDefinition


#: Name-space prefix for Canonical Certification
CERTIFICATION_NS = 'com.canonical.certification::'


class MergeReports():
    def register_arguments(self, parser):
        parser.add_argument(
            'submission', nargs='*', metavar='SUBMISSION',
            help='submission tarball')
        parser.add_argument(
            '-o', '--output-file', metavar='FILE', required=True,
            help='save combined test results to the specified FILE')

    def _parse_submission(self, submission, tmpdir, mode="list"):
        try:
            with tarfile.open(submission) as tar:
                tar.extractall(tmpdir.name)
                with open(os.path.join(
                          tmpdir.name, 'submission.json')) as f:
                    data = json.load(f)
            for result in data['results']:
                result['plugin'] = 'shell'  # Required so default to shell
                result['summary'] = result['name']
                # 'id' field in json file only contains partial id
                result['id'] = result.get('full_id', result['id'])
                if "::" not in result['id']:
                    result['id'] = CERTIFICATION_NS + result['id']
                if mode == "list":
                    self.job_list.append(JobDefinition(result))
                elif mode == "dict":
                    self.job_dict[result['id']] = JobDefinition(result)
            for result in data['resource-results']:
                result['plugin'] = 'resource'
                result['summary'] = result['name']
                # 'id' field in json file only contains partial id
                result['id'] = result.get('full_id', result['id'])
                if "::" not in result['id']:
                    result['id'] = CERTIFICATION_NS + result['id']
                if mode == "list":
                    self.job_list.append(JobDefinition(result))
                elif mode == "dict":
                    self.job_dict[result['id']] = JobDefinition(result)
            for result in data['attachment-results']:
                result['plugin'] = 'attachment'
                result['summary'] = result['name']
                # 'id' field in json file only contains partial id
                result['id'] = result.get('full_id', result['id'])
                if "::" not in result['id']:
                    result['id'] = CERTIFICATION_NS + result['id']
                if mode == "list":
                    self.job_list.append(JobDefinition(result))
                elif mode == "dict":
                    self.job_dict[result['id']] = JobDefinition(result)
            for cat_id, cat_name in data['category_map'].items():
                if mode == "list":
                    self.category_list.append(
                        CategoryUnit({'id': cat_id, 'name': cat_name}))
                elif mode == "dict":
                    self.category_dict[cat_id] = CategoryUnit(
                        {'id': cat_id, 'name': cat_name})
        except OSError as e:
            raise SystemExit(e)
        except KeyError as e:
            self._output_potential_action(str(e))
            raise SystemExit(e)
        return data['title']

    def _populate_session_state(self, job, state):
        io_log = [
            IOLogRecord(count, 'stdout', line.encode('utf-8'))
            for count, line in enumerate(
                job.get_record_value('io_log').splitlines(
                    keepends=True))
        ]
        result = MemoryJobResult({
            'outcome': job.get_record_value('outcome',
                                            job.get_record_value('status')),
            'comments': job.get_record_value('comments'),
            'execution_duration': job.get_record_value('duration'),
            'io_log': io_log,
        })
        state.update_job_result(job, result)
        if job.plugin == 'resource':
            new_resource_list = []
            for record in gen_rfc822_records_from_io_log(job, result):
                resource = Resource(record.data)
                new_resource_list.append(resource)
            if not new_resource_list:
                new_resource_list = [Resource({})]
            state.set_resource_list(job.id, new_resource_list)
        job_state = state.job_state_map[job.id]
        job_state.effective_category_id = job.get_record_value(
            'category_id', 'com.canonical.plainbox::uncategorised')
        job_state.effective_certification_status = job.get_record_value(
            'certification_status', 'unspecified')

    def _create_exporter(self, exporter_id):
        exporter_map = {}
        exporter_units = get_exporters().unit_list
        for unit in exporter_units:
            if unit.Meta.name == 'exporter':
                support = unit.support
                if support:
                    exporter_map[unit.id] = support
        exporter_support = exporter_map[exporter_id]
        return exporter_support.exporter_cls(
            [], exporter_unit=exporter_support)

    def _output_potential_action(self, message):
        hint = ""
        keys = ['resource', 'attachment']
        for key in keys:
            if key in message:
                hint = ("Make sure your input submission provides {}-related "
                        "information.".format(key))
        if hint:
            print("Fail to merge. " + hint)
        else:
            print("Fail to merge.")

    def invoked(self, ctx):
        manager_list = []
        for submission in ctx.args.submission:
            tmpdir = TemporaryDirectory()
            self.job_list = []
            self.category_list = []
            session_title = self._parse_submission(submission, tmpdir)
            manager = SessionManager.create_with_unit_list(
                self.job_list + self.category_list)
            manager.state.metadata.title = session_title
            for job in self.job_list:
                self._populate_session_state(job, manager.state)
            manager_list.append(manager)
        exporter = self._create_exporter(
            'com.canonical.plainbox::html-multi-page')
        with open(ctx.args.output_file, 'wb') as stream:
            exporter.dump_from_session_manager_list(manager_list, stream)
        print(ctx.args.output_file)
