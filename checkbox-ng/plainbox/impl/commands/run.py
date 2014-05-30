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
:mod:`plainbox.impl.commands.run` -- run sub-command
====================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from argparse import FileType, SUPPRESS
from logging import getLogger
from shutil import copyfileobj
import collections
import io
import itertools
import os
import sys

from plainbox.abc import IJobResult
from plainbox.abc import IJobRunnerUI
from plainbox.i18n import gettext as _
from plainbox.i18n import ngettext
from plainbox.impl.color import ansi_on, ansi_off
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.checkbox import CheckBoxCommandMixIn
from plainbox.impl.commands.checkbox import CheckBoxInvocationMixIn
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.exporter import ByteStringStreamTranslator
from plainbox.impl.exporter import get_all_exporters
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.runner import JobRunner
from plainbox.impl.session import SessionManager
from plainbox.impl.session import SessionMetaData
from plainbox.impl.session import SessionPeekHelper
from plainbox.impl.session import SessionResumeError
from plainbox.impl.session import SessionStorageRepository
from plainbox.impl.transport import TransportError
from plainbox.impl.transport import get_all_transports


logger = getLogger("plainbox.commands.run")


class Colorizer:
    """
    Colorizing helper for various kinds of content we need to handle
    """

    # NOTE: Ideally result and all would be handled by multi-dispatch __call__

    def __init__(self, color):
        self.c = color

    def result(self, result):
        outcome_color = {
            IJobResult.OUTCOME_PASS: "GREEN",
            IJobResult.OUTCOME_FAIL: "RED",
            IJobResult.OUTCOME_SKIP: "YELLOW",
            IJobResult.OUTCOME_UNDECIDED: "MAGENTA",
            IJobResult.OUTCOME_NOT_SUPPORTED: "YELLOW",
        }.get(result.outcome, "RESET")
        return self(result.tr_outcome(), outcome_color)

    def header(self, text, color_name='WHITE', bright=True, fill='='):
        return self("[ {} ]".format(text).center(80, fill), color_name, bright)

    def f(self, color_name):
        return getattr(self.c.f, color_name.upper())

    def b(self, color_name):
        return getattr(self.c.b, color_name.upper())

    def s(self, style_name):
        return getattr(self.c.s, style_name.upper())

    def __call__(self, text, color_name="WHITE", bright=True):
        return ''.join([
            self.f(color_name),
            self.c.s.BRIGHT if bright else '', str(text),
            self.c.s.RESET_ALL])

    def BLACK(self, text, bright=True):
        return self(text, "BLACK", bright)

    def RED(self, text, bright=True):
        return self(text, "RED", bright)

    def GREEN(self, text, bright=True):
        return self(text, "GREEN", bright)

    def YELLOW(self, text, bright=True):
        return self(text, "YELLOW", bright)

    def BLUE(self, text, bright=True):
        return self(text, "BLUE", bright)

    def MAGENTA(self, text, bright=True):
        return self(text, "MAGENTA", bright)

    def CYAN(self, text, bright=True):
        return self(text, "CYAN", bright)

    def WHITE(self, text, bright=True):
        return self(text, "WHITE", bright)


Action = collections.namedtuple("Action", "accel label cmd")


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

    def job_cannot_start(self, job, job_state, job_result):
        pass

    def finished(self, job, job_state, job_result):
        pass


class NormalUI(IJobRunnerUI):

    STREAM_MAP = {
        'stdout': sys.stdout,
        'stderr': sys.stderr
    }

    def __init__(self, color, show_cmd_output=True):
        self.show_cmd_output = show_cmd_output
        self.C = Colorizer(color)

    def considering_job(self, job, job_state):
        print(self.C.header(job.id))

    def about_to_start_running(self, job, job_state):
        pass

    def wait_for_interaction_prompt(self, job):
        input(self.C.BLUE(_("Press enter to continue") + '\n'))

    def started_running(self, job, job_state):
        pass

    def about_to_execute_program(self, args, kwargs):
        if self.show_cmd_output:
            print(self.C.BLACK("... 8< -".ljust(80, '-')))
        else:
            print("(" + _("Command output hidden") + ")")

    def got_program_output(self, stream_name, line):
        if not self.show_cmd_output:
            return
        stream = self.STREAM_MAP[stream_name]
        stream = {
            'stdout': sys.stdout,
            'stderr': sys.stderr
        }[stream_name]
        print(self.C.BLACK(line.decode("UTF-8", "ignore").rstrip('\n')),
              file=stream)

    def finished_executing_program(self, returncode):
        if self.show_cmd_output:
            print(self.C.BLACK("- >8 ---".rjust(80, '-')))

    def finished_running(self, job, state, result):
        pass

    def notify_about_description(self, job):
        print(_("Please familiarize yourself with the job description"))
        print(self.C.CYAN(job.tr_description()))

    def job_cannot_start(self, job, job_state, result):
        print(_("Job cannot be started because:"))
        for inhibitor in job_state.readiness_inhibitor_list:
            print(" - {}".format(self.C.YELLOW(inhibitor)))

    def finished(self, job, job_state, result):
        self._print_result_outcome(result)

    def _print_result_outcome(self, result):
        print(_("Outcome") + ": " + self.C.result(result))


class ReRunJob(Exception):
    """
    Exception raised from _interaction_callback to indicate that a job should
    be re-started.
    """


class RunInvocation(CheckBoxInvocationMixIn):
    """
    Invocation of the 'plainbox run' command.

    :ivar ns:
        The argparse namespace obtained from RunCommand
    :ivar _manager:
        The SessionManager object
    :ivar _runner:
        The JobRunner object
    :ivar _exporter:
        A ISessionStateExporter of some kind
    :ivar _transport:
        A ISessionStateTransport of some kind (optional)
    :ivar _backtrack_and_run_missing:
        A flag indicating that we should run over all the jobs in the
        self.state.run_list again, set every time a job is added. Reset every
        time the loop-over-all-jobs is started.
    """

    def __init__(self, provider_list, config, ns, use_colors=True):
        super().__init__(provider_list, config)
        self.C = Colorizer(ansi_on if use_colors else ansi_off)
        self.ns = ns
        self._manager = None
        self._runner = None
        self._exporter = None
        self._transport = None
        self._backtrack_and_run_missing = True

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
                self.ns.not_interactive)

    def run(self):
        ns = self.ns
        if ns.output_format == _('?'):
            self._print_output_format_list(ns)
            return 0
        elif ns.output_options == _('?'):
            self._print_output_option_list(ns)
            return 0
        elif ns.transport == _('?'):
            self._print_transport_list(ns)
            return 0
        else:
            return self.do_normal_sequence()

    def do_normal_sequence(self):
        """
        Proceed through normal set of steps that are required to runs jobs
        """
        # Create exporter and transport early so that we can handle bugs
        # before starting the session.
        self.create_exporter()
        self.create_transport()
        if self.is_interactive:
            resumed = self.maybe_resume_session()
        else:
            self.create_manager(None)
            resumed = False
        # Create the job runner so that we can do stuff
        self.create_runner()
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
            elif cmd == 'next' or cmd is None:
                continue
            elif cmd == 'create':
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
                self.maybe_skip_last_job_after_resume()
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
        print(_("Available output formats: {}").format(
            ', '.join(get_all_exporters())))

    def _print_output_option_list(self, ns):
        print(_("Each format may support a different set of options"))
        for name, exporter_cls in get_all_exporters().items():
            print("{}: {}".format(
                name, ", ".join(exporter_cls.supported_option_list)))

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
            metadata = SessionPeekHelper().peek(data)
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

    def maybe_skip_last_job_after_resume(self):
        last_job = self.metadata.running_job_name
        if last_job is None:
            return
        print(_("Previous session run tried to execute job: {}").format(
            last_job))
        cmd = self._pick_action_cmd([
            Action('s', _("skip that job"), 'skip'),
            Action('f', _("mark it as failed and continue"), 'fail'),
            Action('r', _("run it again"), 'run'),
        ], _("What do you want to do with that job?"))
        if cmd == 'skip' or cmd is None:
            result = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_SKIP,
                'comments': _("Skipped after resuming execution")
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

        This sets the :ivar:`_exporter`.
        """
        exporter_cls = get_all_exporters()[self.ns.output_format]
        if self.ns.output_options:
            option_list = self.ns.output_options.split(',')
        else:
            option_list = None
        try:
            self._exporter = exporter_cls(option_list)
        except ValueError as exc:
            raise SystemExit(str(exc))

    def create_transport(self):
        """
        Create the ISessionStateTransport based on the command line options

        This sets the :ivar:`_transport`.
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

        This sets the :ivar:`_manager` which enables :meth:`manager`,
        :meth:`state` and :meth:`storage` properties.

        The created session state has the on_job_added signal connected to
        :meth:`on_job_added()`.

        :raises SessionResumeError:
            If the session cannot be resumed for any reason.
        """
        all_units = list(
            itertools.chain(*[
                p.get_units()[0] for p in self.provider_list]))
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

        This sets the :ivar:`_runner` which enables :meth:`runner` property.

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
        print(self.C.header(_("Running All Jobs")))
        self._backtrack_and_run_missing = True
        while self._backtrack_and_run_missing:
            self._backtrack_and_run_missing = False
            for job in self.state.run_list:
                job_state = self.state.job_state_map[job.id]
                # Skip jobs that already have result, this is only needed when
                # we run over the list of jobs again, after discovering new
                # jobs via the local job output
                if job_state.result.outcome is None:
                    self.run_single_job(job)

    def run_single_job(self, job):
        self.run_single_job_with_ui(job, self.get_ui_for_job(job))

    def get_ui_for_job(self, job):
        if job.plugin in ('local', 'resource', 'attachment'):
            return NormalUI(self.C.c, show_cmd_output=False)
        else:
            return NormalUI(self.C.c, show_cmd_output=True)

    def run_single_job_with_ui(self, job, ui):
        job_state = self.state.job_state_map[job.id]
        ui.considering_job(job, job_state)
        if job_state.can_start():
            ui.about_to_start_running(job, job_state)
            self.metadata.running_job_name = job.id
            self.manager.checkpoint()
            ui.started_running(job, job_state)
            job_result = self._run_single_job_with_ui_loop(job, ui)
            self.metadata.running_job_name = None
            self.manager.checkpoint()
            ui.finished_running(job, job_state, job_result)
        else:
            job_result = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_NOT_SUPPORTED,
                'comments': job_state.get_readiness_description()
            })
            ui.job_cannot_start(job, job_state, job_result)
        if job_result is not None:
            self.state.update_job_result(job, job_result)
        ui.finished(job, job_state, job_result)

    def _run_single_job_with_ui_loop(self, job, ui):
        while True:
            if job.plugin in ('user-interact', 'user-interact-verify',
                              'user-verify', 'manual'):
                ui.notify_about_description(job)
            if (self.is_interactive and
                    job.plugin in ('user-interact', 'user-interact-verify')):
                ui.wait_for_interaction_prompt(job)
            job_result = self.runner.run_job(job, self.config, ui)
            if (self.is_interactive and
                    job_result.outcome == IJobResult.OUTCOME_UNDECIDED):
                try:
                    job_result = self._interaction_callback(
                        self.runner, job, job_result, self.config)
                except ReRunJob:
                    continue
            return job_result

    def export_and_send_results(self):
        # Get a stream with exported session data.
        exported_stream = io.BytesIO()
        data_subset = self.exporter.get_session_data_subset(self.state)
        self.exporter.dump(data_subset, exported_stream)
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
        if prompt is None:
            prompt = _("Pick an action")
        long_hint = "\n".join(
            "  {accel} => {label}".format(
                accel=self.C.BLUE(action.accel) if action.accel else ' ',
                label=action.label)
            for action in action_list)
        short_hint = ''.join(action.accel for action in action_list)
        while True:
            try:
                print(self.C.BLUE(prompt))
                print(long_hint)
                choice = input("[{}]: ".format(self.C.BLUE(short_hint)))
            except EOFError:
                return None
            else:
                for action in action_list:
                    if choice == action.accel or choice == action.label:
                        return action.cmd

    def _interaction_callback(self, runner, job, result, config,
                              prompt=None, allowed_outcome=None):
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
                Action('p', _('mark as passed'), 'set-pass'))
        if IJobResult.OUTCOME_FAIL in allowed_outcome:
            allowed_actions.append(
                Action('f', _('mark as failed'), 'set-fail'))
        if IJobResult.OUTCOME_SKIP in allowed_outcome:
            allowed_actions.append(
                Action('s', _('skip this test'), 'set-skip'))
        if job.command is not None:
            allowed_actions.append(
                Action('r', _('re-run this job'), 're-run'))
        if result.return_code is not None:
            allowed_actions.append(
                Action('', _('auto-select outcome'), 'set-auto'))
        while result.outcome not in allowed_outcome:
            print(_("Please decide what to do next:"))
            print("  " + _("result") + ": {0}".format(self.C.result(result)))
            if result.comments is None:
                print("  " + _("comments") + ": {0}".format(_("none")))
            else:
                print("  " + _("comments") + ": {0}".format(
                    self.C.CYAN(result.comments, bright=False)))
            cmd = self._pick_action_cmd(allowed_actions)
            if cmd == 'set-pass':
                result.outcome = IJobResult.OUTCOME_PASS
            elif cmd == 'set-fail':
                result.outcome = IJobResult.OUTCOME_FAIL
            elif cmd == 'set-skip' or cmd is None:
                result.outcome = IJobResult.OUTCOME_SKIP
            elif cmd == 'set-auto':
                result.outcome = (
                    IJobResult.OUTCOME_PASS if result.return_code == 0
                    else IJobResult.OUTCOME_FAIL)
            elif cmd == 'set-comments':
                if result.comments is None:
                    result.comments = ""
                new_comment = input(self.C.BLUE(
                    _('Please enter your comments:') + '\n'))
                if new_comment:
                    result.comments += new_comment + '\n'
            elif cmd == 're-run':
                raise ReRunJob
        return result

    def _update_desired_job_list(self, desired_job_list):
        problem_list = self.state.update_desired_job_list(desired_job_list)
        if problem_list:
            print(self.C.header_("Warning", 'YELLOW'))
            print(_("There were some problems with the selected jobs"))
            for problem in problem_list:
                print(" * {}".format(problem))
            print(_("Problematic jobs will not be considered"))

    def print_estimated_duration(self):
        print(self.C.header(_("Session Statistics")))
        print(_("This session is about {0:.2f}% complete").format(
            self.get_completion_ratio() * 100))
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
        self._backtrack_and_run_missing = True


class RunCommand(PlainBoxCommand, CheckBoxCommandMixIn):

    def __init__(self, provider_list, config):
        self.provider_list = provider_list
        self.config = config

    def invoked(self, ns):
        return RunInvocation(self.provider_list, self.config, ns,
                             ns.use_colors).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser("run", help=_("run a test job"))
        parser.set_defaults(command=self)
        group = parser.add_argument_group(title=_("user interface options"))
        parser.set_defaults(use_colors=True)
        group.add_argument(
            '--no-color', dest='use_colors', action='store_false',
            help=SUPPRESS)
        group.add_argument(
            '--not-interactive', action='store_true',
            help=_("skip tests that require interactivity"))
        group.add_argument(
            '-n', '--dry-run', action='store_true',
            help=_("don't really run most jobs"))
        group = parser.add_argument_group(_("output options"))
        assert 'text' in get_all_exporters()
        group.add_argument(
            '-f', '--output-format', default='text',
            metavar=_('FORMAT'), choices=[_('?')] + list(
                get_all_exporters().keys()),
            help=_('save test results in the specified FORMAT'
                   ' (pass ? for a list of choices)'))
        group.add_argument(
            '-p', '--output-options', default='',
            metavar=_('OPTIONS'),
            help=_('comma-separated list of options for the export mechanism'
                   ' (pass ? for a list of choices)'))
        group.add_argument(
            '-o', '--output-file', default='-',
            metavar=_('FILE'), type=FileType("wb"),
            help=_('save test results to the specified FILE'
                   ' (or to stdout if FILE is -)'))
        group.add_argument(
            '-t', '--transport',
            metavar=_('TRANSPORT'), choices=[_('?')] + list(
                get_all_transports().keys()),
            help=_('use TRANSPORT to send results somewhere'
                   ' (pass ? for a list of choices)'))
        group.add_argument(
            '--transport-where',
            metavar=_('WHERE'),
            help=_('where to send data using the selected transport'))
        group.add_argument(
            '--transport-options',
            metavar=_('OPTIONS'),
            help=_('comma-separated list of key-value options (k=v) to '
                   'be passed to the transport'))
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)
