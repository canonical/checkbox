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
from pathlib import Path
from tempfile import TemporaryDirectory

from checkbox_ng.launcher.merge_reports import MergeReports
from plainbox.impl.session import SessionManager


class MergeSubmissions(MergeReports):
    name = "merge-submissions"

    def register_arguments(self, parser):
        parser.add_argument(
            "submission",
            nargs="*",
            metavar="SUBMISSION",
            help="submission tarball",
        )
        parser.add_argument(
            "-o",
            "--output-file",
            metavar="FILE",
            required=True,
            help="save combined test results to the specified FILE",
        )
        parser.add_argument(
            "--title",
            action="store",
            metavar="SESSION_NAME",
            help="title of the session to use",
        )

    def export(self, manager, temp_dir, exporter):
        export_file = temp_dir / "submission.{}".format(exporter)
        exporter = self._create_exporter(
            "com.canonical.plainbox::{}".format(exporter)
        )
        with export_file.open("wb+") as f:
            exporter.dump_from_session_manager(manager, f)

    def invoked(self, ctx):
        tmpdir = TemporaryDirectory()
        self.job_dict = {}
        self.category_dict = {}
        self.system_information = {}
        for submission in ctx.args.submission:
            session_title = self._parse_submission(
                submission, tmpdir, mode="dict"
            )
        manager = SessionManager.create_with_unit_list(
            list(self.job_dict.values()) + list(self.category_dict.values())
        )
        manager.state.metadata.title = ctx.args.title or session_title
        for job in self.job_dict.values():
            self._populate_session_state(job, manager.state)
        for exporter in ["html", "json", "junit"]:
            self.export(manager, Path(tmpdir.name), exporter)
        # Note: This is not using the tar exporter but the 3 separate exporters
        #   instead because the tar exporter can't include the attachments and
        #   iologs in the generated submission (the session state is not fully
        #   recovered and its a mess to do, try it, you have to fix the
        #   io_log_filename for all non-in memory results!) Historically the
        #   solution here was to use tar and then unpack/include/repack, but
        #   that is twice as slow.
        with tarfile.open(ctx.args.output_file, mode="w:xz") as tar:
            tar.add(tmpdir.name, arcname="")
        print(ctx.args.output_file)
