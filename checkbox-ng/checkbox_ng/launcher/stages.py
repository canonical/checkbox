# This file is part of Checkbox.
#
# Copyright 2016-2019 Canonical Ltd.
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
import datetime
import gettext
import json
import logging
import os
import time
import textwrap

from plainbox.abc import IJobResult
from plainbox.i18n import pgettext as C_
from plainbox.impl.config import Configuration
from plainbox.impl.result import JobResultBuilder
from plainbox.impl.result import tr_outcome
from plainbox.impl.transport import InvalidSecureIDError
from plainbox.impl.transport import TransportError
from plainbox.impl.transport import get_all_transports
from plainbox.impl.unit.exporter import ExporterError

from checkbox_ng.launcher.run import (
    Action, ActionUI, NormalUI, ReRunJob, seconds_to_human_duration)

_ = gettext.gettext

_logger = logging.getLogger("checkbox-ng.launcher.stages")


class CheckboxUiStage(metaclass=abc.ABCMeta):
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

    def _pick_action_cmd(self, action_list, prompt=None):
        return ActionUI(action_list, prompt).run()


class MainLoopStage(CheckboxUiStage):

    def __init__(self):
        super().__init__()
        self._sudo_password = None
        self._passwordless_sudo = False
        self._reset_auto_submission_retries()

    def _reset_auto_submission_retries(self):
        """
        This is outlined so both, __init__ and later part of the logic
        can set the same value.
        """
        self._auto_submission_retries = 3


    def _run_single_job_with_ui_loop(self, job, ui):
        print(self.C.header(job.tr_summary(), fill='-'))
        print(_("ID: {0}").format(job.id))
        print(_("Category: {0}").format(
            self.sa.get_job_state(job.id).effective_category_id))
        comments = ""
        while True:
            if job.plugin in ('user-interact', 'user-interact-verify',
                              'user-verify', 'manual'):
                job_state = self.sa.get_job_state(job.id)
                if (not self.is_interactive and
                        job.plugin in ('user-interact',
                                       'user-interact-verify',
                                       'manual')):
                    result_builder = JobResultBuilder(
                        outcome=IJobResult.OUTCOME_SKIP,
                        comments=_("Trying to run interactive job in a silent"
                                   " session"))
                    return result_builder
                if job_state.can_start():
                    ui.notify_about_purpose(job)
                if (self.is_interactive and
                        job.plugin in ('user-interact',
                                       'user-interact-verify',
                                       'manual')):
                    if job_state.can_start():
                        ui.notify_about_steps(job)
                    if job.plugin == 'manual':
                        cmd = 'run'
                    else:
                        if job_state.can_start():
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

    def _run_bootstrap_jobs(self, jobs_to_run):
        for job_no, job_id in enumerate(jobs_to_run, start=1):
            print(self.C.header(
                _('Bootstrap {} ({}/{})').format(
                    job_id, job_no, len(jobs_to_run), fill='-')))
            result_builder = self.sa.run_job(job_id, 'piano', False)
            self.sa.use_job_result(job_id, result_builder.get_result())

    def _generate_job_infos(self, job_list):
        test_info_list = tuple()
        for job in job_list:
            cat_id = self.sa.get_job_state(job.id).effective_category_id
            duration_txt = _('No estimated duration provided for this job')
            if job.estimated_duration is not None:
                duration_txt = '{} {}'.format(job.estimated_duration, _(
                    'seconds'))
            test_info = {
                "id": job.id,
                "partial_id": job.partial_id,
                "name": job.tr_summary(),
                "category_id": cat_id,
                "category_name": self.sa.get_category(cat_id).tr_name(),
                "automated": (
                    _('this job is fully automated')
                    if job.automated
                    else _('this job requires some manual interaction')
                ),
                "duration": duration_txt,
                "description": (job.tr_description() or
                                _('No description provided for this job')),
                "outcome": self.sa.get_job_state(job.id).result.outcome,
            }
            test_info_list = test_info_list + ((test_info, ))
        return test_info_list

    def _generate_tp_infos(self, tp_list):
        tp_info_list = []
        for tp_id in tp_list:
            tp_info = {
                'id': tp_id,
                'name': self.sa.get_test_plan(tp_id).name
            }
            tp_info_list.append(tp_info)
        return tp_info_list


class ReportsStage(CheckboxUiStage):

    def __init__(self):
        super().__init__()
        self._export_fn = None

    def _override_exporting(self, export_fn):
        self._export_fn = export_fn

    def _prepare_stock_report(self, report):

        new_origin = 'stock_reports'
        if report == 'text':
            additional_config = Configuration.from_text(textwrap.dedent("""
                [exporter:text]
                unit = com.canonical.plainbox::text
                [transport:stdout]
                stream = stdout
                type = stream
                [report:1_text_to_screen]
                exporter = text
                forced = yes
                transport = stdout
            """), new_origin)
            self.sa.config.update_from_another(additional_config, new_origin)
        elif report == 'certification':
            additional_config = Configuration.from_text(textwrap.dedent("""
                [exporter:tar]
                unit = com.canonical.plainbox::tar
                [transport:c3]
                type = submission-service
                [report:upload to certification]
                exporter = tar
                transport = c3
            """), new_origin)
            self.sa.config.update_from_another(additional_config, new_origin)
        elif report == 'certification-staging':
            additional_config = Configuration.from_text(textwrap.dedent("""
                [exporter:tar]
                unit = com.canonical.plainbox::tar
                [transport:c3]
                staging = yes
                type = submission-service
                [report:upload to certification-staging]
                exporter = tar
                transport = c3
            """), new_origin)
            self.sa.config.update_from_another(additional_config, new_origin)
        elif report == 'submission_files':
            # LP:1585326 maintain isoformat but removing ':' chars that cause
            # issues when copying files.
            isoformat = "%Y-%m-%dT%H.%M.%S.%f"
            timestamp = datetime.datetime.utcnow().strftime(isoformat)
            if not os.path.exists(self.base_dir):
                os.makedirs(self.base_dir)
            for exporter, file_ext in [('html', '.html'),
                                       ('junit', '.junit.xml'),
                                       ('tar', '.tar.xz')]:
                path = os.path.join(self.base_dir, ''.join(
                    ['submission_', timestamp, file_ext]))
                template = textwrap.dedent("""
                    [transport:{exporter}_file]
                    path = {path}
                    type = file
                    [exporter:{exporter}]
                    unit = com.canonical.plainbox::{exporter}
                    [report:2_{exporter}_file]
                    exporter = {exporter}
                    forced = yes
                    transport = {exporter}_file
                """)
                additional_config = Configuration.from_text(
                    template.format(exporter=exporter, path=path), new_origin)
                self.sa.config.update_from_another(
                    additional_config, new_origin)

    def _prepare_transports(self):
        self.base_dir = os.path.join(
            os.getenv(
                'XDG_DATA_HOME', os.path.expanduser("~/.local/share/")),
            "checkbox-ng")
        self._available_transports = get_all_transports()
        self.transports = dict()

    def _create_transport(self, transport):
        if transport in self.transports:
            return
        # depending on the type of transport we need to pick variable that
        # serves as the 'where' param for the transport. In case of
        # certification site the URL is supplied here
        transport_cfg = self.sa.config.get_parametric_sections(
            'transport')[transport]
        tr_type = transport_cfg['type']
        if tr_type not in self._available_transports:
            _logger.error(_("Unrecognized type '%s' of transport '%s'"),
                          tr_type, transport)
            raise SystemExit(1)
        cls = self._available_transports[tr_type]
        if tr_type == 'file':
            self.transports[transport] = cls(
                os.path.expanduser(transport_cfg['path']))
        elif tr_type == 'stream':
            self.transports[transport] = cls(transport_cfg['stream'])
        elif tr_type == 'submission-service':
            secure_id = transport_cfg.get('secure_id', None)
            if self.is_interactive:
                new_description = input(self.C.BLUE(_(
                    'Enter submission description (press Enter to skip): ')))
                if new_description:
                    self.sa.update_app_blob(json.dumps(
                        {
                            'description': new_description,

                        }).encode("UTF-8"))
            if not secure_id and self.is_interactive:
                secure_id = input(self.C.BLUE(_('Enter secure-id:')))
            if secure_id:
                options = "secure_id={}".format(secure_id)
            else:
                options = ""
            if transport_cfg.get('staging', False):
                url = ('https://certification.staging.canonical.com/'
                       'api/v1/submission/{}/'.format(secure_id))
            elif os.getenv('C3_URL'):
                url = (
                    '{}/{}/'.format(os.getenv('C3_URL'), ctx.args.secure_id))
            else:
                url = ('https://certification.canonical.com/'
                       'api/v1/submission/{}/'.format(secure_id))
            self.transports[transport] = cls(url, options)

    def _export_results(self):
        stock_reports = self.sa.config.get_value('launcher', 'stock_reports')
        if 'none' not in stock_reports:
            for report in stock_reports:
                if report in ['certification', 'certification-staging']:
                    # skip stock c3 report if secure_id is not given from
                    # config files or launchers, and the UI is non-interactive
                    # (silent)
                    if ('transport:c3' not in self.sa.config.sections.keys()
                            and not self.is_interactive):
                        continue
                    # don't generate stock c3 reports if sideloaded providers
                    # were in use, something that should only be done during
                    # development
                    if self.sa.sideloaded_providers:
                        _logger.warning(_("Using side-loaded providers "
                                          "disabled the %s report"), report)
                        continue
                self._prepare_stock_report(report)
        # reports are stored in an ordinary dict(), so sorting them ensures
        # the same order of submitting them between runs, and if they
        # share common prefix, they are next to each other
        for name, params in sorted(
                self.sa.config.get_parametric_sections('report').items()):

            # don't generate stock c3 reports if sideloaded providers
            # were in use, something that should only be done during
            # development
            if (params.get('transport') == 'certification' and
                    self.sa.sideloaded_providers):
                _logger.warning(_("Using side-loaded providers disabled "
                                  "the %s report"), name)
                continue
            if self.is_interactive and not params.get('forced', False):
                message = _("Do you want to submit '{}' report?").format(name)
                cmd = self._pick_action_cmd([
                    Action('y', _("yes"), 'y'),
                    Action('n', _("no"), 'n')
                ], message)
            else:
                cmd = 'y'
            if cmd == 'n':
                continue
            all_exporters = self.sa.config.get_parametric_sections('exporter')
            exporter_id = self.sa.config.get_parametric_sections('exporter')[
                    params['exporter']]['unit']
            exp_options = self.sa.config.get_parametric_sections('exporter')[
                    params['exporter']].get('options', '').split()
            done_sending = False
            while not done_sending:
                try:
                    self._create_transport(params['transport'])
                    transport = self.transports[params['transport']]
                    if self._export_fn:
                        result = self._export_fn(exporter_id, transport)
                    else:
                        try:
                            result = self.sa.export_to_transport(
                                exporter_id, transport, exp_options)
                        except ExporterError as exc:
                            _logger.warning(
                                _("Problem occured when preparing %s report:"
                                  "%s"), exporter_id, exc)
                    if result and 'url' in result:
                        print(result['url'])
                    elif result and 'status_url' in result:
                        print(result['status_url'])
                except TransportError as exc:
                    _logger.warning(
                        _("Problem occured when submitting '%s' report: %s"),
                        name, exc)
                    if self._retry_dialog():
                        # let's remove current transport, so in next
                        # iteration it will be "rebuilt", so if some parts
                        # were user-provided, checkbox will ask for them
                        # again
                        self.transports.pop(params['transport'])
                        continue
                except InvalidSecureIDError:
                    _logger.warning(_("Invalid secure_id"))
                    if not self.is_interactive:
                        # secure_id will not magically change if the session
                        # is a non-interactive one, so let's stop trying
                        done_sending = True
                        continue
                    if self._retry_dialog():
                        self.sa.config.sections['transports']['c3'].pop(
                            'secure_id')
                        continue
                except Exception as exc:
                    _logger.error(
                        _("Problem with a '%s' report using '%s' exporter "
                          "sent to '%s' transport. Reason %s"),
                        name, exporter_id, transport.url, exc)
                done_sending = True

    def _retry_dialog(self):
        if self.is_interactive:
            message = _("Do you want to retry?")
            cmd = self._pick_action_cmd([
                Action('y', _("yes"), 'y'),
                Action('n', _("no"), 'n')
            ], message)
            if cmd == 'y':
                return True
        else:
            if self._auto_submission_retries:
                self._auto_submission_retries -= 1
                # let's double the sleep length with each retry
                sleep_length = [120, 60, 30][self._auto_submission_retries]
                print("Retrying in {}s".format(sleep_length))
                time.sleep(sleep_length)
                return True

        return False

template = textwrap.dedent("""
    [transport:{exporter}_file]
    type = file
    path = {path}
    [exporter:{exporter}]
    unit = com.canonical.plainbox::{exporter}
    [report:2_{exporter}_file]
    transport = {exporter}_file
    exporter = {exporter}
    forced = yes""")
