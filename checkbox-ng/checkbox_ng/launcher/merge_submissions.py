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
import tarfile
from tempfile import TemporaryDirectory

from checkbox_ng.launcher.merge_reports import MergeReports
from plainbox.impl.session import SessionManager


class MergeSubmissions(MergeReports):
    name = 'merge-submissions'

    def register_arguments(self, parser):
        parser.add_argument(
            'submission', nargs='*', metavar='SUBMISSION',
            help='submission tarball')
        parser.add_argument(
            '-o', '--output-file', metavar='FILE',  required=True,
            help='save combined test results to the specified FILE')
        parser.add_argument(
            '--title', action='store', metavar='SESSION_NAME',
            help='title of the session to use')

    def invoked(self, ctx):
        tmpdir = TemporaryDirectory()
        self.job_dict = {}
        self.category_dict = {}
        for submission in ctx.args.submission:
            session_title = self._parse_submission(
                submission, tmpdir, mode='dict')
        manager = SessionManager.create_with_unit_list(
            list(self.job_dict.values()) + list(self.category_dict.values()))
        manager.state.metadata.title = ctx.args.title or session_title
        for job in self.job_dict.values():
            self._populate_session_state(job, manager.state)
        exporter = self._create_exporter(
            'com.canonical.plainbox::tar')
        with open(ctx.args.output_file, 'wb') as stream:
            exporter.dump_from_session_manager(manager, stream)
        with tarfile.open(ctx.args.output_file) as tar:
            tar.extractall(tmpdir.name)
        with tarfile.open(ctx.args.output_file, mode='w:xz') as tar:
            tar.add(tmpdir.name, arcname='')
        print(ctx.args.output_file)
