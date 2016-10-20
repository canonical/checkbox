# This file is part of Checkbox.
#
# Copyright 2016 Canonical Ltd.
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
Bunch of helpers to make it easier to reuse logic and UI functionality
associated with a particular stage of checkbox execution.
"""
import abc
import gettext

from plainbox.abc import IJobResult
from plainbox.i18n import pgettext as C_
from plainbox.impl.commands.inv_run import Action
from plainbox.impl.commands.inv_run import ActionUI
from plainbox.impl.commands.inv_run import NormalUI
from plainbox.impl.commands.inv_run import ReRunJob
from plainbox.impl.commands.inv_run import seconds_to_human_duration
from plainbox.impl.result import JobResultBuilder
from plainbox.impl.result import tr_outcome

_ = gettext.gettext


class MainLoopStage(metaclass=abc.ABCMeta):
    """
    Functionality governing command job execution.
    """
    @property
    @abc.abstractmethod
    def sa(self):
        """SessionAssistant instance to use."""

    @property
    @abc.abstractmethod
    def C(self):
        """Colorizer instance to use."""

    @property
    @abc.abstractmethod
    def is_interactive(self):
        """
        Flag indicating that this is an interactive invocation.

        We can then interact with the user when we encounter OUTCOME_UNDECIDED.
        """

    def _run_single_job_with_ui_loop(self, job, ui):
        print(self.C.header(job.tr_summary(), fill='-'))
        print(_("ID: {0}").format(job.id))
        print(_("Category: {0}").format(
            self.sa.get_job_state(job.id).effective_category_id))
        comments = ""
        while True:
            if job.plugin in ('user-interact', 'user-interact-verify',
                              'user-verify', 'manual'):
                # FIXME: get rid of pulling sa's internals
                jsm = self.sa._context._state._job_state_map
                if jsm[job.id].can_start():
                    ui.notify_about_purpose(job)
                if (self.is_interactive and
                        job.plugin in ('user-interact',
                                       'user-interact-verify',
                                       'manual')):
                    if jsm[job.id].can_start():
                        ui.notify_about_steps(job)
                    if job.plugin == 'manual':
                        cmd = 'run'
                    else:
                        if jsm[job.id].can_start():
                            cmd = ui.wait_for_interaction_prompt(job)
                        else:
                            # 'running' the job will make it marked as skipped
                            # because of the failed dependency
                            cmd = 'run'
                    if cmd == 'run' or cmd is None:
                        result_builder = self.sa.run_job(job.id, ui, False)
                    elif cmd == 'comment':
                        new_comment = input(self.C.BLUE(
                            _('Please enter your comments:') + '\n'))
                        if new_comment:
                            comments += new_comment + '\n'
                        continue
                    elif cmd == 'skip':
                        result_builder = JobResultBuilder(
                            outcome=IJobResult.OUTCOME_SKIP,
                            comments=_("Explicitly skipped before"
                                       " execution"))
                        if comments != "":
                            result_builder.comments = comments
                        break
                    elif cmd == 'quit':
                        raise SystemExit()
                else:
                    result_builder = self.sa.run_job(job.id, ui, False)
            else:
                if 'noreturn' in job.get_flag_set():
                    ui.noreturn_job()
                result_builder = self.sa.run_job(job.id, ui, False)
            if (self.is_interactive and
                    result_builder.outcome == IJobResult.OUTCOME_UNDECIDED):
                try:
                    if comments != "":
                        result_builder.comments = comments
                    ui.notify_about_verification(job)
                    self._interaction_callback(job, result_builder)
                except ReRunJob:
                    self.sa.use_job_result(job.id, result_builder.get_result())
                    continue
            break
        return result_builder

    def _interaction_callback(self, job, result_builder,
                              prompt=None, allowed_outcome=None):
        result = result_builder.get_result()
        if prompt is None:
            prompt = _("Select an outcome or an action: ")
        if allowed_outcome is None:
            allowed_outcome = [IJobResult.OUTCOME_PASS,
                               IJobResult.OUTCOME_FAIL,
                               IJobResult.OUTCOME_SKIP]
        allowed_actions = [
            Action('c', _('add a comment'), 'set-comments')
        ]
        if IJobResult.OUTCOME_PASS in allowed_outcome:
            allowed_actions.append(
                Action('p', _('set outcome to {0}').format(
                    self.C.GREEN(C_('set outcome to <pass>', 'pass'))),
                    'set-pass'))
        if IJobResult.OUTCOME_FAIL in allowed_outcome:
            allowed_actions.append(
                Action('f', _('set outcome to {0}').format(
                    self.C.RED(C_('set outcome to <fail>', 'fail'))),
                    'set-fail'))
        if IJobResult.OUTCOME_SKIP in allowed_outcome:
            allowed_actions.append(
                Action('s', _('set outcome to {0}').format(
                    self.C.YELLOW(C_('set outcome to <skip>', 'skip'))),
                    'set-skip'))
        if job.command is not None:
            allowed_actions.append(
                Action('r', _('re-run this job'), 're-run'))
        if result.return_code is not None:
            if result.return_code == 0:
                suggested_outcome = IJobResult.OUTCOME_PASS
            else:
                suggested_outcome = IJobResult.OUTCOME_FAIL
            allowed_actions.append(
                Action('', _('set suggested outcome [{0}]').format(
                    tr_outcome(suggested_outcome)), 'set-suggested'))
        while result.outcome not in allowed_outcome:
            print(_("Please decide what to do next:"))
            print("  " + _("outcome") + ": {0}".format(
                self.C.result(result)))
            if result.comments is None:
                print("  " + _("comments") + ": {0}".format(
                    C_("none comment", "none")))
            else:
                print("  " + _("comments") + ": {0}".format(
                    self.C.CYAN(result.comments, bright=False)))
            cmd = self._pick_action_cmd(allowed_actions)
            if cmd == 'set-pass':
                result_builder.outcome = IJobResult.OUTCOME_PASS
            elif cmd == 'set-fail':
                result_builder.outcome = IJobResult.OUTCOME_FAIL
            elif cmd == 'set-skip' or cmd is None:
                result_builder.outcome = IJobResult.OUTCOME_SKIP
            elif cmd == 'set-suggested':
                result_builder.outcome = suggested_outcome
            elif cmd == 'set-comments':
                new_comment = input(self.C.BLUE(
                    _('Please enter your comments:') + '\n'))
                if new_comment:
                    result_builder.add_comment(new_comment)
            elif cmd == 're-run':
                raise ReRunJob
            result = result_builder.get_result()

    def _get_ui_for_job(self, job):
        class CheckboxUI(NormalUI):
            def considering_job(self, job, job_state):
                pass
        show_out = True
        if 'suppress-output' in job.get_flag_set():
            show_out = False
        return CheckboxUI(self.C.c, show_cmd_output=show_out)

    def _run_jobs(self, jobs_to_run):
        estimated_time = 0
        for job_id in jobs_to_run:
            job = self.sa.get_job(job_id)
            if (job.estimated_duration is not None and
                    estimated_time is not None):
                estimated_time += job.estimated_duration
            else:
                estimated_time = None
        for job_no, job_id in enumerate(jobs_to_run, start=1):
            print(self.C.header(
                _('Running job {} / {}. Estimated time left: {}').format(
                    job_no, len(jobs_to_run),
                    seconds_to_human_duration(max(0, estimated_time))
                    if estimated_time is not None else _("unknown")),
                fill='-'))
            job = self.sa.get_job(job_id)
            builder = self._run_single_job_with_ui_loop(
                job, self._get_ui_for_job(job))
            result = builder.get_result()
            self.sa.use_job_result(job_id, result)
            if (job.estimated_duration is not None and
                    estimated_time is not None):
                estimated_time -= job.estimated_duration

    def _pick_action_cmd(self, action_list, prompt=None):
        return ActionUI(action_list, prompt).run()
