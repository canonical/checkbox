# This file is part of Checkbox.
#
# Copyright 2012-2018 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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

import collections
import datetime
import logging
import sys

from plainbox.abc import IJobRunnerUI
from plainbox.i18n import gettext as _
from plainbox.impl.color import Colorizer


logger = logging.getLogger("checkbox-ng.launcher.run")


Action = collections.namedtuple("Action", "accel label cmd")


class ActionUI:
    """
    A simple user interface to display a list of actions and let the user to
    pick one
    """

    def __init__(self, action_list, prompt=None, color=None):
        """
        :param action_list:
            A list of 3-tuples (accel, label, cmd)
        :prompt:
            An optional prompt string
        :returns:
            cmd of the selected action or None
        """
        if prompt is None:
            prompt = _("Pick an action")
        self.action_list = action_list
        self.prompt = prompt
        self.C = Colorizer(color)

    def run(self):
        long_hint = "\n".join(
            "  {accel} => {label}".format(
                accel=self.C.BLUE(action.accel) if action.accel else ' ',
                label=action.label)
            for action in self.action_list)
        short_hint = ''.join(action.accel for action in self.action_list)
        while True:
            try:
                print(self.C.BLUE(self.prompt))
                print(long_hint)
                choice = input("[{}]: ".format(self.C.BLUE(short_hint)))
            except EOFError:
                return None
            else:
                for action in self.action_list:
                    if choice == action.accel or choice == action.label:
                        return action.cmd


class SilentUI(IJobRunnerUI):

    def considering_job(self, job, job_state):
        pass

    def about_to_start_running(self, job, job_state):
        pass

    def wait_for_interaction_prompt(self, job):
        pass

    def started_running(self, job, job_state):
        pass

    def about_to_execute_program(self, args, kwargs):
        pass

    def finished_executing_program(self, returncode):
        pass

    def got_program_output(self, stream_name, line):
        pass

    def finished_running(self, job, job_state, job_result):
        pass

    def notify_about_description(self, job):
        pass

    def notify_about_purpose(self, job):
        pass

    def notify_about_steps(self, job):
        pass

    def notify_about_verification(self, job):
        pass

    def job_cannot_start(self, job, job_state, job_result):
        pass

    def finished(self, job, job_state, job_result):
        pass

    def pick_action_cmd(self, action_list, prompt=None):
        pass

    def noreturn_job(self):
        pass


class NormalUI(IJobRunnerUI):

    STREAM_MAP = {
        'stdout': sys.stdout,
        'stderr': sys.stderr
    }

    def __init__(self, color, show_cmd_output=True):
        self.show_cmd_output = show_cmd_output
        self.C = Colorizer(color)
        self._color = color

    def considering_job(self, job, job_state):
        print(self.C.header(job.tr_summary(), fill='-'))
        print(_("ID: {0}").format(job.id))
        print(_("Category: {0}").format(job_state.effective_category_id))

    def about_to_start_running(self, job, job_state):
        pass

    def wait_for_interaction_prompt(self, job):
        return self.pick_action_cmd([
            Action('', _("press ENTER to continue"), 'run'),
            Action('c', _('add a comment'), 'comment'),
            Action('s', _("skip this job"), 'skip'),
            Action('q', _("save the session and quit"), 'quit')
        ])

    def started_running(self, job, job_state):
        pass

    def about_to_execute_program(self, args, kwargs):
        if self.show_cmd_output:
            print(self.C.BLACK("... 8< -".ljust(80, '-')))
        else:
            print(self.C.BLACK("(" + _("Command output hidden") + ")"))

    def got_program_output(self, stream_name, line):
        if not self.show_cmd_output:
            return
        stream = self.STREAM_MAP[stream_name]
        stream = {
            'stdout': sys.stdout,
            'stderr': sys.stderr
        }[stream_name]
        try:
            if stream_name == 'stdout':
                print(self.C.GREEN(line.decode("UTF-8")),
                      end='', file=stream)
            elif stream_name == 'stderr':
                print(self.C.RED(line.decode("UTF-8")),
                      end='', file=stream)
        except UnicodeDecodeError:
            self.show_cmd_output = False
            print(self.C.BLACK("(" + _("Hiding binary test output") + ")"))
        stream.flush()

    def finished_executing_program(self, returncode):
        if self.show_cmd_output:
            print(self.C.BLACK("- >8 ---".rjust(80, '-')))

    def finished_running(self, job, state, result):
        pass

    def notify_about_description(self, job):
        if job.tr_description() is not None:
            print(self.C.CYAN(job.tr_description()))

    def notify_about_purpose(self, job):
        if job.tr_purpose() is not None:
            print(self.C.WHITE(_("Purpose:")))
            print()
            print(self.C.CYAN(job.tr_purpose()))
            print()
        else:
            self.notify_about_description(job)

    def notify_about_steps(self, job):
        if job.tr_steps() is not None:
            print(self.C.WHITE(_("Steps:")))
            print()
            print(self.C.CYAN(job.tr_steps()))
            print()

    def notify_about_verification(self, job):
        if job.tr_verification() is not None:
            print(self.C.WHITE(_("Verification:")))
            print()
            print(self.C.CYAN(job.tr_verification()))
            print()

    def job_cannot_start(self, job, job_state, result):
        print(_("Job cannot be started because:"))
        for inhibitor in job_state.readiness_inhibitor_list:
            print(" - {}".format(self.C.YELLOW(inhibitor)))

    def finished(self, job, job_state, result):
        self._print_result_outcome(result)

    def _print_result_outcome(self, result):
        print(_("Outcome") + ": " + self.C.result(result))

    def pick_action_cmd(self, action_list, prompt=None):
        return ActionUI(action_list, prompt, self._color).run()

    def noreturn_job(self):
        print(self.C.RED(_("Waiting for the system to shut down or"
                           " reboot...")))


class ReRunJob(Exception):
    """
    Exception raised from _interaction_callback to indicate that a job should
    be re-started.
    """


def seconds_to_human_duration(seconds: float) -> str:
    """ Convert ammount of seconds to human readable duration string. """
    delta = datetime.timedelta(seconds=round(seconds))
    return str(delta)
