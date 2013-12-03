# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`checkbox_ng.commands.cli` -- Command line sub-command
===========================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from logging import getLogger
from os.path import join
from shutil import copyfileobj
import curses
import io
import os
import sys
import textwrap

from plainbox.abc import IJobResult
from plainbox.impl.applogic import get_matching_job_list, get_whitelist_by_name
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.check_config import CheckConfigInvocation
from plainbox.impl.commands.checkbox import CheckBoxCommandMixIn
from plainbox.impl.commands.checkbox import CheckBoxInvocationMixIn
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.exporter import ByteStringStreamTranslator
from plainbox.impl.exporter import get_all_exporters
from plainbox.impl.exporter.html import HTMLSessionStateExporter
from plainbox.impl.exporter.xml import XMLSessionStateExporter
from plainbox.impl.result import DiskJobResult, MemoryJobResult
from plainbox.impl.runner import JobRunner
from plainbox.impl.runner import authenticate_warmup
from plainbox.impl.runner import slugify
from plainbox.impl.secure.config import Unset
from plainbox.impl.secure.qualifiers import WhiteList
from plainbox.impl.session import SessionStateLegacyAPI as SessionState


logger = getLogger("checkbox.ng.commands.cli")


def show_menu(stdscr, title, menu):
    """
    Display the appropriate curses menu and return the selected options
    """

    curses.use_default_colors()
    curses.curs_set(0)
    stdscr.keypad(1)
    # Modify color pair #1, to get black on white text
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)

    option_count = len(menu)
    position = 0  # Zero-based index of the selected menu option
    old_position = None
    key_pressed = None
    selection = [position]
    new_selection = False

    while True:
        if position != old_position or new_selection:
            stdscr.erase()
            old_position = position
            new_selection = False
            stdscr.border(0)
            # Display title at x=2, y=2
            stdscr.addstr(2, 2, title, curses.A_STANDOUT)

            # Display all the menu items
            for i in range(option_count):
                text_style = curses.A_NORMAL
                if position == i:
                    text_style = curses.color_pair(1)
                # Display options from line 4, column 4
                stdscr.addstr(4 + i, 4, "[{}] - {}".format(
                    'X' if i in selection else ' ',
                    menu[i].replace('ihv-', '').capitalize()), text_style)

            # Display "OK" at bottom of menu
            text_style = curses.A_NORMAL
            if position == option_count:
                text_style = curses.color_pair(1)
            # Add an empty line before the last option
            stdscr.addstr(5 + option_count, 4, "OK", text_style)
            stdscr.refresh()

        key_pressed = stdscr.getch()
        if key_pressed == curses.KEY_DOWN:
            if position < option_count:
                position += 1
            else:
                position = 0
        elif key_pressed == curses.KEY_UP:
            if position > 0:
                position -= 1
            else:
                position = option_count
        elif position == option_count:
            break
        elif key_pressed == 32:  # KEY_SPACE
            if position in selection:
                selection.remove(position)
            elif position < option_count:
                selection.append(position)
            new_selection = True

    return selection


def show_welcome(stdscr, text):
    """
    Display a curses splash screen containing a welcome text

    Left and right margins are set to 3 chars. Including the border width (1),
    the text is wrapped to screen width - 3 * 2 - 1 *2 using:
        * stdscr.getmaxyx()[1] - 8
        * stdscr.addstr(i, 4, line)
    8 equals to margins(3*2) + borders(2*1)
    4 equals to left margin(3) + left border(1)
    """
    curses.use_default_colors()
    curses.curs_set(0)
    stdscr.border(0)

    i = 0
    for paragraph in text.splitlines():
        i += 1
        for line in textwrap.fill(paragraph,
                                  stdscr.getmaxyx()[1] - 8,
                                  replace_whitespace=False).splitlines():
            stdscr.addstr(i, 4, line)
            i += 1
    stdscr.addstr(i + 1, 4, "Continue", curses.A_STANDOUT)
    while True:
        key_pressed = stdscr.getch()
        if key_pressed == ord('\n'):
            break


class CliInvocation(CheckBoxInvocationMixIn):

    def __init__(self, provider_list, config, settings, ns):
        super().__init__(provider_list)
        self.provider_list = provider_list
        self.config = config
        self.settings = settings
        self.ns = ns
        self.whitelists = []
        if self.ns.whitelist:
            for whitelist in self.ns.whitelist:
                self.whitelists.append(WhiteList.from_file(whitelist.name))
        elif self.config.whitelist is not Unset:
            self.whitelists.append(WhiteList.from_file(self.config.whitelist))
        elif self.ns.include_pattern_list:
            self.whitelists.append(WhiteList(self.ns.include_pattern_list))
        else:
            self.whitelists.append(
                get_whitelist_by_name(
                    provider_list, self.settings['default_whitelist']))

        if self.config.welcome_text is not Unset:
            print()
            for line in self.config.welcome_text.splitlines():
                print(textwrap.fill(line, 80, replace_whitespace=False))
            print()
        print("[ Analyzing Jobs ]".center(80, '='))
        self.session = None
        self.runner = None

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
        job_list = self.get_job_list(ns)
        return self._run_jobs(ns, job_list)

    def ask_for_resume(self):
        return self.ask_user(
            "Do you want to resume the previous session?", ('y', 'n')
        ).lower() == "y"

    def ask_for_resume_action(self):
        return self.ask_user(
            "What do you want to do with that job?", ('skip', 'fail', 'run'))

    def ask_user(self, prompt, allowed):
        answer = None
        while answer not in allowed:
            answer = input("{} [{}] ".format(prompt, ", ".join(allowed)))
        return answer

    def _maybe_skip_last_job_after_resume(self, session):
        last_job = session.metadata.running_job_name
        if last_job is None:
            return
        print("We have previously tried to execute {}".format(last_job))
        action = self.ask_for_resume_action()
        if action == 'skip':
            result = MemoryJobResult({
                'outcome': 'skip',
                'comment': "Skipped after resuming execution"
            })
        elif action == 'fail':
            result = MemoryJobResult({
                'outcome': 'fail',
                'comment': "Failed after resuming execution"
            })
        elif action == 'run':
            result = None
        if result:
            session.update_job_result(
                session.job_state_map[last_job].job, result)
            session.metadata.running_job_name = None
            session.persistent_save()

    def _run_jobs(self, ns, job_list):
        # Create a session that handles most of the stuff needed to run jobs
        try:
            session = SessionState(job_list)
        except DependencyDuplicateError as exc:
            # Handle possible DependencyDuplicateError that can happen if
            # someone is using plainbox for job development.
            print("The job database you are currently using is broken")
            print("At least two jobs contend for the name {0}".format(
                exc.job.name))
            print("First job defined in: {0}".format(exc.job.origin))
            print("Second job defined in: {0}".format(
                exc.duplicate_job.origin))
            raise SystemExit(exc)
        with session.open():
            desired_job_list = []
            for whitelist in self.whitelists:
                desired_job_list.extend(get_matching_job_list(job_list,
                                                              whitelist))
            self._update_desired_job_list(session, desired_job_list)
            if session.previous_session_file():
                if self.is_interactive and self.ask_for_resume():
                    session.resume()
                    self._maybe_skip_last_job_after_resume(session)
                else:
                    session.clean()
            session.metadata.title = " ".join(sys.argv)
            session.persistent_save()
            # Ask the password before anything else in order to run jobs
            # requiring privileges
            if self.is_interactive and self._auth_warmup_needed(session):
                print("[ Authentication ]".center(80, '='))
                return_code = authenticate_warmup()
                if return_code:
                    raise SystemExit(return_code)
            runner = JobRunner(
                session.session_dir, self.provider_list,
                session.jobs_io_log_dir)
            self._run_jobs_with_session(ns, session, runner)
            self.save_results(session)

        # FIXME: sensible return value
        return 0

    def _auth_warmup_needed(self, session):
        # Don't warm up plainbox-trusted-launcher-1 if none of the providers
        # use it. We assume that the mere presence of a provider makes it
        # possible for a root job to be preset but it could be improved to
        # acutally know when this step is absolutely not required (no local
        # jobs, no jobs
        # need root)
        if all(not provider.secure for provider in self.provider_list):
            return False
        # Don't use authentication warm-up if none of the jobs on the run list
        # requires it.
        if all(job.user is None for job in session.run_list):
            return False
        # Otherwise, do pre-authentication
        return True

    def save_results(self, session):
        if self.is_interactive:
            print("[ Results ]".center(80, '='))
            exporter = get_all_exporters()['text']()
            exported_stream = io.BytesIO()
            data_subset = exporter.get_session_data_subset(session)
            exporter.dump(data_subset, exported_stream)
            exported_stream.seek(0)  # Need to rewind the file, puagh
            # This requires a bit more finesse, as exporters output bytes
            # and stdout needs a string.
            translating_stream = ByteStringStreamTranslator(
                sys.stdout, "utf-8")
            copyfileobj(exported_stream, translating_stream)
        base_dir = os.path.join(
            os.getenv(
                'XDG_DATA_HOME', os.path.expanduser("~/.local/share/")),
            "plainbox")
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        results_file = os.path.join(base_dir, 'results.html')
        submission_file = os.path.join(base_dir, 'submission.xml')
        exporter_list = [XMLSessionStateExporter, HTMLSessionStateExporter]
        if 'xlsx' in get_all_exporters():
            from plainbox.impl.exporter.xlsx import XLSXSessionStateExporter
            exporter_list.append(XLSXSessionStateExporter)
        for exporter_cls in exporter_list:
            # Options are only relevant to the XLSX exporter
            exporter = exporter_cls(
                ['with-sys-info', 'with-summary', 'with-job-description',
                 'with-text-attachments'])
            data_subset = exporter.get_session_data_subset(session)
            results_path = results_file
            if exporter_cls is XMLSessionStateExporter:
                results_path = submission_file
            if 'xlsx' in get_all_exporters():
                if exporter_cls is XLSXSessionStateExporter:
                    results_path = results_path.replace('html', 'xlsx')
            with open(results_path, "wb") as stream:
                exporter.dump(data_subset, stream)
        print("\nSaving submission file to {}".format(submission_file))
        self.submission_file = submission_file
        print("View results (HTML): file://{}".format(results_file))
        if 'xlsx' in get_all_exporters():
            print("View results (XLSX): file://{}".format(
                results_file.replace('html', 'xlsx')))

    def _interaction_callback(self, runner, job, config, prompt=None,
                              allowed_outcome=None):
        result = {}
        if prompt is None:
            prompt = "Select an outcome or an action: "
        if allowed_outcome is None:
            allowed_outcome = [IJobResult.OUTCOME_PASS,
                               IJobResult.OUTCOME_FAIL,
                               IJobResult.OUTCOME_SKIP]
        allowed_actions = ['comments']
        if job.command:
            allowed_actions.append('test')
        result['outcome'] = IJobResult.OUTCOME_UNDECIDED
        while result['outcome'] not in allowed_outcome:
            print("Allowed answers are: {}".format(", ".join(allowed_outcome +
                                                             allowed_actions)))
            choice = input(prompt)
            if choice in allowed_outcome:
                result['outcome'] = choice
                break
            elif choice == 'test':
                (result['return_code'],
                 result['io_log_filename']) = runner._run_command(job, config)
            elif choice == 'comments':
                result['comments'] = input('Please enter your comments:\n')
        return DiskJobResult(result)

    def _update_desired_job_list(self, session, desired_job_list):
        problem_list = session.update_desired_job_list(desired_job_list)
        if problem_list:
            print("[ Warning ]".center(80, '*'))
            print("There were some problems with the selected jobs")
            for problem in problem_list:
                print(" * {}".format(problem))
            print("Problematic jobs will not be considered")
        (estimated_duration_auto,
         estimated_duration_manual) = session.get_estimated_duration()
        if estimated_duration_auto:
            print("Estimated duration is {:.2f} for automated jobs.".format(
                  estimated_duration_auto))
        else:
            print(
                "Estimated duration cannot be determined for automated jobs.")
        if estimated_duration_manual:
            print("Estimated duration is {:.2f} for manual jobs.".format(
                  estimated_duration_manual))
        else:
            print("Estimated duration cannot be determined for manual jobs.")

    def _run_jobs_with_session(self, ns, session, runner):
        # TODO: run all resource jobs concurrently with multiprocessing
        # TODO: make local job discovery nicer, it would be best if
        # desired_jobs could be managed entirely internally by SesionState. In
        # such case the list of jobs to run would be changed during iteration
        # but would be otherwise okay).
        print("[ Running All Jobs ]".center(80, '='))
        again = True
        while again:
            again = False
            for job in session.run_list:
                # Skip jobs that already have result, this is only needed when
                # we run over the list of jobs again, after discovering new
                # jobs via the local job output
                if session.job_state_map[job.name].result.outcome is not None:
                    continue
                self._run_single_job_with_session(ns, session, runner, job)
                session.persistent_save()
                if job.plugin == "local":
                    # After each local job runs rebuild the list of matching
                    # jobs and run everything again
                    desired_job_list = []
                    for whitelist in self.whitelists:
                        desired_job_list.extend(
                            get_matching_job_list(session.job_list, whitelist))
                    self._update_desired_job_list(session, desired_job_list)
                    again = True
                    break

    def _run_single_job_with_session(self, ns, session, runner, job):
        print("[ {} ]".format(job.name).center(80, '-'))
        if job.description is not None:
            print(job.description)
            print("^" * len(job.description.splitlines()[-1]))
            print()
        job_state = session.job_state_map[job.name]
        logger.debug("Job name: %s", job.name)
        logger.debug("Plugin: %s", job.plugin)
        logger.debug("Direct dependencies: %s", job.get_direct_dependencies())
        logger.debug("Resource dependencies: %s",
                     job.get_resource_dependencies())
        logger.debug("Resource program: %r", job.requires)
        logger.debug("Command: %r", job.command)
        logger.debug("Can start: %s", job_state.can_start())
        logger.debug("Readiness: %s", job_state.get_readiness_description())
        if job_state.can_start():
            print("Running... (output in {}.*)".format(
                join(session.jobs_io_log_dir, slugify(job.name))))
            session.metadata.running_job_name = job.name
            session.persistent_save()
            # TODO: get a confirmation from the user for certain types of
            # job.plugin
            job_result = runner.run_job(job)
            if (job_result.outcome == IJobResult.OUTCOME_UNDECIDED
                    and self.is_interactive):
                job_result = self._interaction_callback(
                    runner, job, self.config)
            session.metadata.running_job_name = None
            session.persistent_save()
            print("Outcome: {}".format(job_result.outcome))
            print("Comments: {}".format(job_result.comments))
        else:
            job_result = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_NOT_SUPPORTED,
                'comments': job_state.get_readiness_description()
            })
        if job_result is not None:
            session.update_job_result(job, job_result)


class CliCommand(PlainBoxCommand, CheckBoxCommandMixIn):
    """
    Command for running tests using the command line UI.
    """

    def __init__(self, provider_list, config, settings):
        self.provider_list = provider_list
        self.config = config
        self.settings = settings

    def invoked(self, ns):
        # Run check-config, if requested
        if ns.check_config:
            retval = CheckConfigInvocation(self.config).run()
            return retval
        return CliInvocation(self.provider_list, self.config,
                             self.settings, ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(self.settings['subparser_name'],
                                       help=self.settings['subparser_help'])
        parser.set_defaults(command=self)
        parser.add_argument(
            "--check-config",
            action="store_true",
            help="Run check-config")
        parser.add_argument(
            '--not-interactive', action='store_true',
            help="Skip tests that require interactivity")
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)
