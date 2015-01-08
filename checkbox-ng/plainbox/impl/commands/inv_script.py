# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
:mod:`plainbox.impl.commands.inv_script` -- script sub-command
==============================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from logging import getLogger
from tempfile import TemporaryDirectory
import os

from plainbox.i18n import gettext as _
from plainbox.impl.applogic import get_matching_job_list
from plainbox.impl.commands.inv_checkbox import CheckBoxInvocationMixIn
from plainbox.impl.runner import JobRunner
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.qualifiers import JobIdQualifier
from plainbox.impl.session import JobState


logger = getLogger("plainbox.commands.script")


class ScriptInvocation(CheckBoxInvocationMixIn):
    """
    Helper class instantiated to perform a particular invocation of the script
    command. Unlike :class:`ScriptCommand` this class is instantiated each time
    the command is to be invoked.
    """

    def __init__(self, provider_loader, config_loader, job_id):
        super().__init__(provider_loader, config_loader)
        self.job_id = job_id

    def run(self):
        job = self._get_job()
        if job is None:
            print(_("There is no job called {!a}").format(self.job_id))
            print(_(
                "See `plainbox special --list-jobs` for a list of choices"))
            return 126
        elif job.command is None:
            print(_("Selected job does not have a command"))
            return 125
        with TemporaryDirectory() as scratch, TemporaryDirectory() as iologs:
            runner = JobRunner(scratch, self.provider_list, iologs)
            job_state = JobState(job)
            ctrl = runner._get_ctrl_for_job(job)
            runner.log_leftovers = False
            runner.on_leftover_files.connect(self._on_leftover_files)
            return_code, record_path = runner._run_command(
                job, job_state, self.config, ctrl)
            self._display_script_outcome(job, return_code)
        return return_code

    def _on_leftover_files(self, job, config, cwd_dir, leftovers):
        for item in leftovers:
            if os.path.isfile(item):
                self._display_file(item, cwd_dir)
            elif os.path.isdir(item):
                self._display_dir(item, cwd_dir)
            else:
                self._display_other(item, cwd_dir)

    def _display_file(self, pathname, origin):
        filename = os.path.relpath(pathname, origin)
        print(_("Leftover file detected: {!a}:").format(filename))
        with open(pathname, 'rt', encoding='UTF-8') as stream:
            for lineno, line in enumerate(stream, 1):
                line = line.rstrip('\n')
                print("  {}:{}: {}".format(filename, lineno, line))

    def _display_dir(self, pathname, origin):
        print(_("Leftover directory detected: {!a}").format(
            os.path.relpath(pathname, origin)))

    def _display_other(self, pathname, origin):
        print(_("Leftover thing detected: {!a}").format(
            os.path.relpath(pathname, origin)))

    def _display_script_outcome(self, job, return_code):
        print(_("job {} returned {}").format(job.id, return_code))
        print(_("command:"), job.command)

    def _get_job(self):
        job_list = get_matching_job_list(
            self.get_job_list(None),
            JobIdQualifier(self.job_id, Origin.get_caller_origin()))
        if len(job_list) == 0:
            return None
        else:
            return job_list[0]
