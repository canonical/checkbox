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
:mod:`checkbox-ng.launcher.merge_submissions` -- merge-submissions sub-command
==============================================================================
"""
import json
import os
import tarfile
from tempfile import TemporaryDirectory

from guacamole import Command

from plainbox.impl.ctrl import gen_rfc822_records_from_io_log
from plainbox.impl.providers.special import get_exporters
from plainbox.impl.resource import Resource
from plainbox.impl.result import IOLogRecord
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.session import SessionManager
from plainbox.impl.unit.category import CategoryUnit
from plainbox.impl.unit.job import JobDefinition


class MergeSubmissions(Command):
    name = 'merge-submissions'

    def register_arguments(self, parser):
        parser.add_argument(
            'submission', nargs='*', metavar='SUBMISSION',
            help='submission tarball')
        parser.add_argument(
            '-o', '--output-file', metavar='FILE',
            help='save combined test results to the specified FILE')
        parser.add_argument(
            '--title', action='store', metavar='SESSION_NAME',
            help='title of the session to use')

    def invoked(self, ctx):
        tmpdir = TemporaryDirectory()
        jobs = {}
        categories = {}
        for submission in ctx.args.submission:
            try:
                with tarfile.open(submission) as tar:
                    tar.extractall(tmpdir.name)
                    with open(os.path.join(
                              tmpdir.name, 'submission.json')) as f:
                        data = json.load(f)
                for result in data['results']:
                    result['plugin'] = 'shell'  # Required so default to shell
                    result['summary'] = result['name']
                    jobs[result['id']] = JobDefinition(result)
                for result in data['resource-results']:
                    result['plugin'] = 'resource'
                    result['summary'] = result['name']
                    jobs[result['id']] = JobDefinition(result)
                for result in data['attachment-results']:
                    result['plugin'] = 'attachment'
                    result['summary'] = result['name']
                    jobs[result['id']] = JobDefinition(result)
                for cat_id, cat_name in data['category_map'].items():
                    categories[cat_id] = CategoryUnit(
                        {'id': cat_id, 'name': cat_name})
            except OSError as e:
                print(e)
                return 1
            except KeyError as e:
                print("Invalid JSON submission, missing key:", e)
                return 1
        manager = SessionManager.create_with_unit_list(
            list(jobs.values()) + list(categories.values()))
        manager.state.metadata.title = ctx.args.title or data['title']
        for job in jobs.values():
            io_log = [
                IOLogRecord(count, 'stdout', line.encode('utf-8'))
                for count, line in enumerate(
                    job.get_record_value('io_log').splitlines(
                        keepends=True))
            ]
            result = MemoryJobResult({
                'outcome': job.get_record_value('status'),
                'comments': job.get_record_value('comments'),
                'execution_duration': job.get_record_value('duration'),
                'io_log': io_log,
            })
            manager.state.update_job_result(job, result)
            if job.plugin == 'resource':
                new_resource_list = []
                for record in gen_rfc822_records_from_io_log(job, result):
                    resource = Resource(record.data)
                    new_resource_list.append(resource)
                if not new_resource_list:
                    new_resource_list = [Resource({})]
                manager.state.set_resource_list(
                    "com.canonical.certification::" + job.id,
                    new_resource_list)
            job_state = manager.state.job_state_map[job.id]
            job_state.effective_category_id = job.get_record_value(
                'category_id', 'com.canonical.plainbox::uncategorised')
        exporter_map = {}
        exporter_units = get_exporters().unit_list
        for unit in exporter_units:
            if unit.Meta.name == 'exporter':
                support = unit.support
                if support:
                    exporter_map[unit.id] = support
        exporter_support = exporter_map[
            'com.canonical.plainbox::tar']
        exporter = exporter_support.exporter_cls(
            [], exporter_unit=exporter_support)
        with open(ctx.args.output_file, 'wb') as stream:
            exporter.dump_from_session_manager(manager, stream)
        with tarfile.open(ctx.args.output_file) as tar:
            tar.extractall(tmpdir.name)
        with tarfile.open(ctx.args.output_file, mode='w:xz') as tar:
            tar.add(tmpdir.name, arcname='')
        print(ctx.args.output_file)
