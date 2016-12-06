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
import copy
import datetime
import fnmatch
import gettext
import json
import logging
import os
import re
import sys

from guacamole import Command

from plainbox.abc import IJobResult
from plainbox.i18n import ngettext
from plainbox.impl.color import Colorizer
from plainbox.impl.commands.inv_run import Action
from plainbox.impl.commands.inv_run import NormalUI
from plainbox.impl.commands.inv_startprovider import (
    EmptyProviderSkeleton, IQN, ProviderSkeleton)
from plainbox.impl.developer import UsageExpectation
from plainbox.impl.highlevel import Explorer
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.session.assistant import SessionAssistant, SA_RESTARTABLE
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.qualifiers import select_jobs
from plainbox.impl.secure.qualifiers import FieldQualifier
from plainbox.impl.secure.qualifiers import PatternMatcher
from plainbox.impl.session.assistant import SA_RESTARTABLE
from plainbox.impl.session.jobs import InhibitionCause
from plainbox.impl.session.restart import detect_restart_strategy
from plainbox.impl.session.restart import get_strategy_by_name
from plainbox.impl.transport import TransportError
from plainbox.impl.transport import InvalidSecureIDError
from plainbox.impl.transport import get_all_transports
from plainbox.public import get_providers

from checkbox_ng.launcher.stages import MainLoopStage
from checkbox_ng.misc import SelectableJobTreeNode
from checkbox_ng.ui import ScrollableTreeNode
from checkbox_ng.ui import ShowMenu
from checkbox_ng.ui import ShowRerun

_ = gettext.gettext

_logger = logging.getLogger("checkbox-ng.launcher.subcommands")


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

    app_id = '2016.com.canonical:checkbox-cli'

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
        if not self.launcher.launcher_version:
            # it's a legacy launcher, use legacy way of running commands
            from checkbox_ng.tools import CheckboxLauncherTool
            raise SystemExit(CheckboxLauncherTool().main(sys.argv[1:]))
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
            self._configure_restart(ctx)
            self._prepare_transports()
            ctx.sa.use_alternate_configuration(self.launcher)
            ctx.sa.select_providers(*self.launcher.providers)
            if not self._maybe_resume_session():
                self._start_new_session()
                self._pick_jobs_to_run()
            self.base_dir = os.path.join(
                os.getenv(
                    'XDG_DATA_HOME', os.path.expanduser("~/.local/share/")),
                "checkbox-ng")
            if 'submission_files' in self.launcher.stock_reports:
                print("Reports will be saved to: {}".format(self.base_dir))
            self._run_jobs(self.ctx.sa.get_dynamic_todo_list())
            if self.is_interactive:
                while True:
                    if not self._maybe_rerun_jobs():
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
            ctx.sa.configure_application_restart(
                lambda session_id: [
                    ' '.join([
                        os.path.abspath(__file__),
                        os.path.abspath(ctx.args.launcher),
                        "--resume", session_id])
                ])

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
                Action('c', _("create new session"), 'create')
            ], _("Do you want to resume session {0!a}?").format(candidate.id))
            if cmd == 'next':
                continue
            elif cmd == 'create' or cmd is None:
                return False
            elif cmd == 'resume':
                self._resume_session(candidate)
                return True

    def _resume_session(self, session):
        metadata = self.ctx.sa.resume_session(session.id)
        app_blob = json.loads(metadata.app_blob.decode("UTF-8"))
        test_plan_id = app_blob['testplan_id']
        last_job = metadata.running_job_name
        self.ctx.sa.select_test_plan(test_plan_id)
        self.ctx.sa.bootstrap()
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
        self.ctx.sa.bootstrap()

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
        preselected_indecies = []
        if self.launcher.test_plan_default_selection:
            try:
                preselected_indecies = [test_plan_names.index(
                    self.ctx.sa.get_test_plan(
                        self.launcher.test_plan_default_selection).name)]
            except KeyError:
                _logger.warning(_('%s test plan not found'),
                                self.launcher.test_plan_default_selection)
                preselected_indecies = []
        try:
            selected_index = self.ctx.display.run(
                ShowMenu(_("Select test plan"),
                         test_plan_names, preselected_indecies,
                         multiple_allowed=False))[0]
        except IndexError:
            return None
        return filtered_tp_ids[selected_index]

    def _pick_jobs_to_run(self):
        if self.launcher.test_selection_forced:
            # by default all tests are selected; so we're done here
            return
        job_list = [self.ctx.sa.get_job(job_id) for job_id in
                    self.ctx.sa.get_static_todo_list()]
        tree = SelectableJobTreeNode.create_simple_tree(self.ctx.sa, job_list)
        for category in tree.get_descendants():
            category.expanded = False
        title = _('Choose tests to run on your system:')
        self.ctx.display.run(ScrollableTreeNode(tree, title))
        # NOTE: tree.selection is correct but ordered badly. To retain
        # the original ordering we should just treat it as a mask and
        # use it to filter jobs from get_static_todo_list.
        wanted_set = frozenset([job.id for job in tree.selection])
        job_id_list = [job_id for job_id in self.ctx.sa.get_static_todo_list()
                       if job_id in wanted_set]
        self.ctx.sa.use_alternate_selection(job_id_list)

    def _handle_last_job_after_resume(self, last_job):
        if last_job is None:
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

    def _maybe_rerun_jobs(self):
        # create a list of jobs that qualify for rerunning
        rerun_candidates = self._get_rerun_candidates()
        # bail-out early if no job qualifies for rerunning
        if not rerun_candidates:
            return False
        tree = SelectableJobTreeNode.create_simple_tree(self.ctx.sa,
                                                        rerun_candidates)
        # nothing to select in root node and categories - bailing out
        if not tree.jobs and not tree._categories:
            return False
        # deselect all by default
        tree.set_descendants_state(False)
        self.ctx.display.run(ShowRerun(tree, _("Select jobs to re-run")))
        wanted_set = frozenset(tree.selection)
        if not wanted_set:
            # nothing selected - nothing to run
            return False
        rerun_candidates = []
        # include resource jobs that selected jobs depend on
        resources_to_rerun = []
        for job in wanted_set:
            job_state = self.ctx.sa.get_job_state(job.id)
            for inhibitor in job_state.readiness_inhibitor_list:
                if inhibitor.cause == InhibitionCause.FAILED_DEP:
                    resources_to_rerun.append(inhibitor.related_job)
        # reset outcome of jobs that are selected for re-running
        for job in list(wanted_set) + resources_to_rerun:
            self.ctx.sa.get_job_state(job.id).result = MemoryJobResult({})
            rerun_candidates.append(job.id)
        self._run_jobs(rerun_candidates)
        return True

    def _get_rerun_candidates(self):
        """Get all the tests that might be selected for rerunning."""
        def rerun_predicate(job_state):
            return job_state.result.outcome in (
                IJobResult.OUTCOME_FAIL, IJobResult.OUTCOME_CRASH,
                IJobResult.OUTCOME_NOT_SUPPORTED, IJobResult.OUTCOME_SKIP)
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
                'unit': '2013.com.canonical.plainbox::text'}
            self.launcher.transports['stdout'] = {
                'type': 'stream', 'stream': 'stdout'}
            # '1_' prefix ensures ordering amongst other stock reports. This
            # report name does not appear anywhere (because of forced: yes)
            self.launcher.reports['1_text_to_screen'] = {
                'transport': 'stdout', 'exporter': 'text', 'forced': 'yes'}
        elif report == 'certification':
            self.launcher.exporters['hexr'] = {
                'unit': '2013.com.canonical.plainbox::hexr'}
            self.launcher.transports['c3'] = {
                'type': 'certification',
                'secure_id': self.launcher.transports.get('c3', {}).get(
                    'secure_id', None)}
            self.launcher.reports['upload to certification'] = {
                'transport': 'c3', 'exporter': 'hexr'}
        elif report == 'certification-staging':
            self.launcher.exporters['hexr'] = {
                'unit': '2013.com.canonical.plainbox::hexr'}
            self.launcher.transports['c3-staging'] = {
                'type': 'certification',
                'secure_id': self.launcher.transports.get('c3', {}).get(
                    'secure_id', None),
                'staging': 'yes'}
            self.launcher.reports['upload to certification-staging'] = {
                'transport': 'c3-staging', 'exporter': 'hexr'}
        elif report == 'submission_files':
            # LP:1585326 maintain isoformat but removing ':' chars that cause
            # issues when copying files.
            isoformat = "%Y-%m-%dT%H.%M.%S.%f"
            timestamp = datetime.datetime.utcnow().strftime(isoformat)
            if not os.path.exists(self.base_dir):
                os.makedirs(self.base_dir)
            for exporter, file_ext in [('hexr', '.xml'), ('html', '.html'),
                                       ('junit', '.junit.xml'),
                                       ('xlsx', '.xlsx'), ('tar', '.tar.xz')]:
                path = os.path.join(self.base_dir, ''.join(
                    ['submission_', timestamp, file_ext]))
                self.launcher.transports['{}_file'.format(exporter)] = {
                    'type': 'file',
                    'path': path}
                if exporter not in self.launcher.exporters:
                    self.launcher.exporters[exporter] = {
                        'unit': '2013.com.canonical.plainbox::{}'.format(
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
                self.launcher.transports[transport]['path'])
        elif tr_type == 'stream':
            self.transports[transport] = cls(
                self.launcher.transports[transport]['stream'])
        elif tr_type == 'certification':
            if self.launcher.transports[transport].get('staging', False):
                url = ('https://certification.staging.canonical.com/'
                       'submissions/submit/')
            else:
                url = ('https://certification.canonical.com/'
                       'submissions/submit/')
            secure_id = self.launcher.transports[transport].get(
                'secure_id', None)
            if not secure_id and self.is_interactive:
                secure_id = input(self.C.BLUE(_('Enter secure-id:')))
            if secure_id:
                options = "secure_id={}".format(secure_id)
            else:
                options = ""
            self.transports[transport] = cls(url, options)

    def _export_results(self):
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
            default='2013.com.canonical.plainbox::text',
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
        self.sa.select_providers('*')
        self.sa.start_new_session('checkbox-run')
        tps = self.sa.get_test_plans()
        self._configure_report()
        selection = ctx.args.PATTERN
        if len(selection) == 1 and selection[0] in tps:
            self.just_run_test_plan(selection[0])
        else:
            self.run_matching_jobs(selection)
        self.sa.finalize_session()
        self._print_results()
        return 0 if self.sa.get_summary()['fail'] == 0 else 1

    def just_run_test_plan(self, tp_id):
        self.sa.select_test_plan(tp_id)
        self.sa.bootstrap()
        print(self.C.header(_("Running Selected Test Plan")))
        self._run_jobs(self.sa.get_dynamic_todo_list())

    def run_matching_jobs(self, patterns):
        # XXX: SessionAssistant doesn't allow running hand-picked list of jobs
        # this is why this method touches SA's internal to manipulate state, so
        # those jobs may be run
        qualifiers = []
        for pattern in patterns:
            qualifiers.append(FieldQualifier('id', PatternMatcher(
                '^{}$'.format(pattern)), Origin('args')))
        jobs = select_jobs(self.sa._context.state.job_list, qualifiers)
        self.sa._context.state.update_desired_job_list(jobs)
        UsageExpectation.of(self.sa).allowed_calls = (
            self.sa._get_allowed_calls_in_normal_state())
        print(self.C.header(_("Running Selected Jobs")))
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


class List(Command):
    name = 'list'

    def register_arguments(self, parser):
        parser.add_argument(
            'GROUP', nargs='?',
            help=_("list objects from the specified group"))
        parser.add_argument(
            '-a', '--attrs', default=False, action="store_true",
            help=_("show object attributes"))

    def invoked(self, ctx):
        print_objs(ctx.args.GROUP, ctx.args.attrs)


def print_objs(group, show_attrs=False):
    obj = Explorer(get_providers()).get_object_tree()
    indent = ""
    def _show(obj, indent):
        if group is None or obj.group == group:
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
