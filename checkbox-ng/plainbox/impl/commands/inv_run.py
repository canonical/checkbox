# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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
:mod:`plainbox.impl.commands.run` -- run sub-command
====================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from shutil import copyfileobj
import collections
import datetime
import io
import itertools
import logging
import os
import sys
import time

from plainbox.abc import IJobResult
from plainbox.abc import IJobRunnerUI
from plainbox.i18n import gettext as _
from plainbox.i18n import ngettext
from plainbox.i18n import pgettext as C_
from plainbox.impl.color import Colorizer
from plainbox.impl.commands.inv_checkbox import CheckBoxInvocationMixIn
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.exporter import ByteStringStreamTranslator
from plainbox.impl.exporter.text import TextSessionStateExporter
from plainbox.impl.result import JobResultBuilder
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.result import tr_outcome
from plainbox.impl.runner import JobRunner
from plainbox.impl.session import SessionManager
from plainbox.impl.session import SessionMetaData
from plainbox.impl.session import SessionPeekHelper
from plainbox.impl.session import SessionResumeError
from plainbox.impl.session import SessionStorageRepository
from plainbox.impl.transport import get_all_transports
from plainbox.impl.transport import TransportError


logger = logging.getLogger("plainbox.commands.run")


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
        print(self.C.BLACK(line.decode("UTF-8", "ignore")),
              end='', file=stream)
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
            print(self.C.CYAN(_("Purpose:")))
            print(self.C.CYAN(job.tr_purpose()))
        else:
            self.notify_about_description(job)

    def notify_about_steps(self, job):
        if job.tr_steps() is not None:
            print(self.C.CYAN(_("Steps:")))
            print(self.C.CYAN(job.tr_steps()))

    def notify_about_verification(self, job):
        if job.tr_verification() is not None:
            print(self.C.CYAN(_("Verification:")))
            print(self.C.CYAN(job.tr_verification()))

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


class RunInvocation(CheckBoxInvocationMixIn):
    """
    Invocation of the 'plainbox run' command.

    attr ns:
        The argparse namespace obtained from RunCommand
    attr _manager:
        The SessionManager object
    attr _runner:
        The JobRunner object
    attr _exporter:
        A ISessionStateExporter of some kind
    attr _transport:
        A ISessionStateTransport of some kind (optional)
    attr _backtrack_and_run_missing:
        A flag indicating that we should run over all the jobs in the
        self.state.run_list again, set every time a job is added. Reset every
        time the loop-over-all-jobs is started.
    """

    def __init__(self, provider_loader, config_loader, ns, color):
        super().__init__(provider_loader, config_loader)
        self.ns = ns
        self._manager = None
        self._runner = None
        self._exporter = None
        self._transport = None
        self._backtrack_and_run_missing = True
        self._color = color
        self._test_plan = self.find_test_plan()
        self.C = Colorizer(color)

    @property
    def manager(self):
        """
        SessionManager object of the current session
        """
        return self._manager

    @property
    def runner(self):
        """
        JobRunner object of the current session
        """
        return self._runner

    @property
    def state(self):
        """
        SessionState object of the current session
        """
        return self.manager.state

    @property
    def metadata(self):
        """
        SessionMetaData object of the current session
        """
        return self.state.metadata

    @property
    def storage(self):
        """
        SessionStorage object of the current session
        """
        return self.manager.storage

    @property
    def exporter(self):
        """
        The ISessionStateExporter of the current session
        """
        return self._exporter

    @property
    def transport(self):
        """
        The ISessionStateTransport of the current session (optional)
        """
        return self._transport

    @property
    def is_interactive(self):
        """
        Flag indicating that this is an interactive invocation and we can
        interact with the user when we encounter OUTCOME_UNDECIDED
        """
        return (sys.stdin.isatty() and sys.stdout.isatty() and not
                self.ns.non_interactive)

    def run(self):
        ns = self.ns
        if ns.transport == _('?'):
            self._print_transport_list(ns)
            return 0
        else:
            return self.do_normal_sequence()

    def do_normal_sequence(self):
        """
        Proceed through normal set of steps that are required to runs jobs
        """
        # Create transport early so that we can handle bugs before starting the
        # session.
        self.create_transport()
        if self.is_interactive:
            resumed = self.maybe_resume_session()
        else:
            self.create_manager(None)
            resumed = False
        if self.ns.output_options == _('?'):
            self._print_output_option_list(self.ns)
            return 0
        elif self.ns.output_format == _('?'):
            self._print_output_format_list(self.ns)
            return 0
        if self.ns.output_format not in self.manager.exporter_map:
            print(_("invalid choice: '{}'".format(self.ns.output_format)))
            self._print_output_format_list(self.ns)
            return 1
        # Create exporter after we get a session to query the manager and get
        # all exporter units
        self.create_exporter()
        # Create the job runner so that we can do stuff
        self.create_runner()
        # Set the effective category for each job
        self.set_effective_categories()
        # If we haven't resumed then do some one-time initialization
        if not resumed:
            # Store the application-identifying meta-data and checkpoint the
            # session.
            self.store_application_metadata()
            self.metadata.flags.add(SessionMetaData.FLAG_INCOMPLETE)
            self.manager.checkpoint()
            # Select all the jobs that we are likely to run. This is the
            # initial selection as we haven't started any jobs yet. Local jobs
            # will cause that to happen again.
            self.do_initial_job_selection()
        # Print out our estimates
        self.print_estimated_duration()
        # Maybe ask the secure launcher to prompt for the password now. This is
        # imperfect as we are going to run local jobs and we cannot see if they
        # might need root or not. This cannot be fixed before template jobs are
        # added and local jobs deprecated and removed (at least not being a
        # part of the session we want to execute).
        self.maybe_warm_up_authentication()
        # Iterate through the run list and run jobs if possible. This function
        # also implements backtrack to run new jobs that were added (and
        # selected) at runtime. When it exits all the jobs on the run list have
        # a result.
        self.run_all_selected_jobs()
        self.metadata.flags.remove(SessionMetaData.FLAG_INCOMPLETE)
        self.manager.checkpoint()
        # Export the result of the session and pass it to the transport to
        # finish the test run.
        self.export_and_send_results()
        self.metadata.flags.add(SessionMetaData.FLAG_SUBMITTED)
        self.manager.checkpoint()
        # FIXME: sensible return value
        return 0

    def maybe_resume_session(self):
        # Try to use the first session that can be resumed if the user agrees
        resume_storage_list = self.get_resume_candidates()
        resume_storage = None
        resumed = False
        if resume_storage_list:
            print(self.C.header(_("Resume Incomplete Session")))
            print(ngettext(
                "There is {0} incomplete session that might be resumed",
                "There are {0} incomplete sessions that might be resumed",
                len(resume_storage_list)
            ).format(len(resume_storage_list)))
        for resume_storage in resume_storage_list:
            # Skip sessions that the user doesn't want to resume
            cmd = self._pick_action_cmd([
                Action('r', _("resume this session"), 'resume'),
                Action('n', _("next session"), 'next'),
                Action('c', _("create new session"), 'create')
            ], _("Do you want to resume session {0!a}?").format(
                resume_storage.id))
            if cmd == 'resume':
                pass
            elif cmd == 'next':
                continue
            elif cmd == 'create' or cmd is None:
                self.create_manager(None)
                break
            # Skip sessions that cannot be resumed
            try:
                self.create_manager(resume_storage)
            except SessionResumeError:
                cmd = self._pick_action_cmd([
                    Action('i', _("ignore this problem"), 'ignore'),
                    Action('e', _("erase this session"), 'erase')])
                if cmd == 'erase':
                    resume_storage.remove()
                    print(_("Session removed"))
                continue
            else:
                resumed = True
            # If we resumed maybe not rerun the same, probably broken job
            if resume_storage is not None:
                self.handle_last_job_after_resume()
            # Finally ignore other sessions that can be resumed
            break
        else:
            if resume_storage is not None and not self.ask_for_new_session():
                # TRANSLATORS: This is the exit message
                raise SystemExit(_("Session not resumed"))
            # Create a fresh session if nothing got resumed
            self.create_manager(None)
        return resumed

    def _print_output_format_list(self, ns):
        print(_("Available output formats:"))
        for id, exporter in self.manager.exporter_map.items():
            print("{} - {}".format(id, exporter.summary))

    def _print_output_option_list(self, ns):
        print(_("Each format may support a different set of options"))
        for name, exporter in self.manager.exporter_map.items():
            print("{}: {}".format(
                name, ", ".join(exporter.exporter_cls.supported_option_list)))

    def _print_transport_list(self, ns):
        print(_("Available transports: {}").format(
            ', '.join(get_all_transports())))

    def get_resume_candidates(self):
        """
        Look at all of the suspended sessions and pick a list of candidates
        that could be used to resume the session now.
        """
        storage_list = []
        for storage in SessionStorageRepository().get_storage_list():
            data = storage.load_checkpoint()
            if len(data) == 0:
                continue
            try:
                metadata = SessionPeekHelper().peek(data)
            except SessionResumeError as exc:
                logger.warning(_("Corrupted session %s: %s"), storage.id, exc)
            else:
                if (metadata.app_id == self.expected_app_id
                        and metadata.title == self.expected_session_title
                        and SessionMetaData.FLAG_INCOMPLETE in metadata.flags):
                    storage_list.append(storage)
        return storage_list

    def ask_for_confirmation(self, message):
        return self._pick_action_cmd([
            Action('y', _("yes"), True),
            Action('n', _("no"), False)
        ], message)

    def ask_for_new_session(self):
        return self.ask_for_confirmation(
            _("Do you want to start a new session?"))

    def handle_last_job_after_resume(self):
        last_job = self.metadata.running_job_name
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
            self.state.update_job_result(
                self.state.job_state_map[last_job].job, result)
            self.metadata.running_job_name = None
            self.manager.checkpoint()

    def create_exporter(self):
        """
        Create the ISessionStateExporter based on the command line options

        This sets the attr:`_exporter`.
        """
        if self.ns.output_options:
            option_list = self.ns.output_options.split(',')
        else:
            option_list = None
        self._exporter = self.manager.create_exporter(
            self.ns.output_format, option_list)

    def create_transport(self):
        """
        Create the ISessionStateTransport based on the command line options

        This sets the attr:`_transport`.
        """
        if self.ns.transport is None:
            return
        # XXX: perhaps we should be more vocal about it?
        if self.ns.transport not in get_all_transports():
            logger.error("The selected transport %r is not available",
                         self.ns.transport)
            return
        transport_cls = get_all_transports()[self.ns.transport]
        try:
            self._transport = transport_cls(
                self.ns.transport_where, self.ns.transport_options)
        except ValueError as exc:
            raise SystemExit(str(exc))

    def create_manager(self, storage):
        """
        Create or resume a session that handles most of the stuff needed to run
        jobs.

        This sets the attr:`_manager` which enables :meth:`manager`,
        :meth:`state` and :meth:`storage` properties.

        The created session state has the on_job_added signal connected to
        :meth:`on_job_added()`.

        :raises SessionResumeError:
            If the session cannot be resumed for any reason.
        """
        all_units = list(
            itertools.chain(*[p.unit_list for p in self.provider_list]))
        try:
            if storage is not None:
                self._manager = SessionManager.load_session(all_units, storage)
            else:
                self._manager = SessionManager.create_with_unit_list(all_units)
        except DependencyDuplicateError as exc:
            # Handle possible DependencyDuplicateError that can happen if
            # someone is using plainbox for job development.
            print(self.C.RED(
                _("The job database you are currently using is broken")))
            print(self.C.RED(
                _("At least two jobs contend for the id {0}").format(
                    exc.job.id)))
            print(self.C.RED(
                _("First job defined in: {0}").format(exc.job.origin)))
            print(self.C.RED(
                _("Second job defined in: {0}").format(
                    exc.duplicate_job.origin)))
            raise SystemExit(exc)
        except SessionResumeError as exc:
            print(self.C.RED(exc))
            print(self.C.RED(_("This session cannot be resumed")))
            raise
        else:
            # Connect the on_job_added signal. We use it to mark the test loop
            # for re-execution and to update the list of desired jobs.
            self.state.on_job_added.connect(self.on_job_added)

    def create_runner(self):
        """
        Create a job runner.

        This sets the attr:`_runner` which enables :meth:`runner` property.

        Requires the manager to be created (we need the storage object)
        """
        self._runner = JobRunner(
            self.storage.location, self.provider_list,
            # TODO: tie this with well-known-dirs helper
            os.path.join(self.storage.location, 'io-logs'),
            command_io_delegate=self, dry_run=self.ns.dry_run)

    def store_application_metadata(self):
        """
        Store application meta-data (app_id, app_blob) and session title
        """
        self.metadata.title = self.expected_session_title
        self.metadata.app_id = self.expected_app_id
        self.metadata.app_blob = b''

    @property
    def expected_app_id(self):
        return 'plainbox'

    @property
    def expected_session_title(self):
        return " ".join([os.path.basename(sys.argv[0])] + sys.argv[1:])

    def find_test_plan(self):
        # This is using getattr because the code is shared with checkbox-ng
        # that doesn't support the same set of command line options.
        test_plan_id = getattr(self.ns, "test_plan", None)
        if test_plan_id is None:
            return
        for provider in self.provider_list:
            for unit in provider.id_map[test_plan_id]:
                if unit.Meta.name == 'test plan':
                    return unit

    def set_effective_categories(self):
        if self._test_plan is None:
            return
        ecm = self._test_plan.get_effective_category_map(self.state.job_list)
        for job_id, effective_category_id in ecm.items():
            job_state = self.state.job_state_map[job_id]
            job_state.effective_category_id = effective_category_id

    def do_initial_job_selection(self):
        """
        Compute the initial list of desired jobs
        """
        # Compute the desired job list, this can give us notification about
        # problems in the selected jobs. Currently we just display each problem
        desired_job_list = self._get_matching_job_list(
            self.ns, self.state.job_list)
        print(self.C.header(_("Analyzing Jobs")))
        self._update_desired_job_list(desired_job_list)
        # Search each provider for the desired test plan
        if self.ns.test_plan is not None:
            # TODO: add high-level unit lookup functions
            for provider in self.provider_list:
                for unit in provider.id_map.get(self.ns.test_plan, ()):
                    if unit.Meta.name == 'test plan':
                        self.manager.test_plans = (unit,)
                        break

    def maybe_warm_up_authentication(self):
        """
        Ask the password before anything else in order to run jobs requiring
        privileges
        """
        warm_up_list = self.runner.get_warm_up_sequence(self.state.run_list)
        if warm_up_list:
            print(self.C.header(_("Authentication")))
            for warm_up_func in warm_up_list:
                warm_up_func()

    def run_all_selected_jobs(self):
        """
        Run all jobs according to the run list.
        """
        print(self.C.header(_("Running Selected Jobs")))
        self._backtrack_and_run_missing = True
        while self._backtrack_and_run_missing:
            self._backtrack_and_run_missing = False
            jobs_to_run = []
            estimated_time = 0
            # gather jobs that we want to run and skip the jobs that already
            # have result, this is only needed when we run over the list of
            # jobs again, after discovering new jobs via the local job output
            for job in self.state.run_list:
                job_state = self.state.job_state_map[job.id]
                if job_state.result.outcome is None:
                    jobs_to_run.append(job)
                    if (job.estimated_duration is not None
                            and estimated_time is not None):
                        estimated_time += job.estimated_duration
                    else:
                        estimated_time = None
            for job_no, job in enumerate(jobs_to_run, start=1):
                print(self.C.header(
                    _('Running job {} / {}. Estimated time left: {}').format(
                        job_no, len(jobs_to_run),
                        seconds_to_human_duration(max(0, estimated_time))
                        if estimated_time is not None else _("unknown")),
                    fill='-'))
                self.run_single_job(job)
                if (job.estimated_duration is not None
                        and estimated_time is not None):
                    estimated_time -= job.estimated_duration

    def run_single_job(self, job):
        self.run_single_job_with_ui(job, self.get_ui_for_job(job))

    def get_ui_for_job(self, job):
        if self.ns.dont_suppress_output is False and job.plugin in (
                'local', 'resource', 'attachment'):
            return NormalUI(self.C.c, show_cmd_output=False)
        else:
            return NormalUI(self.C.c, show_cmd_output=True)

    def run_single_job_with_ui(self, job, ui):
        job_start_time = time.time()
        job_state = self.state.job_state_map[job.id]
        ui.considering_job(job, job_state)
        if job_state.can_start():
            ui.about_to_start_running(job, job_state)
            self.metadata.running_job_name = job.id
            self.manager.checkpoint()
            ui.started_running(job, job_state)
            result_builder = self._run_single_job_with_ui_loop(
                job, job_state, ui)
            assert result_builder is not None
            result_builder.execution_duration = time.time() - job_start_time
            job_result = result_builder.get_result()
            self.metadata.running_job_name = None
            self.manager.checkpoint()
            ui.finished_running(job, job_state, job_result)
        else:
            result_builder = JobResultBuilder(
                outcome=IJobResult.OUTCOME_NOT_SUPPORTED,
                comments=job_state.get_readiness_description(),
                execution_duration=time.time() - job_start_time)
            job_result = result_builder.get_result()
            ui.job_cannot_start(job, job_state, job_result)
        self.state.update_job_result(job, job_result)
        ui.finished(job, job_state, job_result)

    def _run_single_job_with_ui_loop(self, job, job_state, ui):
        comments = ""
        while True:
            if job.plugin in ('user-interact', 'user-interact-verify',
                              'user-verify', 'manual'):
                ui.notify_about_purpose(job)
                if (self.is_interactive and
                        job.plugin in ('user-interact',
                                       'user-interact-verify',
                                       'manual')):
                    ui.notify_about_steps(job)
                    if job.plugin == 'manual':
                        cmd = 'run'
                    else :
                        cmd = ui.wait_for_interaction_prompt(job)
                    if cmd == 'run' or cmd is None:
                        result_builder = self.runner.run_job(
                            job, job_state, self.config, ui
                        ).get_builder()
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
                    result_builder = self.runner.run_job(
                        job, job_state, self.config, ui
                    ).get_builder()
            else:
                if 'noreturn' in job.get_flag_set():
                    ui.noreturn_job()
                result_builder = self.runner.run_job(
                    job, job_state, self.config, ui
                ).get_builder()
            if (self.is_interactive and
                    result_builder.outcome == IJobResult.OUTCOME_UNDECIDED):
                try:
                    if comments != "":
                        result_builder.comments = comments
                    ui.notify_about_verification(job)
                    self._interaction_callback(
                        self.runner, job, result_builder, self.config)
                except ReRunJob:
                    continue
            break
        return result_builder

    def export_and_send_results(self):
        # Get a stream with exported session data.
        exported_stream = io.BytesIO()
        self.exporter.dump_from_session_manager(self.manager, exported_stream)
        exported_stream.seek(0)  # Need to rewind the file, puagh
        # Write the stream to file if requested
        self._save_results(self.ns.output_file, exported_stream)
        # Invoke the transport?
        if self.transport is not None:
            exported_stream.seek(0)
            try:
                self._transport.send(
                    exported_stream.read(), self.config, self.state)
            except TransportError as exc:
                print(str(exc))

    def _save_results(self, output_file, input_stream):
        if output_file is sys.stdout:
            print(self.C.header(_("Results")))
            # This requires a bit more finesse, as exporters output bytes
            # and stdout needs a string.
            translating_stream = ByteStringStreamTranslator(
                output_file, "utf-8")
            copyfileobj(input_stream, translating_stream)
        else:
            print(_("Saving results to {}").format(output_file.name))
            copyfileobj(input_stream, output_file)
        if output_file is not sys.stdout:
            output_file.close()

    def _pick_action_cmd(self, action_list, prompt=None):
        return ActionUI(action_list, prompt, self._color).run()

    def _interaction_callback(self, runner, job, result_builder, config,
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

    def _update_desired_job_list(self, desired_job_list):
        problem_list = self.state.update_desired_job_list(desired_job_list)
        if problem_list:
            print(self.C.header(_("Warning"), 'YELLOW'))
            print(_("There were some problems with the selected jobs"))
            for problem in problem_list:
                print(" * {}".format(problem))
            print(_("Problematic jobs will not be considered"))

    def print_estimated_duration(self):
        print(self.C.header(_("Session Statistics")))
        print(_("This session is about {0:.2f}{percent} complete").format(
            self.get_completion_ratio() * 100, percent='%'))
        (estimated_duration_auto,
         estimated_duration_manual) = self.state.get_estimated_duration()
        if estimated_duration_auto:
            print(_("Estimated duration is {:.2f} for automated jobs.").format(
                  estimated_duration_auto))
        else:
            print(_(
                "Estimated duration cannot be determined for automated jobs."))
        if estimated_duration_manual:
            print(_("Estimated duration is {:.2f} for manual jobs.").format(
                  estimated_duration_manual))
        else:
            print(_(
                "Estimated duration cannot be determined for manual jobs."))
        print(_("Size of the desired job list: {0}").format(
            len(self.state.desired_job_list)))
        print(_("Size of the effective execution plan: {0}").format(
            len(self.state.run_list)))

    def get_completion_ratio(self):
        total_cnt = len(self.state.run_list)
        total_time = 0
        done_cnt = 0
        done_time = 0
        time_reliable = True
        for job in self.state.run_list:
            inc = job.estimated_duration
            if inc is None:
                time_reliable = False
                continue
            total_time += inc
            if self.state.job_state_map[job.id].result.outcome is not None:
                done_cnt += 1
                done_time += inc
        if time_reliable:
            if total_time == 0:
                return 0
            else:
                return done_time / total_time
        else:
            if total_cnt == 0:
                return 0
            else:
                return done_cnt / total_cnt

    def on_job_added(self, job):
        """
        Handler connected to SessionState.on_job_added()

        The goal of this handler is to re-select all desired jobs (based on
        original command line arguments and new list of known jobs) and set the
        backtrack_and_run_missing flag that is observed by
        _run_all_selected_jobs()
        """
        new_matching_job_list = self._get_matching_job_list(
            self.ns, self.state.job_list)
        self._update_desired_job_list(new_matching_job_list)
        if self._test_plan is not None:
            job_state = self.state.job_state_map[job.id]
            job_state.effective_category_id = (
                self._test_plan.get_effective_category(job))
        self._backtrack_and_run_missing = True


def seconds_to_human_duration(seconds: float) -> str:
    """ Convert ammount of seconds to human readable duration string. """
    delta = datetime.timedelta(seconds=round(seconds))
    return str(delta)
