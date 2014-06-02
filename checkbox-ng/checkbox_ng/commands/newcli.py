# This file is part of Checkbox.
#
# Copyright 2013-2014 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`checkbox_ng.commands.cli` -- Command line sub-command
===========================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from gettext import gettext as _
from logging import getLogger
from shutil import copyfileobj
import io
import json
import operator
import os
import sys

from plainbox.impl.applogic import get_whitelist_by_name
from plainbox.impl.commands.run import RunInvocation
from plainbox.impl.exporter import ByteStringStreamTranslator
from plainbox.impl.exporter import get_all_exporters
from plainbox.impl.exporter.html import HTMLSessionStateExporter
from plainbox.impl.exporter.xml import XMLSessionStateExporter
from plainbox.impl.secure.config import Unset
from plainbox.impl.secure.qualifiers import FieldQualifier
from plainbox.impl.secure.qualifiers import OperatorMatcher
from plainbox.impl.secure.qualifiers import WhiteList
from plainbox.impl.secure.qualifiers import select_jobs
from plainbox.impl.session import SessionMetaData
from plainbox.vendor.textland import get_display

from checkbox_ng.misc import SelectableJobTreeNode
from checkbox_ng.ui import ScrollableTreeNode
from checkbox_ng.ui import ShowMenu
from checkbox_ng.ui import ShowWelcome


logger = getLogger("checkbox.ng.commands.newcli")


class CliInvocation2(RunInvocation):
    """
    Invocation of the 'checkbox cli' command.

    :ivar ns:
        The argparse namespace obtained from CliCommand
    :ivar _settings:
        Settings specific to 'checkbox cli'
    :ivar _display:
        A textland display object
    :ivar _whitelists:
        A list of whitelists to look at
    """

    def __init__(self, provider_list, config, ns, settings, display=None):
        super().__init__(provider_list, config, ns)
        if display is None:
            display = get_display()
        self._settings = settings
        self._display = display
        self._whitelists = []
        self.select_whitelist()

    @property
    def settings(self):
        """
        TBD: 'checkbox cli' specific settings
        """
        return self._settings

    @property
    def display(self):
        """
        A TextLand display object
        """
        return self._display

    def select_whitelist(self):
        if self.ns.whitelist:
            for whitelist in self.ns.whitelist:
                self._whitelists.append(WhiteList.from_file(whitelist.name))
        elif self.config.whitelist is not Unset:
            self._whitelists.append(WhiteList.from_file(self.config.whitelist))
        elif self.ns.include_pattern_list:
            self._whitelists.append(WhiteList(self.ns.include_pattern_list))

    def run(self):
        return self.do_normal_sequence()

    def do_normal_sequence(self):
        """
        Proceed through normal set of steps that are required to runs jobs

        .. note::
            This version is overridden as there is no better way to manage this
            pile rather than having a copy-paste + edits piece of text until
            arrowhead replaced plainbox run internals with a flow chart that
            can be derived meaningfully.

            For now just look for changes as compared to run.py's version.
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
        # XXX: we don't want to know about new jobs just yet
        self.state.on_job_added.disconnect(self.on_job_added)
        # Create the job runner so that we can do stuff
        self.create_runner()
        # If we haven't resumed then do some one-time initialization
        if not resumed:
            # Show the welcome message
            self.show_welcome_screen()
            # Maybe allow the user to do a manual whitelist selection
            self.maybe_interactively_select_whitelists()
            # Store the application-identifying meta-data and checkpoint the
            # session.
            self.store_application_metadata()
            self.metadata.flags.add(SessionMetaData.FLAG_INCOMPLETE)
            self.manager.checkpoint()
            # Run all the local jobs. We need to do this to see all the things
            # the user may select
            self.select_local_jobs()
            self.run_all_selected_jobs()
            self.interactively_pick_jobs_to_run()
        else:
            self.load_app_blob()
        # Maybe ask the secure launcher to prompt for the password now. This is
        # imperfect as we are going to run local jobs and we cannot see if they
        # might need root or not. This cannot be fixed before template jobs are
        # added and local jobs deprecated and removed (at least not being a
        # part of the session we want to execute).
        self.maybe_warm_up_authentication()
        self.print_estimated_duration()
        self.run_all_selected_jobs()
        self.export_and_send_results()
        if SessionMetaData.FLAG_INCOMPLETE in self.metadata.flags:
            print(self.C.header("Session Complete!", "GREEN"))
            self.metadata.flags.remove(SessionMetaData.FLAG_INCOMPLETE)
            self.manager.checkpoint()
        return 0

    def store_application_metadata(self):
        super().store_application_metadata()
        self.metadata.app_blob = json.dumps([
            whitelist.origin.source.filename
            for whitelist in self._whitelists
        ]).encode("UTF-8")
        logger.info("Saved whitelist mask: %r", self._whitelists)

    def load_app_blob(self):
        whitelist_filename_list = json.loads(
            self.metadata.app_blob.decode("UTF-8"))
        whitelist_list = [
            WhiteList.from_file(filename)
            for filename in whitelist_filename_list]
        self._whitelists = whitelist_list
        logger.info("Loaded whitelist mask: %r", self._whitelists)

    def show_welcome_screen(self):
        text = self.settings.get('welcome_text')
        if self.is_interactive and text:
            self.display.run(ShowWelcome(text))

    def maybe_interactively_select_whitelists(self):
        if self.is_interactive and not self._whitelists:
            self._whitelists.extend(self.get_interactively_picked_whitelists())
        else:
            self._whitelists.extend(self.get_default_whitelists())
        logger.info(_("Selected whitelists: %r"), self._whitelists)

    def get_interactively_picked_whitelists(self):
        """
        Show an interactive dialog that allows the user to pick a list of
        whitelists. The set of whitelists is limited to those offered by the
        'default_providers' setting.

        :returns:
            A list of selected whitelists
        """
        whitelist_name_list = []
        for provider in self.provider_list:
            if provider.name in self.settings['default_providers'] or True:
                whitelist_name_list.extend([
                    whitelist.name for whitelist in
                    provider.get_builtin_whitelists()])
        selected_list = self.display.run(
            ShowMenu(_("Suite selection"), whitelist_name_list))
        if not selected_list:
            raise SystemExit(_("No whitelists selected, aborting"))
        return [get_whitelist_by_name(
            self.provider_list, whitelist_name_list[selected_index])
            for selected_index in selected_list]

    def get_default_whitelists(self):
        return [get_whitelist_by_name(
            self.provider_list, self.settings['default_whitelist'])]

    def create_exporter(self):
        """
        Create the ISessionStateExporter based on the command line options

        This sets the :ivar:`_exporter`.
        """
        # TODO:
        self._exporter = None

    def create_transport(self):
        """
        Create the ISessionStateTransport based on the command line options

        This sets the :ivar:`_transport`.
        """
        # TODO:
        self._transport = None

    @property
    def expected_app_id(self):
        return 'checkbox'

    def select_local_jobs(self):
        print(self.C.header(_("Selecting Job Generators")))
        # Create a qualifier list that will pick all local jobs out of the
        # subset of jobs also enumerated by the whitelists we've already
        # picked.
        #
        # Since each whitelist is a qualifier that selects jobs enumerated
        # within, we only need to and an exclusive qualifier that deselects
        # non-local jobs and we're done.
        qualifier_list = []
        qualifier_list.extend(self._whitelists)
        qualifier_list.append(FieldQualifier(
            'plugin', OperatorMatcher(operator.ne, 'local'), inclusive=False))
        local_job_list = select_jobs(
            self.manager.state.job_list, qualifier_list)
        self._update_desired_job_list(local_job_list)

    def interactively_pick_jobs_to_run(self):
        print(self.C.header(_("Selecting Jobs For Execution")))
        self._update_desired_job_list(select_jobs(
            self.manager.state.job_list, self._whitelists))
        tree = SelectableJobTreeNode.create_tree(
            self.manager.state.run_list,
            legacy_mode=True)
        title = _('Choose tests to run on your system:')
        self.display.run(ScrollableTreeNode(tree, title))
        # NOTE: tree.selection is correct but ordered badly.  To retain
        # the original ordering we should just treat it as a mask and
        # use it to filter jobs from desired_job_list.
        wanted_set = frozenset(tree.selection)
        job_list = [job for job in self.manager.state.run_list
                    if job in wanted_set]
        self._update_desired_job_list(job_list)

    def export_and_send_results(self):
        if self.is_interactive:
            print(self.C.header(_("Results")))
            exporter = get_all_exporters()['text']()
            exported_stream = io.BytesIO()
            data_subset = exporter.get_session_data_subset(self.manager.state)
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
            data_subset = exporter.get_session_data_subset(self.manager.state)
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
