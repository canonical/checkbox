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
Definition of sub-command classes for checkbox-cli
"""
from argparse import ArgumentTypeError
from argparse import SUPPRESS
from collections import defaultdict
from string import Formatter
from tempfile import TemporaryDirectory
import copy
import fnmatch
import gettext
import json
import logging
import operator
import os
import re
import sys
import tarfile
import time

from plainbox.abc import IJobResult
from plainbox.i18n import ngettext
from plainbox.impl.color import Colorizer
from plainbox.impl.execution import UnifiedRunner
from plainbox.impl.highlevel import Explorer
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.runner import slugify
from plainbox.impl.secure.sudo_broker import sudo_password_provider
from plainbox.impl.session.assistant import SA_RESTARTABLE
from plainbox.impl.session.restart import detect_restart_strategy
from plainbox.impl.session.restart import get_strategy_by_name
from plainbox.impl.session.storage import WellKnownDirsHelper
from plainbox.impl.transport import TransportError
from plainbox.impl.transport import get_all_transports
from plainbox.impl.transport import SECURE_ID_PATTERN

from checkbox_ng.config import load_configs
from checkbox_ng.launcher.stages import MainLoopStage, ReportsStage
from checkbox_ng.launcher.startprovider import (
    EmptyProviderSkeleton, IQN, ProviderSkeleton)
from checkbox_ng.launcher.run import Action
from checkbox_ng.launcher.run import NormalUI
from checkbox_ng.urwid_ui import CategoryBrowser
from checkbox_ng.urwid_ui import ManifestBrowser
from checkbox_ng.urwid_ui import ReRunBrowser
from checkbox_ng.urwid_ui import TestPlanBrowser

_ = gettext.gettext

_logger = logging.getLogger("checkbox-ng.launcher.subcommands")


class Submit():
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
        parser.add_argument(
            "-m", "--message",
            help=_("Submission description"))

    def invoked(self, ctx):
        transport_cls = None
        mode = 'rb'
        options_string = "secure_id={0}".format(ctx.args.secure_id)
        url = ('https://certification.canonical.com/'
               'api/v1/submission/{}/'.format(ctx.args.secure_id))
        submission_file = ctx.args.submission
        if ctx.args.staging:
            url = ('https://certification.staging.canonical.com/'
                   'api/v1/submission/{}/'.format(ctx.args.secure_id))
        elif os.getenv('C3_URL'):
            url = ('{}/{}/'.format(os.getenv('C3_URL'), ctx.args.secure_id))
        from checkbox_ng.certification import SubmissionServiceTransport
        transport_cls = SubmissionServiceTransport
        transport = transport_cls(url, options_string)
        if ctx.args.message:
            tmpdir = TemporaryDirectory()
            with tarfile.open(ctx.args.submission) as tar:
                tar.extractall(tmpdir.name)
            with open(os.path.join(tmpdir.name, 'submission.json')) as f:
                json_payload = json.load(f)
            with open(os.path.join(tmpdir.name, 'submission.json'), 'w') as f:
                json_payload['description'] = ctx.args.message
                json.dump(json_payload, f, sort_keys=True, indent=4)
            new_subm_file = os.path.join(
                tmpdir.name, os.path.basename(ctx.args.submission))
            with tarfile.open(new_subm_file, mode='w:xz') as tar:
                tar.add(tmpdir.name, arcname='')
            submission_file = new_subm_file
        try:
            with open(submission_file, mode) as subm_file:
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


class StartProvider():
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


class Launcher(MainLoopStage, ReportsStage):
    @property
    def sa(self):
        return self.ctx.sa

    @property
    def C(self):
        return self._C

    def get_sa_api_version(self):
        return '0.99'

    def get_sa_api_flags(self):
        return [SA_RESTARTABLE]

    def invoked(self, ctx):
        if ctx.args.version:
            from checkbox_ng.version import get_version_info
            for component, version in get_version_info().items():
                print("{}: {}".format(component, version))
            return
        if ctx.args.verify:
            # validation is always run, so if there were any errors the program
            # exited by now, so validation passed
            print(_("Launcher seems valid."))
            return
        self.configuration = load_configs(ctx.args.launcher)
        logging_level = {
            'normal': logging.WARNING,
            'verbose': logging.INFO,
            'debug': logging.DEBUG,
        }[self.configuration.get_value('ui', 'verbosity')]
        if not ctx.args.verbose and not ctx.args.debug:
            # Command line args take precendence
            logging.basicConfig(level=logging_level)
        try:
            self._C = Colorizer()
            self.ctx = ctx
            # now we have all the correct flags and options, so we need to
            # replace the previously built SA with the defaults
            self._configure_restart(ctx)
            self._prepare_transports()
            ctx.sa.use_alternate_configuration(self.configuration)
            if not self._maybe_resume_session():
                self._start_new_session()
                self._pick_jobs_to_run()
            if not self.ctx.sa.get_static_todo_list():
                return 0
            if 'submission_files' in self.configuration.get_value(
                    'launcher', 'stock_reports'):
                print("Reports will be saved to: {}".format(self.base_dir))
            # we initialize the nb of attempts for all the selected jobs...
            for job_id in self.ctx.sa.get_dynamic_todo_list():
                job_state = self.ctx.sa.get_job_state(job_id)
                job_state.attempts = self.configuration.get_value(
                    'ui', 'max_attempts')
            # ... before running them
            self._run_jobs(self.ctx.sa.get_dynamic_todo_list())
            if self.is_interactive and not self.configuration.get_value(
                'ui', 'auto_retry'):
                while True:
                    if not self._maybe_rerun_jobs():
                        break
            elif self.configuration.get_value('ui', 'auto_retry'):
                while True:
                    if not self._maybe_auto_rerun_jobs():
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
        return (self.configuration.get_value('ui', 'type')  == 'interactive'
                and sys.stdin.isatty() and sys.stdout.isatty())

    def _configure_restart(self, ctx):
        if SA_RESTARTABLE not in self.get_sa_api_flags():
            return
        if self.configuration.get_value('restart', 'strategy'):
            try:
                cls = get_strategy_by_name(
                    self.configuration.get_value('restart', 'strategy'))
                strategy = cls(**self.configuration.get_strategy_kwargs())
                ctx.sa.use_alternate_restart_strategy(strategy)
            except KeyError:
                _logger.warning(_('Unknown restart strategy: %s', (
                    self.launcher.restart_strategy)))
                _logger.warning(_(
                    'Using automatically detected restart strategy'))
                try:
                    strategy = detect_restart_strategy(session_type='local')
                except LookupError as exc:
                    _logger.warning(exc)
                    _logger.warning(_('Automatic restart disabled!'))
                    strategy = None
        else:
            strategy = detect_restart_strategy(session_type='local')
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
                respawn_cmd = sys.argv[0]  # entry-point to checkbox
            respawn_cmd += " launcher "
            if ctx.args.launcher:
                respawn_cmd += os.path.abspath(ctx.args.launcher) + ' '
            respawn_cmd += '--resume {}'  # interpolate with session_id
            ctx.sa.configure_application_restart(
                lambda session_id: [respawn_cmd.format(session_id)], 'local')

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
        title = self.ctx.args.title or self.configuration.get_value(
            'launcher', 'session_title')
        title = title or self.configuration.get_value('launcher', 'app_id')
        if self.configuration.get_value('launcher', 'app_version'):
            title += ' {}'.format(self.configuration.get_value(
                'launcher', 'app_version'))
        runner_kwargs = {
            'normal_user_provider': lambda: self.configuration.get_value(
                'daemon', 'normal_user'),
            'password_provider': sudo_password_provider.get_sudo_password,
            'stdin': None,
        }
        self.ctx.sa.start_new_session(title, UnifiedRunner, runner_kwargs)
        if self.configuration.get_value('test plan', 'forced'):
            tp_id = self.configuration.get_value('test plan', 'unit')
            if tp_id not in self.ctx.sa.get_test_plans():
                _logger.error(_(
                    'The test plan "%s" is not available!'), tp_id)
                raise SystemExit(1)
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
        description = self.ctx.args.message or self.configuration.get_value(
                'launcher', 'session_desc')
        self.ctx.sa.update_app_blob(json.dumps(
            {'testplan_id': tp_id,
             'description': description}).encode("UTF-8"))
        bs_jobs = self.ctx.sa.get_bootstrap_todo_list()
        self._run_bootstrap_jobs(bs_jobs)
        self.ctx.sa.finish_bootstrap()

    def _delete_old_sessions(self, ids):
        completed_ids = [s[0] for s in self.ctx.sa.get_old_sessions()]
        self.ctx.sa.delete_sessions(completed_ids + ids)

    def _interactively_pick_test_plan(self):
        test_plan_ids = self.ctx.sa.get_test_plans()
        filtered_tp_ids = set()
        for filter in self.configuration.get_value('test plan', 'filter'):
            filtered_tp_ids.update(fnmatch.filter(test_plan_ids, filter))
        tp_info_list = self._generate_tp_infos(filtered_tp_ids)
        if not tp_info_list:
            print(self.C.RED(_("There were no test plans to select from!")))
            return
        selected_tp = TestPlanBrowser(
            _("Select test plan"), tp_info_list,
            self.configuration.get_value('test plan', 'unit')).run()
        return selected_tp

    def _strtobool(self, val):
        return val.lower() in ('y', 'yes', 't', 'true', 'on', '1')

    def _pick_jobs_to_run(self):
        if self.configuration.get_value('test selection', 'forced'):
            if self.configuration.manifest:
                self.ctx.sa.save_manifest(
                    {manifest_id:
                     self._strtobool(
                         self.configuration.manifest[manifest_id]) for
                     manifest_id in self.configuration.manifest}
                )
            # by default all tests are selected; so we're done here
            return
        job_list = [self.ctx.sa.get_job(job_id) for job_id in
                    self.ctx.sa.get_static_todo_list()]
        if not job_list:
            print(self.C.RED(_("There were no tests to select from!")))
            return
        test_info_list = self._generate_job_infos(job_list)
        wanted_set = CategoryBrowser(
            _("Choose tests to run on your system:"), test_info_list).run()
        manifest_repr = self.ctx.sa.get_manifest_repr()
        if manifest_repr:
            manifest_answers = ManifestBrowser(
                "System Manifest:", manifest_repr).run()
            self.ctx.sa.save_manifest(manifest_answers)
        # no need to set an alternate selection if the job list not changed
        if len(test_info_list) == len(wanted_set):
            return
        # NOTE: tree.selection is correct but ordered badly. To retain
        # the original ordering we should just treat it as a mask and
        # use it to filter jobs from get_static_todo_list.
        job_id_list = [job_id for job_id in self.ctx.sa.get_static_todo_list()
                       if job_id in wanted_set]
        self.ctx.sa.use_alternate_selection(job_id_list)

    def _handle_last_job_after_resume(self, last_job):
        if last_job is None:
            return
        if self.ctx.args.session_id:
            # session_id is present only if auto-resume is used
            result_dict = {
                'outcome': IJobResult.OUTCOME_PASS,
                'comments': _("Automatically passed after resuming execution"),
            }
            session_share = WellKnownDirsHelper.session_share(
                self.ctx.sa.get_session_id())
            result_path = os.path.join(session_share, '__result')
            if os.path.exists(result_path):
                try:
                    with open(result_path, 'rt') as f:
                        result_dict = json.load(f)
                        # the only really important field in the result is
                        # 'outcome' so let's make sure it doesn't contain
                        # anything stupid
                        if result_dict.get('outcome') not in [
                                'pass', 'fail', 'skip']:
                            result_dict['outcome'] = IJobResult.OUTCOME_PASS
                except json.JSONDecodeError as e:
                    pass
            print(_("Automatically resuming session. "
                    "Outcome of the previous job: {}".format(
                        result_dict['outcome'])))
            result = MemoryJobResult(result_dict)
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

    def _maybe_auto_rerun_jobs(self):
        rerun_candidates = self.ctx.sa.get_rerun_candidates('auto')
        # bail-out early if no job qualifies for rerunning
        if not rerun_candidates:
            return False
        # we wait before retrying
        delay = self.configuration.get_value('ui', 'delay_before_retry')
        _logger.info(_("Waiting {} seconds before retrying failed"
                       " jobs...".format(delay)))
        time.sleep(delay)
        candidates = self.ctx.sa.prepare_rerun_candidates(rerun_candidates)
        self._run_jobs(candidates)
        return True

    def _maybe_rerun_jobs(self):
        # create a list of jobs that qualify for rerunning
        rerun_candidates = self.ctx.sa.get_rerun_candidates('manual')
        # bail-out early if no job qualifies for rerunning
        if not rerun_candidates:
            return False
        test_info_list = self._generate_job_infos(rerun_candidates)
        wanted_set = ReRunBrowser(
            _("Select jobs to re-run"), test_info_list, rerun_candidates).run()
        if not wanted_set:
            # nothing selected - nothing to run
            return False
        rerun_candidates = [
            self.ctx.sa.get_job(job_id) for job_id in wanted_set]
        rerun_candidates = self.ctx.sa.prepare_rerun_candidates(
            rerun_candidates)
        # include resource jobs that selected jobs depend on
        self._run_jobs(rerun_candidates)
        return True

    def _get_ui_for_job(self, job):
        class CheckboxUI(NormalUI):
            def considering_job(self, job, job_state):
                pass
        show_out = True
        output = self.configuration.get_value('ui', 'output')
        if output == 'hide-resource-and-attachment':
            if job.plugin in ('local', 'resource', 'attachment'):
                show_out = False
        elif output in ['hide', 'hide-automated']:
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
            "-m", "--message",
            help=_("submission description"))
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
        parser.add_argument('--clear-cache', action='store_true', help=_(
            'remove cached results from the system'))
        parser.add_argument('--clear-old-sessions', action='store_true', help=_(
            "remove previous sessions' data"))
        parser.add_argument('--version', action='store_true', help=_(
            "show program's version information and exit"))


class CheckboxUI(NormalUI):

    def considering_job(self, job, job_state):
        pass


class Run(MainLoopStage):
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
            metavar=_('FILE'),  # type=FileType("wb"),
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
        parser.add_argument(
            '--title', action='store', metavar='SESSION_NAME',
            help=_('title of the session to use'))
        parser.add_argument(
            "-m", "--message",
            help=_("submission description"))

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
        try:
            self._C = Colorizer()
            self.ctx = ctx

            self._configure_restart()
            config = load_configs()
            self.sa.use_alternate_configuration(config)
            self.sa.start_new_session(
                self.ctx.args.title or 'checkbox-run',
                UnifiedRunner)
            tps = self.sa.get_test_plans()
            self._configure_report()
            selection = ctx.args.PATTERN
            submission_message = self.ctx.args.message
            if len(selection) == 1 and selection[0] in tps:
                self.ctx.sa.update_app_blob(json.dumps(
                    {'testplan_id': selection[0],
                     'description': submission_message}).encode("UTF-8"))
                self.just_run_test_plan(selection[0])
            else:
                self.ctx.sa.update_app_blob(json.dumps(
                    {'description': submission_message}).encode("UTF-8"))
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
        except KeyboardInterrupt:
            return 1

    def just_run_test_plan(self, tp_id):
        self.sa.select_test_plan(tp_id)
        self.sa.bootstrap()
        print(self.C.header(_("Running Selected Test Plan")))
        self._run_jobs(self.sa.get_dynamic_todo_list())

    def _configure_report(self):
        """Configure transport and exporter."""
        if self.ctx.args.output_format == '?':
            print_objs('exporter', self.ctx.sa)
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
        strategy = detect_restart_strategy(session_type='local')
        snap_name = os.getenv('SNAP_NAME')
        if snap_name:
            # NOTE: This implies that any snap wishing to include a
            # Checkbox snap to be autostarted creates a snapcraft
            # app called "checkbox-cli"
            respawn_cmd = '/snap/bin/{}.checkbox-cli'.format(snap_name)
        else:
            respawn_cmd = sys.argv[0]  # entry-point to checkbox
        respawn_cmd += ' --resume {}'  # interpolate with session_id
        self.sa.configure_application_restart(
            lambda session_id: [respawn_cmd.format(session_id)], 'local')


class List():
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
                print_objs('job', ctx.sa, True)

                def filter_fun(u): return u.attrs['template_unit'] == 'job'
                print_objs('template', ctx.sa, True, filter_fun)
            jobs = get_all_jobs(ctx.sa)
            if ctx.args.format == '?':
                all_keys = set()
                for job in jobs:
                    all_keys.update(job.keys())
                print(_('Available fields are:'))
                print(', '.join(sorted(list(all_keys))))
                return
            if not ctx.args.format:
                # setting default in parser.add_argument would apply to all
                # the list invocations. We want default to be present only for
                # the 'all-jobs' group.
                ctx.args.format = 'id: {full_id}\n{_summary}\n'
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
                print(Formatter().vformat(
                    unescaped, (), DefaultKeyedDict(None, job)), end='')
            return
        elif ctx.args.format:
            print(_("--format applies only to 'all-jobs' group.  Ignoring..."))
        print_objs(ctx.args.GROUP, ctx.sa, ctx.args.attrs)


class ListBootstrapped():
    @property
    def sa(self):
        return self.ctx.sa

    def register_arguments(self, parser):
        parser.add_argument(
            'TEST_PLAN',
            help=_("test-plan id to bootstrap"))
        parser.add_argument(
            '-f', '--format', type=str, default="{full_id}\n",
            help=_(("output format, as passed to print function. "
                    "Use '?' to list possible values")))

    def invoked(self, ctx):
        self.ctx = ctx
        self.sa.start_new_session('checkbox-listing-ephemeral')
        tps = self.sa.get_test_plans()
        if ctx.args.TEST_PLAN not in tps:
            raise SystemExit('Test plan not found')
        self.sa.select_test_plan(ctx.args.TEST_PLAN)
        self.sa.bootstrap()
        jobs = []
        for job in self.sa.get_static_todo_list():
            job_unit = self.sa.get_job(job)
            attrs = job_unit._raw_data.copy()
            attrs['full_id'] = job_unit.id
            attrs['id'] = job_unit.partial_id
            jobs.append(attrs)
        if ctx.args.format == '?':
            all_keys = set()
            for job in jobs:
                all_keys.update(job.keys())
            print(_('Available fields are:'))
            print(', '.join(sorted(list(all_keys))))
            return
        if ctx.args.format:
            for job in jobs:
                unescaped = ctx.args.format.replace(
                    '\\n', '\n').replace('\\t', '\t')

                class DefaultKeyedDict(defaultdict):
                    def __missing__(self, key):
                        return _('<missing {}>').format(key)
                print(Formatter().vformat(
                    unescaped, (), DefaultKeyedDict(None, job)), end='')
        else:
            for job_id in jobs:
                print(job_id)


class TestPlanExport():

    @property
    def sa(self):
        return self.ctx.sa

    def register_arguments(self, parser):
        parser.add_argument(
            'TEST_PLAN',
            help=_("test-plan id to bootstrap"))
        parser.add_argument(
            '-n', '--nofake', action='store_true')

    def invoked(self, ctx):
        self.ctx = ctx
        if ctx.args.nofake:
            self.sa.start_new_session('tp-export-ephemeral')
        else:
            from plainbox.impl.execution import FakeJobRunner
            self.sa.start_new_session('tp-export-ephemeral', FakeJobRunner)
            self.sa._context.state._fake_resources = True
        tps = self.sa.get_test_plans()
        if ctx.args.TEST_PLAN not in tps:
            raise SystemExit('Test plan not found')
        self.sa.select_test_plan(ctx.args.TEST_PLAN)
        self.sa.bootstrap()
        path = self.sa.export_to_file(
            'com.canonical.plainbox::tp-export', [],
            self.sa._manager.storage.location,
            slugify(self.sa._manager.test_plans[0].name))
        print(path)


def get_all_jobs(sa):
    providers = sa.get_selected_providers()
    root = Explorer(providers).get_object_tree()

    def get_jobs(obj):
        jobs = []
        if obj.group == 'job' or (
                obj.group == 'template' and obj.attrs['template_unit'] == 'job'):
            attrs = dict(obj._impl._raw_data.copy())
            attrs['full_id'] = obj.name
            jobs.append(attrs)
        for child in obj.children:
            jobs += get_jobs(child)
        return jobs
    return sorted(get_jobs(root), key=operator.itemgetter('full_id'))


def print_objs(group, sa, show_attrs=False, filter_fun=None):
    providers = sa.get_selected_providers()
    obj = Explorer(providers).get_object_tree()

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
