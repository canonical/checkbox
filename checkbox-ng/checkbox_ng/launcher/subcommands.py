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
Definition of sub-command classes for checkbox-cli
"""
from argparse import SUPPRESS
from collections import defaultdict
import copy
import datetime
import fnmatch
import gettext
import json
import logging
import operator
import os
import re
import sys
import time

from guacamole import Command

from plainbox.abc import IJobResult
from plainbox.i18n import ngettext
from plainbox.impl.color import Colorizer
from plainbox.impl.commands.inv_check_config import CheckConfigInvocation
from plainbox.impl.commands.inv_run import Action
from plainbox.impl.commands.inv_run import NormalUI
from plainbox.impl.commands.inv_startprovider import (
    EmptyProviderSkeleton, IQN, ProviderSkeleton)
from plainbox.impl.highlevel import Explorer
from plainbox.impl.providers import get_providers
from plainbox.impl.providers.embedded_providers import (
    EmbeddedProvider1PlugInCollection)
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.session.assistant import SessionAssistant, SA_RESTARTABLE
from plainbox.impl.session.jobs import InhibitionCause
from plainbox.impl.session.restart import detect_restart_strategy
from plainbox.impl.session.restart import get_strategy_by_name
from plainbox.impl.transport import TransportError
from plainbox.impl.transport import InvalidSecureIDError
from plainbox.impl.transport import get_all_transports
from plainbox.impl.transport import SECURE_ID_PATTERN

from checkbox_ng.config import CheckBoxConfig
from checkbox_ng.launcher.stages import MainLoopStage
from checkbox_ng.urwid_ui import CategoryBrowser
from checkbox_ng.urwid_ui import ReRunBrowser
from checkbox_ng.urwid_ui import test_plan_browser

_ = gettext.gettext

_logger = logging.getLogger("checkbox-ng.launcher.subcommands")


class CheckConfig(Command):
    def invoked(self, ctx):
        return CheckConfigInvocation(lambda: CheckBoxConfig.get()).run()


class Submit(Command):
    def register_arguments(self, parser):
        def secureid(secure_id):
            if not re.match(SECURE_ID_PATTERN, secure_id):
                raise ArgumentTypeError(
                    _("must be 15-character (or more) alphanumeric string"))
            return secure_id
        parser.add_argument(
            'secure_id', metavar=_("SECURE-ID"),
            type=secureid,
            help=_("associate submission with a machine using this SECURE-ID"))
        parser.add_argument(
            "submission", metavar=_("SUBMISSION"),
            help=_("The path to the results file"))
        parser.add_argument(
            "-s", "--staging", action="store_true",
            help=_("Use staging environment"))

    def invoked(self, ctx):
        transport_cls = None
        enc = None
        mode = 'rb'
        options_string = "secure_id={0}".format(ctx.args.secure_id)
        url = ('https://certification.canonical.com/'
               'api/v1/submission/{}/'.format(ctx.args.secure_id))
        if ctx.args.staging:
            url = ('https://certification.staging.canonical.com/'
                   'api/v1/submission/{}/'.format(ctx.args.secure_id))
        from checkbox_ng.certification import SubmissionServiceTransport
        transport_cls = SubmissionServiceTransport
        transport = transport_cls(url, options_string)
        try:
            with open(ctx.args.submission, mode, encoding=enc) as subm_file:
                result = transport.send(subm_file)
        except (TransportError, OSError) as exc:
            raise SystemExit(exc)
        else:
            if result and 'url' in result:
                # TRANSLATORS: Do not translate the {} format marker.
                print(_("Successfully sent, submission status"
                        " at {0}").format(result['url']))
            elif result and 'status_url' in result:
                # TRANSLATORS: Do not translate the {} format marker.
                print(_("Successfully sent, submission status"
                        " at {0}").format(result['status_url']))
            else:
                # TRANSLATORS: Do not translate the {} format marker.
                print(_("Successfully sent, server response"
                        ": {0}").format(result))


class StartProvider(Command):
    def register_arguments(self, parser):
        parser.add_argument(
            'name', metavar=_('name'), type=IQN,
            # TRANSLATORS: please keep the YYYY.example... text unchanged or at
            # the very least translate only YYYY and some-name. In either case
            # some-name must be a reasonably-ASCII string (should be safe for a
            # portable directory name)
            help=_("provider name, eg: YYYY.example.org:some-name"))
        parser.add_argument(
            '--empty', action='store_const', const=EmptyProviderSkeleton,
            default=ProviderSkeleton, dest='skeleton',
            help=_('create an empty provider'))

    def invoked(self, ctx):
        ctx.args.skeleton(ctx.args.name).instantiate(
            '.', name=ctx.args.name,
            gettext_domain=re.sub("[.:]", "_", ctx.args.name))


class Launcher(Command, MainLoopStage):

    name = 'launcher'

    app_id = 'com.canonical:checkbox-cli'

    @property
    def sa(self):
        return self.ctx.sa

    @property
    def C(self):
        return self._C

    def get_sa_api_version(self):
        return self.launcher.api_version

    def get_sa_api_flags(self):
        return self.launcher.api_flags

    def invoked(self, ctx):
        if ctx.args.verify:
            # validation is always run, so if there were any errors the program
            # exited by now, so validation passed
            print(_("Launcher seems valid."))
            return
        self.launcher = ctx.cmd_toplevel.launcher
        logging_level = {
            'normal': logging.WARNING,
            'verbose': logging.INFO,
            'debug': logging.DEBUG,
        }[self.launcher.verbosity]
        if not ctx.args.verbose and not ctx.args.debug:
            # Command line args take precendence
            logging.basicConfig(level=logging_level)

        if self.launcher.ui_type in ['converged', 'converged-silent']:
            # Stop processing the launcher config and call the QML ui
            qml_main_file = os.path.join('/usr/share/checkbox-converged',
                                         'checkbox-converged.qml')
            cmd = ['qmlscene', qml_main_file,
                   '--launcher={}'.format(os.path.abspath(ctx.args.launcher))]
            os.execvp(cmd[0], cmd)

        try:
            self._C = Colorizer()
            self.ctx = ctx
            # now we have all the correct flags and options, so we need to
            # replace the previously built SA with the defaults
            ctx.sa = SessionAssistant(
                self.get_app_id(),
                self.get_cmd_version(),
                self.get_sa_api_version(),
                self.get_sa_api_flags(),
            )
            # side-load providers local-providers
            side_load_path = os.path.expandvars(os.path.join(
                '/home', '$USER', 'providers'))
            additional_providers = ()
            if os.path.exists(side_load_path):
                print(self._C.RED(_(
                    "WARNING: using side-loded providers")))
                os.environ['PROVIDERPATH'] = ''
                embedded_providers = EmbeddedProvider1PlugInCollection(
                        side_load_path)
                additional_providers = embedded_providers.get_all_plugin_objects()
            self._configure_restart(ctx)
            self._prepare_transports()
            ctx.sa.use_alternate_configuration(self.launcher)
            try:
                ctx.sa.select_providers(
                    *self.launcher.providers,
                    additional_providers=additional_providers)
            except ValueError:
                print(self._C.RED(_("No providers found")))
                return 1
            if not self._maybe_resume_session():
                self._start_new_session()
                self._pick_jobs_to_run()
            if not self.ctx.sa.get_static_todo_list():
                return 0
            self.base_dir = os.path.join(
                os.getenv(
                    'XDG_DATA_HOME', os.path.expanduser("~/.local/share/")),
                "checkbox-ng")
            if 'submission_files' in self.launcher.stock_reports:
                print("Reports will be saved to: {}".format(self.base_dir))
            # we initialize the nb of attempts for all the selected jobs...
            for job_id in self.ctx.sa.get_dynamic_todo_list():
                job_state = self.ctx.sa.get_job_state(job_id)
                job_state.attempts = self.launcher.max_attempts
            # ... before running them
            self._run_jobs(self.ctx.sa.get_dynamic_todo_list())
            if self.is_interactive and not self.launcher.auto_retry:
                while True:
                    if not self._maybe_rerun_jobs():
                        break
            elif self.launcher.auto_retry:
                while True:
                    if not self._maybe_auto_retry_jobs():
                        break
            self._export_results()
            ctx.sa.finalize_session()
            return 0 if ctx.sa.get_summary()['fail'] == 0 else 1
        except KeyboardInterrupt:
            return 1

    @property
    def is_interactive(self):
        """
        Flag indicating that this is an interactive invocation.

        We can then interact with the user when we encounter OUTCOME_UNDECIDED.
        """
        return (self.launcher.ui_type == 'interactive' and
            sys.stdin.isatty() and sys.stdout.isatty())

    def _configure_restart(self, ctx):
        if SA_RESTARTABLE not in self.get_sa_api_flags():
            return
        if self.launcher.restart_strategy:
            try:
                cls = get_strategy_by_name(
                    self.launcher.restart_strategy)
                kwargs = copy.deepcopy(self.launcher.restart)
                # [restart] section has the kwargs for the strategy initializer
                # and the 'strategy' which is not one, let's pop it
                kwargs.pop('strategy')
                strategy = cls(**kwargs)
                ctx.sa.use_alternate_restart_strategy(strategy)

            except KeyError:
                _logger.warning(_('Unknown restart strategy: %s', (
                    self.launcher.restart_strategy)))
                _logger.warning(_(
                    'Using automatically detected restart strategy'))
                try:
                    strategy = detect_restart_strategy()
                except LookupError as exc:
                    _logger.warning(exc)
                    _logger.warning(_('Automatic restart disabled!'))
                    strategy = None
        else:
            strategy = detect_restart_strategy()
        if strategy:
            # gluing the command with pluses b/c the middle part
            # (launcher path) is optional
            snap_name = os.getenv('SNAP_NAME')
            if snap_name:
                # NOTE: This implies that any snap wishing to include a
                # Checkbox snap to be autostarted creates a snapcraft
                # app called "checkbox-cli"
                respawn_cmd = '/snap/bin/{}.checkbox-cli'.format(snap_name)
            else:
                respawn_cmd = sys.argv[0] # entry-point to checkbox
            respawn_cmd += " launcher "
            if ctx.args.launcher:
                respawn_cmd += os.path.abspath(ctx.args.launcher) + ' '
            respawn_cmd += '--resume {}' # interpolate with session_id
            ctx.sa.configure_application_restart(
                lambda session_id: [ respawn_cmd.format(session_id)])

    def _maybe_resume_session(self):
        resume_candidates = list(self.ctx.sa.get_resumable_sessions())
        if self.ctx.args.session_id:
            requested_sessions = [s for s in resume_candidates if (
                s.id == self.ctx.args.session_id)]
            if requested_sessions:
                # session_ids are unique, so there should be only 1
                self._resume_session(requested_sessions[0])
                return True
            else:
                raise RuntimeError("Requested session is not resumable!")
        elif self.is_interactive:
            print(self.C.header(_("Resume Incomplete Session")))
            print(ngettext(
                "There is {0} incomplete session that might be resumed",
                "There are {0} incomplete sessions that might be resumed",
                len(resume_candidates)
            ).format(len(resume_candidates)))
            return self._run_resume_ui_loop(resume_candidates)
        else:
            return False

    def _run_resume_ui_loop(self, resume_candidates):
        for candidate in resume_candidates:
            cmd = self._pick_action_cmd([
                Action('r', _("resume this session"), 'resume'),
                Action('n', _("next session"), 'next'),
                Action('c', _("create new session"), 'create'),
                Action('d', _("delete old sessions"), 'delete'),
            ], _("Do you want to resume session {0!a}?").format(candidate.id))
            if cmd == 'next':
                continue
            elif cmd == 'create' or cmd is None:
                return False
            elif cmd == 'resume':
                self._resume_session(candidate)
                return True
            elif cmd == 'delete':
                ids = [candidate.id for candidate in resume_candidates]
                self._delete_old_sessions(ids)
                return False

    def _resume_session(self, session):
        metadata = self.ctx.sa.resume_session(session.id)
        if 'testplanless' not in metadata.flags:
            app_blob = json.loads(metadata.app_blob.decode("UTF-8"))
            test_plan_id = app_blob['testplan_id']
            self.ctx.sa.select_test_plan(test_plan_id)
            self.ctx.sa.bootstrap()
        last_job = metadata.running_job_name
        # If we resumed maybe not rerun the same, probably broken job
        self._handle_last_job_after_resume(last_job)

    def _start_new_session(self):
        print(_("Preparing..."))
        title = self.launcher.app_id
        if self.ctx.args.title:
            title = self.ctx.args.title
        elif self.ctx.args.launcher:
            title = os.path.basename(self.ctx.args.launcher)
        if self.launcher.app_version:
            title += ' {}'.format(self.launcher.app_version)
        self.ctx.sa.start_new_session(title)
        if self.launcher.test_plan_forced:
            tp_id = self.launcher.test_plan_default_selection
        elif not self.is_interactive:
            # XXX: this maybe somewhat redundant with validation
            _logger.error(_(
                'Non-interactive session without test plan specified in the '
                'launcher!'))
            raise SystemExit(1)
        else:
            tp_id = self._interactively_pick_test_plan()
            if tp_id is None:
                raise SystemExit(_("No test plan selected."))
        self.ctx.sa.select_test_plan(tp_id)
        self.ctx.sa.update_app_blob(json.dumps(
            {'testplan_id': tp_id, }).encode("UTF-8"))
        bs_jobs = self.ctx.sa.get_bootstrap_todo_list()
        self._run_bootstrap_jobs(bs_jobs)
        self.ctx.sa.finish_bootstrap()

    def _delete_old_sessions(self, ids):
        completed_ids = [s[0] for s in self.ctx.sa.get_old_sessions()]
        self.ctx.sa.delete_sessions(completed_ids + ids)

    def _interactively_pick_test_plan(self):
        test_plan_ids = self.ctx.sa.get_test_plans()
        filtered_tp_ids = set()
        for filter in self.launcher.test_plan_filters:
            filtered_tp_ids.update(fnmatch.filter(test_plan_ids, filter))
        filtered_tp_ids = list(filtered_tp_ids)
        filtered_tp_ids.sort(
            key=lambda tp_id: self.ctx.sa.get_test_plan(tp_id).name)
        test_plan_names = [self.ctx.sa.get_test_plan(tp_id).name for tp_id in
                           filtered_tp_ids]
        preselected_index = None
        if self.launcher.test_plan_default_selection:
            try:
                preselected_index = test_plan_names.index(
                    self.ctx.sa.get_test_plan(
                        self.launcher.test_plan_default_selection).name)
            except KeyError:
                _logger.warning(_('%s test plan not found'),
                                self.launcher.test_plan_default_selection)
                preselected_index = None
        try:
            selected_index = test_plan_browser(
                _("Select test plan"), test_plan_names, preselected_index)
            return filtered_tp_ids[selected_index]
        except (IndexError, TypeError):
            return None

    def _pick_jobs_to_run(self):
        if self.launcher.test_selection_forced:
            # by default all tests are selected; so we're done here
            return
        job_list = [self.ctx.sa.get_job(job_id) for job_id in
                    self.ctx.sa.get_static_todo_list()]
        test_info_list = self._generate_job_infos(job_list)
        if not job_list:
            print(self.C.RED(_("There were no tests to select from!")))
            return
        wanted_set = CategoryBrowser(
            _("Choose tests to run on your system:"), test_info_list).run()
        # NOTE: tree.selection is correct but ordered badly. To retain
        # the original ordering we should just treat it as a mask and
        # use it to filter jobs from get_static_todo_list.
        job_id_list = [job_id for job_id in self.ctx.sa.get_static_todo_list()
                       if job_id in wanted_set]
        self.ctx.sa.use_alternate_selection(job_id_list)

    def _generate_job_infos(self, job_list):
        test_info_list = tuple()
        for job in job_list:
            cat_id = self.ctx.sa.get_job_state(job.id).effective_category_id
            duration_txt = _('No estimated duration provided for this job')
            if job.estimated_duration is not None:
                duration_txt = '{} {}'.format(job.estimated_duration, _(
                    'seconds'))
            test_info = {
                "id": job.id,
                "partial_id": job.partial_id,
                "name": job.tr_summary(),
                "category_id": cat_id,
                "category_name": self.ctx.sa.get_category(cat_id).tr_name(),
                "automated": (_('this job is fully automated') if job.automated
                    else _('this job requires some manual interaction')),
                "duration": duration_txt,
                "description": (job.tr_description() or
                    _('No description provided for this job')),
                "outcome": self.ctx.sa.get_job_state(job.id).result.outcome,
            }
            test_info_list = test_info_list + ((test_info, ))
        return test_info_list

    def _handle_last_job_after_resume(self, last_job):
        if last_job is None:
            return
        if self.ctx.args.session_id:
            # session_id is present only if auto-resume is used
            print(_("Auto resuming session. Marking previous job as passed"))
            result = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_PASS,
                'comments': _("Passed after resuming execution")
            })
            self.ctx.sa.use_job_result(last_job, result)
            return

        print(_("Previous session run tried to execute job: {}").format(
            last_job))
        cmd = self._pick_action_cmd([
            Action('s', _("skip that job"), 'skip'),
            Action('p', _("mark it as passed and continue"), 'pass'),
            Action('f', _("mark it as failed and continue"), 'fail'),
            Action('r', _("run it again"), 'run'),
        ], _("What do you want to do with that job?"))
        if cmd == 'skip' or cmd is None:
            result = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_SKIP,
                'comments': _("Skipped after resuming execution")
            })
        elif cmd == 'pass':
            result = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_PASS,
                'comments': _("Passed after resuming execution")
            })
        elif cmd == 'fail':
            result = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_FAIL,
                'comments': _("Failed after resuming execution")
            })
        elif cmd == 'run':
            result = None
        if result:
            self.ctx.sa.use_job_result(last_job, result)

    def _maybe_auto_retry_jobs(self):
        # create a list of jobs that qualify for rerunning
        retry_candidates = self._get_auto_retry_candidates()
        # bail-out early if no job qualifies for rerunning
        if not retry_candidates:
            return False
        # we wait before retrying
        delay = self.launcher.delay_before_retry
        _logger.info(_("Waiting {} seconds before retrying failed"
                       " jobs...".format(delay)))
        time.sleep(delay)
        candidates = []
        # include resource jobs that jobs to retry depend on
        resources_to_rerun = []
        for job in retry_candidates:
            job_state = self.ctx.sa.get_job_state(job.id)
            for inhibitor in job_state.readiness_inhibitor_list:
                if inhibitor.cause == InhibitionCause.FAILED_DEP:
                    resources_to_rerun.append(inhibitor.related_job)
        # reset outcome of jobs that are selected for re-running
        for job in retry_candidates + resources_to_rerun:
            self.ctx.sa.get_job_state(job.id).result = MemoryJobResult({})
            candidates.append(job.id)
            _logger.info("{}: {} attempts".format(
                job.id,
                self.ctx.sa.get_job_state(job.id).attempts
            ))
        self._run_jobs(candidates)
        return True

    def _get_auto_retry_candidates(self):
        """Get all the tests that might be selected for an automatic retry."""
        def retry_predicate(job_state):
            return job_state.result.outcome in (IJobResult.OUTCOME_FAIL,) \
                   and job_state.effective_auto_retry != 'no'
        retry_candidates = []
        todo_list = self.ctx.sa.get_static_todo_list()
        job_states = {job_id: self.ctx.sa.get_job_state(job_id) for job_id
                      in todo_list}
        for job_id, job_state in job_states.items():
            if retry_predicate(job_state) and job_state.attempts > 0:
                retry_candidates.append(self.ctx.sa.get_job(job_id))
        return retry_candidates

    def _maybe_rerun_jobs(self):
        # create a list of jobs that qualify for rerunning
        rerun_candidates = self._get_rerun_candidates()
        # bail-out early if no job qualifies for rerunning
        if not rerun_candidates:
            return False
        test_info_list = self._generate_job_infos(rerun_candidates)
        wanted_set = ReRunBrowser(
            _("Select jobs to re-run"), test_info_list, rerun_candidates).run()
        if not wanted_set:
            # nothing selected - nothing to run
            return False
        rerun_candidates = []
        # include resource jobs that selected jobs depend on
        resources_to_rerun = []
        for job_id in wanted_set:
            job_state = self.ctx.sa.get_job_state(job_id)
            for inhibitor in job_state.readiness_inhibitor_list:
                if inhibitor.cause == InhibitionCause.FAILED_DEP:
                    resources_to_rerun.append(inhibitor.related_job.id)
        # some resource jobs may have been selected in the UI and also added
        # automatically, let's only add the missing ones
        wanted_jobs = [j for j in wanted_set if j not in resources_to_rerun]
        # reset outcome of jobs that are selected for re-running
        for job_id in resources_to_rerun + wanted_jobs:
            self.ctx.sa.get_job_state(job_id).result = MemoryJobResult({})
            rerun_candidates.append(job_id)
        self._run_jobs(rerun_candidates)
        return True

    def _get_rerun_candidates(self):
        """Get all the tests that might be selected for rerunning."""
        def rerun_predicate(job_state):
            return job_state.result.outcome in (
                IJobResult.OUTCOME_FAIL, IJobResult.OUTCOME_CRASH,
                IJobResult.OUTCOME_SKIP, IJobResult.OUTCOME_NOT_SUPPORTED)
        rerun_candidates = []
        todo_list = self.ctx.sa.get_static_todo_list()
        job_states = {job_id: self.ctx.sa.get_job_state(job_id) for job_id
                      in todo_list}
        for job_id, job_state in job_states.items():
            if rerun_predicate(job_state):
                rerun_candidates.append(self.ctx.sa.get_job(job_id))
        return rerun_candidates

    def _prepare_stock_report(self, report):
        # this is purposefully not using pythonic dict-keying for better
        # readability
        if not self.launcher.transports:
            self.launcher.transports = dict()
        if not self.launcher.exporters:
            self.launcher.exporters = dict()
        if not self.launcher.reports:
            self.launcher.reports = dict()
        if report == 'text':
            self.launcher.exporters['text'] = {
                'unit': 'com.canonical.plainbox::text'}
            self.launcher.transports['stdout'] = {
                'type': 'stream', 'stream': 'stdout'}
            # '1_' prefix ensures ordering amongst other stock reports. This
            # report name does not appear anywhere (because of forced: yes)
            self.launcher.reports['1_text_to_screen'] = {
                'transport': 'stdout', 'exporter': 'text', 'forced': 'yes'}
        elif report == 'certification':
            self.launcher.exporters['tar'] = {
                'unit': 'com.canonical.plainbox::tar'}
            self.launcher.transports['c3'] = {
                'type': 'submission-service',
                'secure_id': self.launcher.transports.get('c3', {}).get(
                    'secure_id', None)}
            self.launcher.reports['upload to certification'] = {
                'transport': 'c3', 'exporter': 'tar'}
        elif report == 'certification-staging':
            self.launcher.exporters['tar'] = {
                'unit': 'com.canonical.plainbox::tar'}
            self.launcher.transports['c3-staging'] = {
                'type': 'submission-service',
                'secure_id': self.launcher.transports.get('c3', {}).get(
                    'secure_id', None),
                'staging': 'yes'}
            self.launcher.reports['upload to certification-staging'] = {
                'transport': 'c3-staging', 'exporter': 'tar'}
        elif report == 'submission_files':
            # LP:1585326 maintain isoformat but removing ':' chars that cause
            # issues when copying files.
            isoformat = "%Y-%m-%dT%H.%M.%S.%f"
            timestamp = datetime.datetime.utcnow().strftime(isoformat)
            if not os.path.exists(self.base_dir):
                os.makedirs(self.base_dir)
            for exporter, file_ext in [('html', '.html'),
                                       ('junit', '.junit.xml'),
                                       ('xlsx', '.xlsx'), ('tar', '.tar.xz')]:
                path = os.path.join(self.base_dir, ''.join(
                    ['submission_', timestamp, file_ext]))
                self.launcher.transports['{}_file'.format(exporter)] = {
                    'type': 'file',
                    'path': path}
                if exporter not in self.launcher.exporters:
                    self.launcher.exporters[exporter] = {
                        'unit': 'com.canonical.plainbox::{}'.format(
                            exporter)}
                self.launcher.reports['2_{}_file'.format(exporter)] = {
                    'transport': '{}_file'.format(exporter),
                    'exporter': '{}'.format(exporter),
                    'forced': 'yes'
                }

    def _prepare_transports(self):
        self._available_transports = get_all_transports()
        self.transports = dict()

    def _create_transport(self, transport):
        if transport in self.transports:
            return
        # depending on the type of transport we need to pick variable that
        # serves as the 'where' param for the transport. In case of
        # certification site the URL is supplied here
        tr_type = self.launcher.transports[transport]['type']
        if tr_type not in self._available_transports:
            _logger.error(_("Unrecognized type '%s' of transport '%s'"),
                          tr_type, transport)
            raise SystemExit(1)
        cls = self._available_transports[tr_type]
        if tr_type == 'file':
            self.transports[transport] = cls(
                os.path.expanduser(self.launcher.transports[transport]['path']))
        elif tr_type == 'stream':
            self.transports[transport] = cls(
                self.launcher.transports[transport]['stream'])
        elif tr_type == 'submission-service':
            secure_id = self.launcher.transports[transport].get(
                'secure_id', None)
            if not secure_id and self.is_interactive:
                secure_id = input(self.C.BLUE(_('Enter secure-id:')))
            if secure_id:
                options = "secure_id={}".format(secure_id)
            else:
                options = ""
            if self.launcher.transports[transport].get('staging', False):
                url = ('https://certification.staging.canonical.com/'
                       'api/v1/submission/{}/'.format(secure_id))
            else:
                url = ('https://certification.canonical.com/'
                       'api/v1/submission/{}/'.format(secure_id))
            self.transports[transport] = cls(url, options)

    def _export_results(self):
        if 'none' not in self.launcher.stock_reports:
            for report in self.launcher.stock_reports:
                # skip stock c3 report if secure_id is not given from config files
                # or launchers, and the UI is non-interactive (silent)
                if (report in ['certification', 'certification-staging'] and
                        'c3' not in self.launcher.transports and
                        self.is_interactive == False):
                    continue
                self._prepare_stock_report(report)
        # reports are stored in an ordinary dict(), so sorting them ensures
        # the same order of submitting them between runs, and if they
        # share common prefix, they are next to each other
        for name, params in sorted(self.launcher.reports.items()):
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
            exporter_id = self.launcher.exporters[params['exporter']]['unit']
            done_sending = False
            while not done_sending:
                try:
                    self._create_transport(params['transport'])
                    transport = self.transports[params['transport']]
                    result = self.ctx.sa.export_to_transport(
                        exporter_id, transport)
                    if result and 'url' in result:
                        print(result['url'])
                    elif result and 'status_url' in result:
                        print(result['status_url'])
                except TransportError as exc:
                    _logger.warning(
                        _("Problem occured when submitting %s report: %s"),
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
                    if self._retry_dialog():
                        self.launcher.transports['c3'].pop('secure_id')
                        continue
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
        return False

    def _get_ui_for_job(self, job):
        class CheckboxUI(NormalUI):
            def considering_job(self, job, job_state):
                pass
        show_out = True
        if self.launcher.output == 'hide-resource-and-attachment':
            if job.plugin in ('local', 'resource', 'attachment'):
                show_out = False
        elif self.launcher.output in ['hide', 'hide-automated']:
            if job.plugin in ('shell', 'local', 'resource', 'attachment'):
                show_out = False
        if 'suppress-output' in job.get_flag_set():
            show_out = False
        if 'use-chunked-io' in job.get_flag_set():
            show_out = True
        if self.ctx.args.dont_suppress_output:
            show_out = True
        return CheckboxUI(self.C.c, show_cmd_output=show_out)

    def register_arguments(self, parser):
        parser.add_argument(
            'launcher', metavar=_('LAUNCHER'), nargs='?',
            help=_('launcher definition file to use'))
        parser.add_argument(
            '--resume', dest='session_id', metavar='SESSION_ID',
            help=SUPPRESS)
        parser.add_argument(
            '--verify', action='store_true',
            help=_('only validate the launcher'))
        parser.add_argument(
            '--title', action='store', metavar='SESSION_NAME',
            help=_('title of the session to use'))
        parser.add_argument(
            '--dont-suppress-output', action='store_true', default=False,
            help=_('Absolutely always show command output'))
        # the next to options are and should be exact copies of what the
        # top-level command offers - this is here so when someone launches
        # checkbox-cli through launcher, they have those options available
        parser.add_argument('-v', '--verbose', action='store_true', help=_(
            'print more logging from checkbox'))
        parser.add_argument('--debug', action='store_true', help=_(
            'print debug messages from checkbox'))



class CheckboxUI(NormalUI):

    def considering_job(self, job, job_state):
        pass


class Run(Command, MainLoopStage):
    name = 'run'

    def register_arguments(self, parser):
        parser.add_argument(
            'PATTERN', nargs="*",
            help=_("run jobs matching the given regular expression"))
        parser.add_argument(
            '--non-interactive', action='store_true',
            help=_("skip tests that require interactivity"))
        parser.add_argument(
            '-f', '--output-format',
            default='com.canonical.plainbox::text',
            metavar=_('FORMAT'),
            help=_('save test results in the specified FORMAT'
                   ' (pass ? for a list of choices)'))
        parser.add_argument(
            '-p', '--output-options', default='',
            metavar=_('OPTIONS'),
            help=_('comma-separated list of options for the export mechanism'
                   ' (pass ? for a list of choices)'))
        parser.add_argument(
            '-o', '--output-file', default='-',
            metavar=_('FILE'),# type=FileType("wb"),
            help=_('save test results to the specified FILE'
                   ' (or to stdout if FILE is -)'))
        parser.add_argument(
            '-t', '--transport',
            metavar=_('TRANSPORT'),
                choices=[_('?')] + list(get_all_transports().keys()),
            help=_('use TRANSPORT to send results somewhere'
                   ' (pass ? for a list of choices)'))
        parser.add_argument(
            '--transport-where',
            metavar=_('WHERE'),
            help=_('where to send data using the selected transport'))
        parser.add_argument(
            '--transport-options',
            metavar=_('OPTIONS'),
            help=_('comma-separated list of key-value options (k=v) to '
                   'be passed to the transport'))

    @property
    def C(self):
        return self._C

    @property
    def sa(self):
        return self.ctx.sa

    @property
    def is_interactive(self):
        """
        Flag indicating that this is an interactive invocation.

        We can then interact with the user when we encounter OUTCOME_UNDECIDED.
        """
        return (sys.stdin.isatty() and sys.stdout.isatty() and not
                self.ctx.args.non_interactive)

    def invoked(self, ctx):
        self._C = Colorizer()
        self.ctx = ctx
        ctx.sa = SessionAssistant(
            "com.canonical:checkbox-cli",
            self.get_cmd_version(),
            "0.99",
            ["restartable"],
        )
        self._configure_restart()
        self.sa.select_providers('*')
        self.sa.start_new_session('checkbox-run')
        tps = self.sa.get_test_plans()
        self._configure_report()
        selection = ctx.args.PATTERN
        if len(selection) == 1 and selection[0] in tps:
            self.just_run_test_plan(selection[0])
        else:
            self.sa.hand_pick_jobs(selection)
            print(self.C.header(_("Running Selected Jobs")))
            self._run_jobs(self.sa.get_dynamic_todo_list())
            # there might have been new jobs instantiated
            while True:
                self.sa.hand_pick_jobs(ctx.args.PATTERN)
                todos = self.sa.get_dynamic_todo_list()
                if not todos:
                    break
                self._run_jobs(self.sa.get_dynamic_todo_list())
        self.sa.finalize_session()
        self._print_results()
        return 0 if self.sa.get_summary()['fail'] == 0 else 1

    def just_run_test_plan(self, tp_id):
        self.sa.select_test_plan(tp_id)
        self.sa.bootstrap()
        print(self.C.header(_("Running Selected Test Plan")))
        self._run_jobs(self.sa.get_dynamic_todo_list())

    def _configure_report(self):
        """Configure transport and exporter."""
        if self.ctx.args.output_format == '?':
            print_objs('exporter')
            raise SystemExit(0)
        if self.ctx.args.transport == '?':
            print(', '.join(get_all_transports()))
            raise SystemExit(0)
        if not self.ctx.args.transport:
            if self.ctx.args.transport_where:
                _logger.error(_(
                    "--transport-where is useless without --transport"))
                raise SystemExit(1)
            if self.ctx.args.transport_options:
                _logger.error(_(
                    "--transport-options is useless without --transport"))
                raise SystemExit(1)
            if self.ctx.args.output_file != '-':
                self.transport = 'file'
                self.transport_where = self.ctx.args.output_file
                self.transport_options = ''
            else:
                self.transport = 'stream'
                self.transport_where = 'stdout'
                self.transport_options = ''
        else:
            if self.ctx.args.transport not in get_all_transports():
                _logger.error("The selected transport %r is not available",
                             self.ctx.args.transport)
                raise SystemExit(1)
            self.transport = self.ctx.args.transport
            self.transport_where = self.ctx.args.transport_where
            self.transport_options = self.ctx.args.transport_options
        self.exporter = self.ctx.args.output_format
        self.exporter_opts = self.ctx.args.output_options


    def _print_results(self):
        all_transports = get_all_transports()
        transport = get_all_transports()[self.transport](
            self.transport_where, self.transport_options)
        print(self.C.header(_("Results")))
        if self.transport == 'file':
            print(_("Saving results to {}").format(self.transport_where))
        elif self.transport == 'certification':
            print(_("Sending results to {}").format(self.transport_where))
        self.sa.export_to_transport(
            self.exporter, transport, self.exporter_opts)

    def _configure_restart(self):
        strategy = detect_restart_strategy()
        snap_name = os.getenv('SNAP_NAME')
        if snap_name:
            # NOTE: This implies that any snap wishing to include a
            # Checkbox snap to be autostarted creates a snapcraft
            # app called "checkbox-cli"
            respawn_cmd = '/snap/bin/{}.checkbox-cli'.format(snap_name)
        else:
            respawn_cmd = sys.argv[0] # entry-point to checkbox
        respawn_cmd += ' --resume {}' # interpolate with session_id
        self.sa.configure_application_restart(
            lambda session_id: [ respawn_cmd.format(session_id)])


class List(Command):
    name = 'list'

    def register_arguments(self, parser):
        parser.add_argument(
            'GROUP', nargs='?',
            help=_("list objects from the specified group"))
        parser.add_argument(
            '-a', '--attrs', default=False, action="store_true",
            help=_("show object attributes"))
        parser.add_argument(
            '-f', '--format', type=str,
            help=_(("output format, as passed to print function. "
                "Use '?' to list possible values")))

    def invoked(self, ctx):
        if ctx.args.GROUP == 'all-jobs':
            if ctx.args.attrs:
                print_objs('job', True)
                filter_fun = lambda u: u.attrs['template_unit'] == 'job'
                print_objs('template', True, filter_fun)
            jobs = get_all_jobs()
            if ctx.args.format == '?':
                all_keys = set()
                for job in jobs:
                    all_keys.update(job.keys())
                print(list(all_keys))
                return
            if not ctx.args.format:
                # setting default in parser.add_argument would apply to all
                # the list invocations. We want default to be present only for
                # the 'all-jobs' group.
                ctx.args.format = 'id: {id}\n{tr_summary}\n'
            for job in jobs:
                unescaped = ctx.args.format.replace(
                    '\\n', '\n').replace('\\t', '\t')
                class DefaultKeyedDict(defaultdict):
                    def __missing__(self, key):
                        return _('<missing {}>').format(key)
                # formatters are allowed to use special field 'unit_type' so
                # let's add it to the job representation
                assert 'unit_type' not in job.keys()
                if job.get('template_unit') == 'job':
                    job['unit_type'] = 'template_job'
                else:
                    job['unit_type'] = 'job'
                print(unescaped.format(**DefaultKeyedDict(None, job)), end='')
            return
        elif ctx.args.format:
            print(_("--format applies only to 'all-jobs' group.  Ignoring..."))
        print_objs(ctx.args.GROUP, ctx.args.attrs)


class ListBootstrapped(Command):
    name = 'list-bootstrapped'

    @property
    def sa(self):
        return self.ctx.sa

    def register_arguments(self, parser):
        parser.add_argument(
            'TEST_PLAN',
            help=_("test-plan id to bootstrap"))
        parser.add_argument(
            '--partial', default=False, action="store_true",
            help=_("print only partial id"))

    def invoked(self, ctx):
        self.ctx = ctx
        self.sa.select_providers('*')
        self.sa.start_new_session('checkbox-listing-ephemeral')
        tps = self.sa.get_test_plans()
        if ctx.args.TEST_PLAN not in tps:
            raise SystemExit('Test plan not found')
        self.sa.select_test_plan(ctx.args.TEST_PLAN)
        self.sa.bootstrap()
        for job_id in self.sa.get_static_todo_list():
            if ctx.args.partial:
                print(self.sa.get_job(job_id).partial_id)
            else:
                print(job_id)


def get_all_jobs():
    root = Explorer(get_providers()).get_object_tree()
    def get_jobs(obj):
        jobs = []
        if obj.group == 'job':
            jobs.append(obj.attrs)
        elif obj.group == 'template' and obj.attrs['template_unit'] == 'job':
            jobs.append(obj.attrs)
        for child in obj.children:
            jobs += get_jobs(child)
        return jobs
    return sorted(get_jobs(root),key=operator.itemgetter('id'))


def print_objs(group, show_attrs=False, filter_fun=None):
    obj = Explorer(get_providers()).get_object_tree()
    indent = ""
    def _show(obj, indent):
        if group is None or obj.group == group:
            # object must satisfy filter_fun (if supplied) to be printed
            if filter_fun and not filter_fun(obj):
                return
            # Display the object name and group
            print("{}{} {!r}".format(indent, obj.group, obj.name))
            indent += "  "
            if show_attrs:
                for key, value in obj.attrs.items():
                    print("{}{:15}: {!r}".format(indent, key, value))
        if obj.children:
            if group is None:
                print("{}{}".format(indent, _("children")))
                indent += "  "
            for child in obj.children:
                _show(child, indent)

    _show(obj, "")
