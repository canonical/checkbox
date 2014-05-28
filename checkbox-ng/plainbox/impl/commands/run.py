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

from argparse import FileType
from logging import getLogger
from os.path import join
from shutil import copyfileobj
import io
import itertools
import os
import sys

from plainbox.abc import IJobResult
from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.checkbox import CheckBoxCommandMixIn
from plainbox.impl.commands.checkbox import CheckBoxInvocationMixIn
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.exporter import ByteStringStreamTranslator
from plainbox.impl.exporter import get_all_exporters
from plainbox.impl.result import DiskJobResult, MemoryJobResult
from plainbox.impl.runner import JobRunner
from plainbox.impl.runner import slugify
from plainbox.impl.session import SessionManager
from plainbox.impl.session import SessionMetaData
from plainbox.impl.session import SessionPeekHelper
from plainbox.impl.session import SessionResumeError
from plainbox.impl.session import SessionStorageRepository
from plainbox.impl.transport import TransportError
from plainbox.impl.transport import get_all_transports


logger = getLogger("plainbox.commands.run")


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

    def __init__(self, provider_list, config, ns):
        super().__init__(provider_list, config)
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
        # Try to use the first session that can be resumed if the user agrees
        resume_storage_list = self.get_resume_candidates()
        resume_storage = None
        for resume_storage in resume_storage_list:
            # Skip sessions that the user doesn't want to resume
            if not self.ask_for_resume(resume_storage):
                continue
            # Skip sessions that cannot be resumed
            try:
                self.create_manager(resume_storage)
            except SessionResumeError:
                continue
            # If we resumed maybe not rerun the same, probably broken job
            if resume_storage is not None:
                self.maybe_skip_last_job_after_resume()
            # Finally ignore other sessions that can be resumed
            break
        else:
            if resume_storage is not None and not self.ask_for_new_session():
                raise SystemExit(_("Session not resumed"))
            # Create a fresh session if nothing got resumed
            self.create_manager(None)
        # Store the application-identifying meta-data and checkpoint the
        # session.
        self.store_application_metadata()
        self.metadata.flags.add(SessionMetaData.FLAG_INCOMPLETE)
        self.manager.checkpoint()
        # Create the job runner so that we can do stuff
        self.create_runner()
        # Select all the jobs that we are likely to run. This is the initial
        # selection as we haven't started any jobs yet. Local jobs will cause
        # that to happen again.
        self.do_initial_job_selection()
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
        # TODO: use proper APIs for yes-no questions
        try:
            return self.ask_user(message, ('y', 'n')).lower() == "y"
        except EOFError:
            return False

    def ask_for_resume(self, storage):
        return self.ask_for_confirmation(
            _("Do you want to resume session: {0}").format(storage.id))

    def ask_for_new_session(self):
        return self.ask_for_confirmation(
            _("Do you want to start a new session"))

    def ask_for_resume_action(self):
        try:
            return self.ask_user(
                _("What do you want to do with that job?"),
                (_('skip'), _('fail'), _('run')))
        except EOFError:
            return _('skip')

    def maybe_skip_last_job_after_resume(self):
        last_job = self.metadata.running_job_name
        if last_job is None:
            return
        print(_("Previous session run tried to execute: {}").format(last_job))
        action = self.ask_for_resume_action()
        if action == _('skip'):
            result = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_SKIP,
                'comment': _("Skipped after resuming execution")
            })
        elif action == _('fail'):
            result = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_FAIL,
                'comment': _("Failed after resuming execution")
            })
        elif action == _('run'):
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
            print(_("The job database you are currently using is broken"))
            print(_("At least two jobs contend for the id {0}").format(
                exc.job.id))
            print(_("First job defined in: {0}").format(exc.job.origin))
            print(_("Second job defined in: {0}").format(
                exc.duplicate_job.origin))
            raise SystemExit(exc)
        except SessionResumeError as exc:
            print(exc)
            print(_("This session cannot be resumed"))
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
        print(_("[ Analyzing Jobs ]").center(80, '='))
        # TODO resume?
        self._update_desired_job_list(desired_job_list)
        self._print_estimated_duration()

    def maybe_warm_up_authentication(self):
        """
        Ask the password before anything else in order to run jobs requiring
        privileges
        """
        warm_up_list = self.runner.get_warm_up_sequence(self.state.run_list)
        if warm_up_list:
            print(_("[ Authentication ]").center(80, '='))
            for warm_up_func in warm_up_list:
                warm_up_func()

    def run_all_selected_jobs(self):
        """
        Run all jobs according to the run list.
        """
        print(_("[ Running All Jobs ]").center(80, '='))
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
        print("[ {} ]".format(job.tr_summary()).center(80, '-'))
        description = job.tr_description()
        if description is not None:
            print(description)
            print()
        job_state = self.state.job_state_map[job.id]
        logger.debug(_("Job id: %s"), job.id)
        logger.debug(_("Plugin: %s"), job.plugin)
        logger.debug(_("Direct dependencies: %s"),
                     job.get_direct_dependencies())
        logger.debug(_("Resource dependencies: %s"),
                     job.get_resource_dependencies())
        logger.debug(_("Resource program: %r"), job.requires)
        logger.debug(_("Command: %r"), job.command)
        logger.debug(_("Can start: %s"), job_state.can_start())
        logger.debug(_("Readiness: %s"), job_state.get_readiness_description())
        if job_state.can_start():
            print(_("Running... (output in {}.*)").format(
                join(self.runner._jobs_io_log_dir, slugify(job.id))))
            self.metadata.running_job_name = job.id
            self.manager.checkpoint()
            # TODO: get a confirmation from the user for certain types of
            # job.plugin
            job_result = self.runner.run_job(job, self.config)
            if (job_result.outcome == IJobResult.OUTCOME_UNDECIDED
                    and self.is_interactive):
                job_result = self._interaction_callback(
                    self.runner, job, self.config)
            self.metadata.running_job_name = None
            self.manager.checkpoint()
            print(_("Outcome: {}").format(job_result.outcome))
            print(_("Comments: {}").format(job_result.comments))
        else:
            job_result = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_NOT_SUPPORTED,
                'comments': job_state.get_readiness_description()
            })
        if job_result is not None:
            self.state.update_job_result(job, job_result)

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

    def ask_user(self, prompt, allowed):
        answer = None
        while answer not in allowed:
            answer = input("{} [{}] ".format(prompt, ", ".join(allowed)))
        return answer

    def _save_results(self, output_file, input_stream):
        if output_file is sys.stdout:
            print(_("[ Results ]").center(80, '='))
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

    def _interaction_callback(self, runner, job, config, prompt=None,
                              allowed_outcome=None):
        result = {}
        if prompt is None:
            prompt = _("Select an outcome or an action: ")
        if allowed_outcome is None:
            allowed_outcome = [IJobResult.OUTCOME_PASS,
                               IJobResult.OUTCOME_FAIL,
                               IJobResult.OUTCOME_SKIP]
        allowed_actions = {
            _('comments'): 'set-comments',
        }
        if IJobResult.OUTCOME_PASS in allowed_outcome:
            allowed_actions[_("pass")] = "set-pass"
        if IJobResult.OUTCOME_FAIL in allowed_outcome:
            allowed_actions[_("fail")] = "set-fail"
        if IJobResult.OUTCOME_SKIP in allowed_outcome:
            allowed_actions[_("skip")] = "set-skip"
        if job.command:
            allowed_actions[_("test")] = "run-test"
        result['outcome'] = IJobResult.OUTCOME_UNDECIDED
        while result['outcome'] not in allowed_outcome:
            print(_("Allowed answers are: {}").format(
                ", ".join(allowed_actions.keys())))
            try:
                choice = input(prompt)
            except EOFError:
                result['outcome'] = IJobResult.OUTCOME_SKIP
                break
            else:
                action = allowed_actions.get(choice)
            if action is None:
                continue
            elif action == 'set-pass':
                result['outcome'] = IJobResult.OUTCOME_PASS
            elif action == 'set-fail':
                result['outcome'] = IJobResult.OUTCOME_FAIL
            elif action == 'set-skip':
                result['outcome'] = IJobResult.OUTCOME_SKIP
            elif action == 'run-test':
                (result['return_code'], result['io_log_filename']) = (
                    runner._run_command(job, config))
            elif action == 'set-comments':
                result['comments'] = input(_('Please enter your comments:\n'))
        return DiskJobResult(result)

    def _update_desired_job_list(self, desired_job_list):
        problem_list = self.state.update_desired_job_list(desired_job_list)
        if problem_list:
            print(_("[ Warning ]").center(80, '*'))
            print(_("There were some problems with the selected jobs"))
            for problem in problem_list:
                print(" * {}".format(problem))
            print(_("Problematic jobs will not be considered"))

    def _print_estimated_duration(self):
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
        return RunInvocation(self.provider_list, self.config, ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser("run", help=_("run a test job"))
        parser.set_defaults(command=self)
        group = parser.add_argument_group(title=_("user interface options"))
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
