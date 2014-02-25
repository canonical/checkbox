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
import io
import os
import sys
import textwrap

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
from plainbox.impl.secure.qualifiers import WhiteList
from plainbox.impl.secure.qualifiers import select_jobs
from plainbox.impl.session import SessionManager, SessionStorageRepository
from plainbox.vendor.textland import DrawingContext
from plainbox.vendor.textland import EVENT_KEYBOARD
from plainbox.vendor.textland import EVENT_RESIZE
from plainbox.vendor.textland import Event
from plainbox.vendor.textland import IApplication
from plainbox.vendor.textland import KeyboardData
from plainbox.vendor.textland import Size
from plainbox.vendor.textland import TextImage
from plainbox.vendor.textland import get_display
from plainbox.vendor.textland import NORMAL, REVERSE, UNDERLINE


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
                title = job.name
                line = prefix + self.depth * '   ' + '   ' + title
                if len(line) > cols:
                    col_max = cols - 4  # includes len('...') + a space
                    line = line[:col_max] + '...'
                self._flat_list.append(line)
        return self._flat_list

    def add_job(self, job):
        if job.plugin == 'resource':
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


class ShowWelcome(IApplication):
    """
    Display a welcome message
    """
    def __init__(self, text):
        self.image = TextImage(Size(0, 0))
        self.text = text

    def consume_event(self, event: Event):
        if event.kind == EVENT_RESIZE:
            self.image = TextImage(event.data)  # data is the new size
        elif event.kind == EVENT_KEYBOARD and event.data.key == "enter":
            raise StopIteration
        self.repaint(event)
        return self.image

    def repaint(self, event: Event):
        ctx = DrawingContext(self.image)
        i = 0
        ctx.border()
        for paragraph in self.text.splitlines():
            i += 1
            for line in textwrap.fill(
                    paragraph,
                    self.image.size.width - 8,
                    replace_whitespace=False).splitlines():
                ctx.move_to(4, i)
                ctx.print(line)
                i += 1
        ctx.move_to(4, i + 1)
        ctx.attributes.style = REVERSE
        ctx.print("< Continue >")


class ShowMenu(IApplication):
    """
    Display the appropriate menu and return the selected options
    """
    def __init__(self, title, menu):
        self.image = TextImage(Size(0, 0))
        self.title = title
        self.menu = menu
        self.option_count = len(menu)
        self.position = 0  # Zero-based index of the selected menu option
        self.selection = [self.position]

    def consume_event(self, event: Event):
        if event.kind == EVENT_RESIZE:
            self.image = TextImage(event.data)  # data is the new size
        elif event.kind == EVENT_KEYBOARD:
            if event.data.key == "down":
                if self.position < self.option_count:
                    self.position += 1
                else:
                    self.position = 0
            elif event.data.key == "up":
                if self.position > 0:
                    self.position -= 1
                else:
                    self.position = self.option_count
            elif (event.data.key == "enter" and
                  self.position == self.option_count):
                raise StopIteration(self.selection)
            elif event.data.key == "space":
                if self.position in self.selection:
                    self.selection.remove(self.position)
                elif self.position < self.option_count:
                    self.selection.append(self.position)
        self.repaint(event)
        return self.image

    def repaint(self, event: Event):
        ctx = DrawingContext(self.image)
        ctx.border(tm=1)
        ctx.attributes.style = REVERSE
        ctx.print(' ' * self.image.size.width)
        ctx.move_to(1, 0)
        ctx.print(self.title)

        # Display all the menu items
        for i in range(self.option_count):
            ctx.attributes.style = NORMAL
            if i == self.position:
                ctx.attributes.style = REVERSE
            # Display options from line 3, column 4
            ctx.move_to(4, 3 + i)
            ctx.print("[{}] - {}".format(
                'X' if i in self.selection else ' ',
                self.menu[i].replace('ihv-', '').capitalize()))

        # Display "OK" at bottom of menu
        ctx.attributes.style = NORMAL
        if self.position == self.option_count:
            ctx.attributes.style = REVERSE
        # Add an empty line before the last option
        ctx.move_to(4, 4 + self.option_count)
        ctx.print("< OK >")


class ScrollableTreeNode(IApplication):
    """
    Class used to interact with a SelectableJobTreeNode
    """
    def __init__(self, tree, title):
        self.image = TextImage(Size(0, 0))
        self.tree = tree
        self.title = title
        self.top = 0  # Top line number
        self.highlight = 0  # Highlighted line number

    def consume_event(self, event: Event):
        if event.kind == EVENT_RESIZE:
            self.image = TextImage(event.data)  # data is the new size
        elif event.kind == EVENT_KEYBOARD:
            self.image = TextImage(self.image.size)
            if event.data.key == "up":
                self._scroll("up")
            elif event.data.key == "down":
                self._scroll("down")
            elif event.data.key == "space":
                self._selectNode()
            elif event.data.key == "enter":
                self._toggleNode()
            elif event.data.key in 'sS':
                self.tree.set_descendants_state(True)
            elif event.data.key in 'dD':
                self.tree.set_descendants_state(False)
            elif event.data.key in 'tT':
                raise StopIteration
        self.repaint(event)
        return self.image

    def repaint(self, event: Event):
        ctx = DrawingContext(self.image)
        ctx.border(tm=1, bm=1)
        cols = self.image.size.width
        extra_cols = 0
        if cols > 80:
            extra_cols = cols - 80
        ctx.attributes.style = REVERSE
        ctx.print(' ' * cols)
        ctx.move_to(1, 0)
        bottom = self.top + self.image.size.height - 4
        ctx.print(self.title)
        ctx.move_to(1, self.image.size.height - 1)
        ctx.attributes.style = UNDERLINE
        ctx.print("Enter")
        ctx.move_to(6, self.image.size.height - 1)
        ctx.attributes.style = NORMAL
        ctx.print(": Expand/Collapse")
        ctx.move_to(27, self.image.size.height - 1)
        ctx.attributes.style = UNDERLINE
        ctx.print("S")
        ctx.move_to(28, self.image.size.height - 1)
        ctx.attributes.style = NORMAL
        ctx.print("elect All")
        ctx.move_to(41, self.image.size.height - 1)
        ctx.attributes.style = UNDERLINE
        ctx.print("D")
        ctx.move_to(42, self.image.size.height - 1)
        ctx.attributes.style = NORMAL
        ctx.print("eselect All")
        ctx.move_to(66 + extra_cols, self.image.size.height - 1)
        ctx.print("Start ")
        ctx.move_to(72 + extra_cols, self.image.size.height - 1)
        ctx.attributes.style = UNDERLINE
        ctx.print("T")
        ctx.move_to(73 + extra_cols, self.image.size.height - 1)
        ctx.attributes.style = NORMAL
        ctx.print("esting")
        for i, line in enumerate(self.tree.render(cols - 3)[self.top:bottom]):
            ctx.move_to(2, i + 2)
            if i != self.highlight:
                ctx.attributes.style = NORMAL
            else:  # highlight the current line
                ctx.attributes.style = REVERSE
            ctx.print(line)

    def _selectNode(self):
        """
        Mark a node/job as selected for this test run.
        See :meth:`SelectableJobTreeNode.set_ancestors_state()` and
        :meth:`SelectableJobTreeNode.set_descendants_state()` for details
        about the automatic selection of parents and descendants.
        """
        node, category = self.tree.get_node_by_index(self.top + self.highlight)
        if category:  # then the selected node is a job not a category
            job = node
            category.job_selection[job] = not(category.job_selection[job])
            category.update_selected_state()
            category.set_ancestors_state(category.job_selection[job])
        else:
            node.selected = not(node.selected)
            node.set_descendants_state(node.selected)
            node.set_ancestors_state(node.selected)

    def _toggleNode(self):
        """
        Expand/collapse a node
        """
        node, is_job = self.tree.get_node_by_index(self.top + self.highlight)
        if not is_job:
            node.expanded = not(node.expanded)

    def _scroll(self, direction):
        visible_length = len(self.tree.render())
        # Scroll the tree view
        if (direction == "up" and
                self.highlight == 0 and self.top != 0):
            self.top -= 1
            return
        elif (direction == "down" and
                (self.highlight + 1) == (self.image.size.height - 4) and
                (self.top + self.image.size.height - 4) != visible_length):
            self.top += 1
            return
        # Move the highlighted line
        if (direction == "up" and
                (self.top != 0 or self.highlight != 0)):
            self.highlight -= 1
        elif (direction == "down" and
                (self.top + self.highlight + 1) != visible_length and
                (self.highlight + 1) != (self.image.size.height - 4)):
            self.highlight += 1


class CliInvocation(CheckBoxInvocationMixIn):

    def __init__(self, provider_list, config, settings, ns, display=None):
        super().__init__(provider_list)
        self.provider_list = provider_list
        self.config = config
        self.settings = settings
        self.display = display
        self.ns = ns
        self.whitelists = []
        if self.ns.whitelist:
            for whitelist in self.ns.whitelist:
                self.whitelists.append(WhiteList.from_file(whitelist.name))
        elif self.config.whitelist is not Unset:
            self.whitelists.append(WhiteList.from_file(self.config.whitelist))
        elif self.ns.include_pattern_list:
            self.whitelists.append(WhiteList(self.ns.include_pattern_list))

        if self.is_interactive:
            if self.settings['welcome_text']:
                if self.display is None:
                    self.display = get_display()
                self.display.run(ShowWelcome(self.settings['welcome_text']))
            if not self.whitelists:
                whitelists = []
                for p in self.provider_list:
                    if p.name in self.settings['default_providers']:
                        whitelists.extend(
                            [w.name for w in p.get_builtin_whitelists()])
                selection = self.display.run(ShowMenu("Suite selection",
                                                      whitelists))
                if not selection:
                    raise SystemExit('No whitelists selected, aborting...')
                for s in selection:
                    self.whitelists.append(
                        get_whitelist_by_name(provider_list, whitelists[s]))
        else:
            self.whitelists.append(
                get_whitelist_by_name(
                    provider_list, self.settings['default_whitelist']))

        print("[ Analyzing Jobs ]".center(80, '='))
        self.manager = None
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

    def _maybe_skip_last_job_after_resume(self, manager):
        last_job = manager.state.metadata.running_job_name
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
            manager.state.update_job_result(
                manager.state.job_state_map[last_job].job, result)
            manager.state.metadata.running_job_name = None
            manager.checkpoint()

    def _run_jobs(self, ns, manager):
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
                manager = SessionManager.create_session(job_list,
                                                        legacy_mode=True)
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
            manager.state.metadata.title = " ".join(sys.argv)
            manager.checkpoint()
            desired_job_list = select_jobs(manager.state.job_list,
                                           self.whitelists)
            self._update_desired_job_list(manager, desired_job_list)
        # Ask the password before anything else in order to run jobs
        # requiring privileges
        if self.is_interactive and self._auth_warmup_needed(manager):
            print("[ Authentication ]".center(80, '='))
            return_code = authenticate_warmup()
            if return_code:
                raise SystemExit(return_code)
        runner = JobRunner(
            manager.storage.location, self.provider_list,
            os.path.join(manager.storage.location, 'io-logs'),
            command_io_delegate=self)
        self._run_jobs_with_session(ns, manager, runner)
        self.save_results(manager)
        manager.destroy()

        # FIXME: sensible return value
        return 0

    def _auth_warmup_needed(self, manager):
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
        if all(job.user is None for job in manager.state.run_list):
            return False
        # Otherwise, do pre-authentication
        return True

    def save_results(self, manager):
        if self.is_interactive:
            print("[ Results ]".center(80, '='))
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
            data_subset = exporter.get_session_data_subset(manager.state)
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

    def _update_desired_job_list(self, manager, desired_job_list):
        problem_list = manager.state.update_desired_job_list(desired_job_list)
        if problem_list:
            print("[ Warning ]".center(80, '*'))
            print("There were some problems with the selected jobs")
            for problem in problem_list:
                print(" * {}".format(problem))
            print("Problematic jobs will not be considered")
        (estimated_duration_auto,
         estimated_duration_manual) = manager.state.get_estimated_duration()
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

    def _run_jobs_with_session(self, ns, manager, runner):
        # TODO: run all resource jobs concurrently with multiprocessing
        # TODO: make local job discovery nicer, it would be best if
        # desired_jobs could be managed entirely internally by SesionState. In
        # such case the list of jobs to run would be changed during iteration
        # but would be otherwise okay).
        print("[ Running All Jobs ]".center(80, '='))
        again = True
        while again:
            again = False
            for job in manager.state.run_list:
                # Skip jobs that already have result, this is only needed when
                # we run over the list of jobs again, after discovering new
                # jobs via the local job output
                if (manager.state.job_state_map[job.name].result.outcome
                        is not None):
                    continue
                self._run_single_job_with_session(ns, manager, runner, job)
                manager.checkpoint()
                if job.plugin == "local":
                    # After each local job runs rebuild the list of matching
                    # jobs and run everything again
                    desired_job_list = select_jobs(manager.state.job_list,
                                                   self.whitelists)
                    self._update_desired_job_list(manager, desired_job_list)
                    again = True
                    break

    def _run_single_job_with_session(self, ns, manager, runner, job):
        if job.plugin not in ['local', 'resource']:
            print("[ {} ]".format(job.name).center(80, '-'))
            if job.description is not None:
                print(job.description)
                print("^" * len(job.description.splitlines()[-1]))
                print()
        job_state = manager.state.job_state_map[job.name]
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
            if job.plugin not in ['local', 'resource']:
                print("Running... (output in {}.*)".format(
                    join(manager.storage.location, slugify(job.name))))
            manager.state.metadata.running_job_name = job.name
            manager.checkpoint()
            # TODO: get a confirmation from the user for certain types of
            # job.plugin
            job_result = runner.run_job(job)
            if (job_result.outcome == IJobResult.OUTCOME_UNDECIDED
                    and self.is_interactive):
                job_result = self._interaction_callback(
                    runner, job, self.config)
            manager.state.metadata.running_job_name = None
            manager.checkpoint()
            if job.plugin not in ['local', 'resource']:
                print("Outcome: {}".format(job_result.outcome))
                if job_result.comments is not None:
                    print("Comments: {}".format(job_result.comments))
        else:
            job_result = MemoryJobResult({
                'outcome': IJobResult.OUTCOME_NOT_SUPPORTED,
                'comments': job_state.get_readiness_description()
            })
        if job_result is not None:
            manager.state.update_job_result(job, job_result)


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
