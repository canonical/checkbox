# This file is part of Checkbox.
#
# Copyright 2013-2014 Canonical Ltd.
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

from gettext import gettext as _
from logging import getLogger
from os.path import join
from shutil import copyfileobj
import io
import os
import sys

from plainbox.abc import IJobResult
from plainbox.impl.applogic import get_whitelist_by_name
from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.commands.check_config import CheckConfigInvocation
from plainbox.impl.commands.checkbox import CheckBoxCommandMixIn
from plainbox.impl.commands.checkbox import CheckBoxInvocationMixIn
from plainbox.impl.depmgr import DependencyDuplicateError
from plainbox.impl.exporter import ByteStringStreamTranslator
from plainbox.impl.exporter import get_all_exporters
from plainbox.impl.exporter.html import HTMLSessionStateExporter
from plainbox.impl.exporter.xml import XMLSessionStateExporter
from plainbox.impl.job import JobTreeNode
from plainbox.impl.result import DiskJobResult, MemoryJobResult
from plainbox.impl.runner import JobRunner
from plainbox.impl.runner import authenticate_warmup
from plainbox.impl.runner import slugify
from plainbox.impl.secure.config import Unset
from plainbox.impl.secure.qualifiers import CompositeQualifier
from plainbox.impl.secure.qualifiers import NonLocalJobQualifier
from plainbox.impl.secure.qualifiers import WhiteList
from plainbox.impl.secure.qualifiers import select_jobs
from plainbox.impl.session import SessionManager, SessionStorageRepository
from plainbox.vendor.textland import get_display

from checkbox_ng.ui import ScrollableTreeNode
from checkbox_ng.ui import ShowMenu
from checkbox_ng.ui import ShowWelcome


logger = getLogger("checkbox.ng.commands.cli")


class SelectableJobTreeNode(JobTreeNode):
    """
    Implementation of a node in a tree that can be selected/deselected
    """
    def __init__(self, job=None):
        super().__init__(job)
        self.selected = True
        self.job_selection = {}
        self.expanded = True
        self.current_index = 0
        self._resource_jobs = []

    def get_node_by_index(self, index, tree=None):
        """
        Return the node found at the position given by index considering the
        tree from a top-down list view.
        """
        if tree is None:
            tree = self
        if self.expanded:
            for category in self.categories:
                if index == tree.current_index:
                    tree.current_index = 0
                    return (category, None)
                else:
                    tree.current_index += 1
                result = category.get_node_by_index(index, tree)
                if result != (None, None):
                    return result
            for job in self.jobs:
                if index == tree.current_index:
                    tree.current_index = 0
                    return (job, self)
                else:
                    tree.current_index += 1
        return (None, None)

    def render(self, cols=80):
        """
        Return the tree as a simple list of categories and jobs suitable for
        display. Jobs are properly indented to respect the tree hierarchy
        and selection marks are added automatically at the beginning of each
        element.

        The node titles should not exceed the width of a the terminal and
        thus are cut to fit inside.
        """
        self._flat_list = []
        if self.expanded:
            for category in self.categories:
                prefix = '[ ]'
                if category.selected:
                    prefix = '[X]'
                line = ''
                title = category.name
                if category.jobs or category.categories:
                    if category.expanded:
                        line = prefix + self.depth * '   ' + ' - ' + title
                    else:
                        line = prefix + self.depth * '   ' + ' + ' + title
                else:
                    line = prefix + self.depth * '   ' + '   ' + title
                if len(line) > cols:
                    col_max = cols - 4  # includes len('...') + a space
                    line = line[:col_max] + '...'
                self._flat_list.append(line)
                self._flat_list.extend(category.render(cols))
            for job in self.jobs:
                prefix = '[ ]'
                if self.job_selection[job]:
                    prefix = '[X]'
                title = job.partial_id
                line = prefix + self.depth * '   ' + '   ' + title
                if len(line) > cols:
                    col_max = cols - 4  # includes len('...') + a space
                    line = line[:col_max] + '...'
                self._flat_list.append(line)
        return self._flat_list

    def add_job(self, job):
        if job.plugin == 'resource':
            # I don't want the user to see resources but I need to keep
            # track of them to put them in the final selection. I also
            # don't want to add them to the tree.
            self._resource_jobs.append(job)
            return
        super().add_job(job)
        self.job_selection[job] = True

    @property
    def selection(self):
        """
        Return all the jobs currently selected
        """
        self._selection_list = []
        for category in self.categories:
            self._selection_list.extend(category.selection)
        for job in self.job_selection:
            if self.job_selection[job]:
                self._selection_list.append(job)
        # Don't forget to append the collected resource jobs to the final
        # selection
        self._selection_list.extend(self._resource_jobs)
        return self._selection_list

    def set_ancestors_state(self, new_state):
        """
        Set the selection state of all ancestors consistently
        """
        # If child is set, then all ancestors must be set
        if new_state:
            parent = self.parent
            while parent:
                parent.selected = new_state
                parent = parent.parent
        # If child is not set, then all ancestors mustn't be set
        # unless another child of the ancestor is set
        else:
            parent = self.parent
            while parent:
                if any((category.selected
                        for category in parent.categories)):
                    break
                if any((parent.job_selection[job]
                        for job in parent.job_selection)):
                    break
                parent.selected = new_state
                parent = parent.parent

    def update_selected_state(self):
        """
        Update the category state according to its job selection
        """
        if any((self.job_selection[job] for job in self.job_selection)):
            self.selected = True
        else:
            self.selected = False

    def set_descendants_state(self, new_state):
        """
        Set the selection state of all descendants recursively
        """
        self.selected = new_state
        for job in self.job_selection:
            self.job_selection[job] = new_state
        for category in self.categories:
            category.set_descendants_state(new_state)


class CliInvocation(CheckBoxInvocationMixIn):

    def __init__(self, provider_list, config, settings, ns, display=None):
        super().__init__(provider_list, config)
        self.settings = settings
        self.display = display
        self.ns = ns
        self.whitelists = []
        self._local_only = False  # Only run local jobs
        if self.ns.whitelist:
            for whitelist in self.ns.whitelist:
                self.whitelists.append(WhiteList.from_file(whitelist.name))
        elif self.config.whitelist is not Unset:
            self.whitelists.append(WhiteList.from_file(self.config.whitelist))
        elif self.ns.include_pattern_list:
            self.whitelists.append(WhiteList(self.ns.include_pattern_list))

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
        previous_session_file = SessionStorageRepository().get_last_storage()
        resume_in_progress = False
        if previous_session_file:
            if self.is_interactive:
                if self.ask_for_resume():
                    resume_in_progress = True
                    manager = SessionManager.load_session(
                        job_list, previous_session_file)
                    self._maybe_skip_last_job_after_resume(manager)
            else:
                resume_in_progress = True
                manager = SessionManager.load_session(
                    job_list, previous_session_file)
        if not resume_in_progress:
            # Create a session that handles most of the stuff needed to run
            # jobs
            try:
                manager = SessionManager.create_with_job_list(
                    job_list, legacy_mode=True)
            except DependencyDuplicateError as exc:
                # Handle possible DependencyDuplicateError that can happen if
                # someone is using plainbox for job development.
                print(_("The job database you are currently using is broken"))
                print(_("At least two jobs contend for the name {0}").format(
                    exc.job.id))
                print(_("First job defined in: {0}").format(exc.job.origin))
                print(_("Second job defined in: {0}").format(
                    exc.duplicate_job.origin))
                raise SystemExit(exc)
            manager.state.metadata.title = " ".join(sys.argv)
            if self.is_interactive:
                if self.display is None:
                    self.display = get_display()
                # FIXME: i18n problem, welcome text must be translatable but
                # comes from external source. It should be made a part of the
                # program.
                if self.settings['welcome_text']:
                    self.display.run(
                        ShowWelcome(self.settings['welcome_text']))
                if not self.whitelists:
                    whitelists = []
                    for p in self.provider_list:
                        if p.name in self.settings['default_providers']:
                            whitelists.extend(
                                [w.name for w in p.get_builtin_whitelists()])
                    selection = self.display.run(ShowMenu("Suite selection",
                                                          whitelists))
                    if not selection:
                        raise SystemExit(
                            _('No whitelists selected, aborting...'))
                    for s in selection:
                        self.whitelists.append(
                            get_whitelist_by_name(self.provider_list,
                                                  whitelists[s]))
            else:
                self.whitelists.append(
                    get_whitelist_by_name(
                        self.provider_list,
                        self.settings['default_whitelist']))
        manager.checkpoint()

        if self.is_interactive and not resume_in_progress:
            # Pre-run all local jobs
            desired_job_list = select_jobs(
                manager.state.job_list,
                [CompositeQualifier(
                    self.whitelists +
                    [NonLocalJobQualifier(inclusive=False)]
                )])
            self._update_desired_job_list(manager, desired_job_list)
            # Ask the password before anything else in order to run local jobs
            # requiring privileges
            if self._auth_warmup_needed(manager):
                print("[ {} ]".format(_("Authentication")).center(80, '='))
                return_code = authenticate_warmup()
                if return_code:
                    raise SystemExit(return_code)
            self._local_only = True
            self._run_jobs(ns, manager)
            self._local_only = False

        if not resume_in_progress:
            # Run the rest of the desired jobs
            desired_job_list = select_jobs(manager.state.job_list,
                                           self.whitelists)
            self._update_desired_job_list(manager, desired_job_list)
            if self.is_interactive:
                # Ask the password before anything else in order to run jobs
                # requiring privileges
                if self._auth_warmup_needed(manager):
                    print("[ {} ]".format(_("Authentication")).center(80, '='))
                    return_code = authenticate_warmup()
                    if return_code:
                        raise SystemExit(return_code)
                tree = SelectableJobTreeNode.create_tree(
                    manager.state.run_list,
                    legacy_mode=True)
                title = _('Choose tests to run on your system:')
                if self.display is None:
                    self.display = get_display()
                self.display.run(ScrollableTreeNode(tree, title))
                self._update_desired_job_list(manager, tree.selection)
                estimated_duration_auto, estimated_duration_manual = \
                    manager.state.get_estimated_duration()
                if estimated_duration_auto:
                    print(_("Estimated duration is {:.2f} for automated"
                            " jobs.").format(estimated_duration_auto))
                else:
                    print(_("Estimated duration cannot be determined for"
                            " automated jobs."))
                if estimated_duration_manual:
                    print(_("Estimated duration is {:.2f} for manual"
                            " jobs.").format(estimated_duration_manual))
                else:
                    print(_("Estimated duration cannot be determined for"
                            " manual jobs."))
        self._run_jobs(ns, manager)
        manager.destroy()

        # FIXME: sensible return value
        return 0

    def ask_for_resume(self):
        return self.ask_user(
            _("Do you want to resume the previous session?"), (_('y'), _('n'))
        ).lower() == "y"

    def ask_for_resume_action(self):
        return self.ask_user(
            _("What do you want to do with that job?"),
            (_('skip'), _('fail'), _('run')))

    def ask_user(self, prompt, allowed):
        answer = None
        while answer not in allowed:
            answer = input("{} [{}] ".format(prompt, ", ".join(allowed)))
        return answer

    def _maybe_skip_last_job_after_resume(self, manager):
        last_job = manager.state.metadata.running_job_name
        if last_job is None:
            return
        print(_("We have previously tried to execute {}").format(last_job))
        action = self.ask_for_resume_action()
        if action == _('skip'):
            result = MemoryJobResult({
                'outcome': 'skip',
                'comment': _("Skipped after resuming execution")
            })
        elif action == _('fail'):
            result = MemoryJobResult({
                'outcome': 'fail',
                'comment': _("Failed after resuming execution")
            })
        elif action == 'run':
            result = None
        if result:
            manager.state.update_job_result(
                manager.state.job_state_map[last_job].job, result)
            manager.state.metadata.running_job_name = None
            manager.checkpoint()

    def _run_jobs(self, ns, manager):
        runner = JobRunner(
            manager.storage.location, self.provider_list,
            os.path.join(manager.storage.location, 'io-logs'),
            command_io_delegate=self)
        self._run_jobs_with_session(ns, manager, runner)
        if not self._local_only:
            self.save_results(manager)

    def _auth_warmup_needed(self, manager):
        # Don't warm up plainbox-trusted-launcher-1 if none of the providers
        # use it. We assume that the mere presence of a provider makes it
        # possible for a root job to be preset but it could be improved to
        # actually know when this step is absolutely not required (no local
        # jobs, no jobs
        # need root)
        if all(not provider.secure for provider in self.provider_list):
            return False
        # Don't use authentication warm-up if none of the jobs on the run list
        # requires it.
        if all(job.user is None for job in manager.state.run_list):
            return False
        # Otherwise, do pre-authentication
        return True

    def save_results(self, manager):
        if self.is_interactive:
            print("[ {} ]".format(_('Results')).center(80, '='))
            exporter = get_all_exporters()['text']()
            exported_stream = io.BytesIO()
            data_subset = exporter.get_session_data_subset(manager.state)
            exporter.dump(data_subset, exported_stream)
            exported_stream.seek(0)  # Need to rewind the file, puagh
            # This requires a bit more finesse, as exporters output bytes
            # and stdout needs a string.
            translating_stream = ByteStringStreamTranslator(
                sys.stdout, "utf-8")
            copyfileobj(exported_stream, translating_stream)
        # FIXME: this should probably not go to plainbox but checkbox-ng
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
        # We'd like these options for our reports.
        exp_options = ['with-sys-info', 'with-summary', 'with-job-description',
                       'with-text-attachments']
        for exporter_cls in exporter_list:
            # Exporters may support different sets of options, ensure we don't
            # pass an unsupported one (which would cause a crash)
            actual_options = [opt for opt in exp_options
                              if opt in exporter_cls.supported_option_list]
            exporter = exporter_cls(actual_options)
            data_subset = exporter.get_session_data_subset(manager.state)
            results_path = results_file
            if exporter_cls is XMLSessionStateExporter:
                results_path = submission_file
            # FIXME: replacing extension is ugly
            if 'xlsx' in get_all_exporters():
                if exporter_cls is XLSXSessionStateExporter:
                    results_path = results_path.replace('html', 'xlsx')
            with open(results_path, "wb") as stream:
                exporter.dump(data_subset, stream)
        print()
        print(_("Saving submission file to {}").format(submission_file))
        self.submission_file = submission_file
        print(_("View results") + " (HTML): file://{}".format(results_file))
        if 'xlsx' in get_all_exporters():
            # FIXME: replacing extension is ugly
            print(_("View results") + " (XLSX): file://{}".format(
                results_file.replace('html', 'xlsx')))

    def _interaction_callback(self, runner, job, config, prompt=None,
                              allowed_outcome=None):
        result = {}
        if prompt is None:
            prompt = _("Select an outcome or an action: ")
        if allowed_outcome is None:
            allowed_outcome = [IJobResult.OUTCOME_PASS,
                               IJobResult.OUTCOME_FAIL,
                               IJobResult.OUTCOME_SKIP]
        allowed_actions = [_('comments')]
        if job.command:
            allowed_actions.append(_('test'))
        result['outcome'] = IJobResult.OUTCOME_UNDECIDED
        while result['outcome'] not in allowed_outcome:
            print(_("Allowed answers are: {}").format(
                ", ".join(allowed_outcome + allowed_actions)))
            choice = input(prompt)
            if choice in allowed_outcome:
                result['outcome'] = choice
                break
            elif choice == _('test'):
                (result['return_code'],
                 result['io_log_filename']) = runner._run_command(job, config)
            elif choice == _('comments'):
                result['comments'] = input(_('Please enter your comments:\n'))
        return DiskJobResult(result)

    def _update_desired_job_list(self, manager, desired_job_list):
        problem_list = manager.state.update_desired_job_list(desired_job_list)
        if problem_list:
            print("[ {} ]".format(_('Warning')).center(80, '*'))
            print(_("There were some problems with the selected jobs"))
            for problem in problem_list:
                print(" * {}".format(problem))
            print(_("Problematic jobs will not be considered"))

    def _run_jobs_with_session(self, ns, manager, runner):
        # TODO: run all resource jobs concurrently with multiprocessing
        # TODO: make local job discovery nicer, it would be best if
        # desired_jobs could be managed entirely internally by SesionState. In
        # such case the list of jobs to run would be changed during iteration
        # but would be otherwise okay).
        if self._local_only:
            print("[ {} ]".format(
                _('Loading Jobs Definition')
            ).center(80, '='))
        else:
            print("[ {} ]".format(
                _('Running All Jobs')
            ).center(80, '='))
        again = True
        while again:
            again = False
            for job in manager.state.run_list:
                # Skip jobs that already have result, this is only needed when
                # we run over the list of jobs again, after discovering new
                # jobs via the local job output
                if (manager.state.job_state_map[job.id].result.outcome
                        is not None):
                    continue
                self._run_single_job_with_session(ns, manager, runner, job)
                manager.checkpoint()
                if job.plugin == "local":
                    # After each local job runs rebuild the list of matching
                    # jobs and run everything again
                    desired_job_list = select_jobs(manager.state.job_list,
                                                   self.whitelists)
                    if self._local_only:
                        desired_job_list = [
                            job for job in desired_job_list
                            if job.plugin == 'local']
                    self._update_desired_job_list(manager, desired_job_list)
                    again = True
                    break

    def _run_single_job_with_session(self, ns, manager, runner, job):
        if job.plugin not in ['local', 'resource']:
            print("[ {} ]".format(job.tr_summary()).center(80, '-'))
        job_state = manager.state.job_state_map[job.id]
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
            if job.plugin not in ['local', 'resource']:
                if job.description is not None:
                    print(job.description)
                    print("^" * len(job.description.splitlines()[-1]))
                    print()
                print(_("Running... (output in {}.*)").format(
                    join(manager.storage.location, slugify(job.id))))
            manager.state.metadata.running_job_name = job.id
            manager.checkpoint()
            # TODO: get a confirmation from the user for certain types of
            # job.plugin
            job_result = runner.run_job(job, self.config)
            if (job_result.outcome == IJobResult.OUTCOME_UNDECIDED
                    and self.is_interactive):
                job_result = self._interaction_callback(
                    runner, job, self.config)
            manager.state.metadata.running_job_name = None
            manager.checkpoint()
            if job.plugin not in ['local', 'resource']:
                print(_("Outcome: {}").format(job_result.outcome))
                if job_result.comments is not None:
                    print(_("Comments: {}").format(job_result.comments))
        else:
            job_result = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_NOT_SUPPORTED,
                'comments': job_state.get_readiness_description()
            })
            if job.plugin not in ['local', 'resource']:
                print(_("Outcome: {}").format(job_result.outcome))
        if job_result is not None:
            manager.state.update_job_result(job, job_result)


class CliCommand(PlainBoxCommand, CheckBoxCommandMixIn):
    """
    Command for running tests using the command line UI.
    """
    gettext_domain = "checkbox-ng"

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
            help=_("run check-config"))
        parser.add_argument(
            '--not-interactive', action='store_true',
            help=_("skip tests that require interactivity"))
        # Call enhance_parser from CheckBoxCommandMixIn
        self.enhance_parser(parser)
