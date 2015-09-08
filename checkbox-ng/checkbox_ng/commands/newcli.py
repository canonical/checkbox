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
import operator
import os
import re
import sys

from plainbox.abc import IJobResult
from plainbox.impl.commands.inv_run import RunInvocation
from plainbox.impl.exporter import ByteStringStreamTranslator
from plainbox.impl.secure.config import Unset, ValidationError
from plainbox.impl.secure.origin import CommandLineTextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.qualifiers import FieldQualifier
from plainbox.impl.secure.qualifiers import OperatorMatcher
from plainbox.impl.secure.qualifiers import RegExpJobQualifier
from plainbox.impl.secure.qualifiers import select_jobs
from plainbox.impl.session import SessionMetaData
from plainbox.impl.transport import get_all_transports
from plainbox.impl.transport import TransportError
from plainbox.vendor.textland import get_display

from checkbox_ng.misc import SelectableJobTreeNode
from checkbox_ng.ui import ScrollableTreeNode
from checkbox_ng.ui import ShowMenu
from checkbox_ng.ui import ShowRerun
from checkbox_ng.ui import ShowWelcome


logger = getLogger("checkbox.ng.commands.newcli")


class CliInvocation2(RunInvocation):
    """
    Invocation of the 'checkbox cli' command.

    :ivar ns:
        The argparse namespace obtained from CliCommand
    :ivar _launcher:
        launcher specific to 'checkbox cli'
    :ivar _display:
        A textland display object
    :ivar _qualifier_list:
        A list of job qualifiers used to build the session desired_job_list
    """

    def __init__(self, provider_loader, config_loader, ns, launcher,
                 display=None):
        super().__init__(provider_loader, config_loader, ns, ns.color)
        if display is None:
            display = get_display()
        self._launcher = launcher
        self._display = display
        self._qualifier_list = []
        self._testplan_list = []
        self.select_qualifier_list()

    @property
    def launcher(self):
        """
        TBD: 'checkbox cli' specific launcher settings
        """
        return self._launcher

    @property
    def display(self):
        """
        A TextLand display object
        """
        return self._display

    def select_qualifier_list(self):
        # Add whitelists
        if 'whitelist' in self.ns and self.ns.whitelist:
            for whitelist_file in self.ns.whitelist:
                qualifier = self.get_whitelist_from_file(
                    whitelist_file.name, whitelist_file)
                if qualifier is not None:
                    self._qualifier_list.append(qualifier)
        # Add all the --include jobs
        for pattern in self.ns.include_pattern_list:
            origin = Origin(CommandLineTextSource('-i', pattern), None, None)
            try:
                qualifier = RegExpJobQualifier(
                    '^{}$'.format(pattern), origin, inclusive=True)
            except Exception as exc:
                logger.warning(
                    _("Incorrect pattern %r: %s"), pattern, exc)
            else:
                self._qualifier_list.append(qualifier)
        # Add all the --exclude jobs
        for pattern in self.ns.exclude_pattern_list:
            origin = Origin(CommandLineTextSource('-x', pattern), None, None)
            try:
                qualifier = RegExpJobQualifier(
                    '^{}$'.format(pattern), origin, inclusive=False)
            except Exception as exc:
                logger.warning(
                    _("Incorrect pattern %r: %s"), pattern, exc)
            else:
                self._qualifier_list.append(qualifier)
        if self.config.whitelist is not Unset:
            self._qualifier_list.append(
                self.get_whitelist_from_file(self.config.whitelist))

    def select_testplan(self):
        # Add the test plan
        if self.ns.test_plan is not None:
            for provider in self.provider_list:
                for unit in provider.id_map[self.ns.test_plan]:
                    if unit.Meta.name == 'test plan':
                        self._qualifier_list.append(unit.get_qualifier())
                        self._testplan_list.append(unit)
                        return
            else:
                logger.error(_("There is no test plan: %s"), self.ns.test_plan)

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
        # Create transport early so that we can handle bugs before starting the
        # session.
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
            # Process testplan command line options
            self.select_testplan()
            # Maybe allow the user to do a manual whitelist selection
            if not self._qualifier_list:
                self.maybe_interactively_select_testplans()
            if self._testplan_list:
                self.manager.test_plans = tuple(self._testplan_list)
            # Store the application-identifying meta-data and checkpoint the
            # session.
            self.store_application_metadata()
            self.metadata.flags.add(SessionMetaData.FLAG_INCOMPLETE)
            self.manager.checkpoint()
            # Run all the local jobs. We need to do this to see all the things
            # the user may select
            if self.is_interactive:
                self.select_local_jobs()
                self.run_all_selected_jobs()
            self.interactively_pick_jobs_to_run()
        # Maybe ask the secure launcher to prompt for the password now. This is
        # imperfect as we are going to run local jobs and we cannot see if they
        # might need root or not. This cannot be fixed before template jobs are
        # added and local jobs deprecated and removed (at least not being a
        # part of the session we want to execute).
        self.maybe_warm_up_authentication()
        self.print_estimated_duration()
        self.run_all_selected_jobs()
        if self.is_interactive:
            while True:
                if self.maybe_rerun_jobs():
                    continue
                else:
                    break
        self.export_and_send_results()
        if SessionMetaData.FLAG_INCOMPLETE in self.metadata.flags:
            print(self.C.header("Session Complete!", "GREEN"))
            self.metadata.flags.remove(SessionMetaData.FLAG_INCOMPLETE)
            self.manager.checkpoint()
        return 0

    def store_application_metadata(self):
        super().store_application_metadata()
        self.metadata.app_blob = b''

    def show_welcome_screen(self):
        text = self.launcher.text
        if self.is_interactive and text:
            self.display.run(ShowWelcome(text))

    def maybe_interactively_select_testplans(self):
        if self.launcher.skip_whitelist_selection:
            self._qualifier_list.extend(self.get_default_testplans())
        elif self.is_interactive:
            self._qualifier_list.extend(
                self.get_interactively_picked_testplans())
        elif self.launcher.whitelist_selection:
            self._qualifier_list.extend(self.get_default_testplans())
        logger.info(_("Selected testplans: %r"), self._qualifier_list)

    def get_interactively_picked_testplans(self):
        """
        Show an interactive dialog that allows the user to pick a list of
        testplans. The set of testplans is limited to those offered by the
        'default_providers' setting.

        :returns:
            A list of selected testplans
        """
        testplans = []
        testplan_selection = []
        for provider in self.provider_list:
            testplans.extend(
                [unit for unit in provider.unit_list if
                 unit.Meta.name == 'test plan' and
                 re.search(self.launcher.whitelist_filter, unit.partial_id)])
        testplan_name_list = [testplan.tr_name() for testplan in testplans]
        testplan_selection = [
            testplans.index(t) for t in testplans if
            re.search(self.launcher.whitelist_selection, t.partial_id)]
        selected_list = self.display.run(
            ShowMenu(_("Suite selection"), testplan_name_list,
                     testplan_selection))
        if not selected_list:
            raise SystemExit(_("No testplan selected, aborting"))
        self._testplan_list.extend(
            [testplans[selected_index] for selected_index in selected_list])
        return [testplans[selected_index].get_qualifier() for selected_index
                in selected_list]

    def get_default_testplans(self):
        testplans = []
        for provider in self.provider_list:
            testplans.extend([
                unit.get_qualifier() for unit in provider.unit_list if
                unit.Meta.name == 'test plan' and re.search(
                    self.launcher.whitelist_selection, unit.partial_id)])
        return testplans

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
        qualifier_list.extend(self._qualifier_list)
        origin = Origin.get_caller_origin()
        qualifier_list.append(FieldQualifier(
            'plugin', OperatorMatcher(operator.ne, 'local'), origin,
            inclusive=False))
        local_job_list = select_jobs(
            self.manager.state.job_list, qualifier_list)
        self._update_desired_job_list(local_job_list)

    def interactively_pick_jobs_to_run(self):
        print(self.C.header(_("Selecting Jobs For Execution")))
        self._update_desired_job_list(select_jobs(
            self.manager.state.job_list, self._qualifier_list))
        if self.launcher.skip_test_selection or not self.is_interactive:
            return
        tree = SelectableJobTreeNode.create_tree(
            self.manager.state, self.manager.state.run_list)
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
            exporter = self.manager.create_exporter(
                '2013.com.canonical.plainbox::text')
            exported_stream = io.BytesIO()
            exporter.dump_from_session_manager(self.manager, exported_stream)
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
        exp_options = ['with-sys-info', 'with-summary', 'with-job-description',
                       'with-text-attachments', 'with-certification-status',
                       'with-job-defs', 'with-io-log', 'with-comments']
        print()
        if self.launcher.exporter is not Unset:
            exporters = self.launcher.exporter
        else:
            exporters = [
                '2013.com.canonical.plainbox::hexr',
                '2013.com.canonical.plainbox::html',
                '2013.com.canonical.plainbox::xlsx',
                '2013.com.canonical.plainbox::json',
            ]
        for unit_name in exporters:
            exporter = self.manager.create_exporter(
                unit_name, exp_options, strict=False)
            extension = exporter.unit.file_extension
            results_path = os.path.join(
                base_dir, 'submission.{}'.format(extension))
            with open(results_path, "wb") as stream:
                exporter.dump_from_session_manager(self.manager, stream)
            print(_("View results") + " ({}): file://{}".format(
                extension, results_path))
        self.submission_file = os.path.join(base_dir, 'submission.xml')
        if self.launcher.submit_to is not Unset:
            if self.launcher.submit_to == 'certification':
                # If we supplied a submit_url in the launcher, it
                # should override the one in the config.
                if self.launcher.submit_url:
                    self.config.c3_url = self.launcher.submit_url
                # Same behavior for submit_to_hexr (a boolean flag which
                # should result in adding "submit_to_hexr=1" to transport
                # options later on)
                if self.launcher.submit_to_hexr:
                    self.config.submit_to_hexr = True
                # for secure_id, config (which is user-writable) should
                # override launcher (which is not)
                if not self.config.secure_id:
                    self.config.secure_id = self.launcher.secure_id
                # Override the secure_id configuration with the one provided
                # by the command-line option
                if self.ns.secure_id:
                    self.config.secure_id = self.ns.secure_id
                if self.config.secure_id is Unset:
                    again = True
                    if not self.is_interactive:
                        again = False
                    while again:
                        # TRANSLATORS: Do not translate the {} format marker.
                        if self.ask_for_confirmation(
                            _("\nSubmit results to {0}?".format(
                                self.launcher.submit_url))):
                            try:
                                self.config.secure_id = input(_("Secure ID: "))
                            except ValidationError:
                                print(
                                    _("ERROR: Secure ID must be 15 or "
                                      "18-character alphanumeric string"))
                            else:
                                again = False
                                self.submit_certification_results()
                        else:
                            again = False
                else:
                    # Automatically try to submit results if the secure_id is
                    # valid
                    self.submit_certification_results()
            elif self.launcher.submit_to == 'launchpad':
                if self.config.email_address is Unset:
                    again = True
                    if not self.is_interactive:
                        again = False
                    while again:
                        if self.ask_for_confirmation(
                                _("\nSubmit results to launchpad.net/+hwdb?")):
                            self.config.email_address = input(
                                _("Email address: "))
                            again = False
                            self.submit_launchpad_results()
                        else:
                            again = False
                else:
                    # Automatically try to submit results if the email_address
                    # is valid
                    self.submit_launchpad_results()

    def submit_launchpad_results(self):
        transport_cls = get_all_transports().get('launchpad')
        options_string = "field.emailaddress={}".format(
            self.config.email_address)
        transport = transport_cls(self.config.lp_url, options_string)
        # TRANSLATORS: Do not translate the {} format markers.
        print(_("Submitting results to {0} for email_address {1})").format(
            self.config.lp_url, self.config.email_address))
        with open(self.submission_file, encoding='utf-8') as stream:
            try:
                # NOTE: don't pass the file-like object to this transport
                json = transport.send(
                    stream.read(),
                    self.config,
                    session_state=self.manager.state)
                if json.get('url'):
                    # TRANSLATORS: Do not translate the {} format marker.
                    print(_("Submission uploaded to: {0}".format(json['url'])))
                elif json.get('status'):
                    print(json['status'])
                else:
                    # TRANSLATORS: Do not translate the {} format marker.
                    print(
                        _("Bad response from {0} transport".format(transport)))
            except TransportError as exc:
                print(str(exc))

    def submit_certification_results(self):
        from checkbox_ng.certification import InvalidSecureIDError
        transport_cls = get_all_transports().get('certification')
        # TRANSLATORS: Do not translate the {} format markers.
        print(_("Submitting results to {0} for secure_id {1})").format(
            self.config.c3_url, self.config.secure_id))
        option_chunks = []
        option_chunks.append("secure_id={0}".format(self.config.secure_id))
        if self.config.submit_to_hexr:
            option_chunks.append("submit_to_hexr=1")
        # Assemble the option string
        options_string = ",".join(option_chunks)
        # Create the transport object
        try:
            transport = transport_cls(
                self.config.c3_url, options_string)
        except InvalidSecureIDError as exc:
            print(exc)
            return False
        with open(self.submission_file) as stream:
            try:
                # Send the data, reading from the fallback file
                result = transport.send(stream, self.config)
                if 'url' in result:
                    # TRANSLATORS: Do not translate the {} format marker.
                    print(_("Successfully sent, submission status"
                            " at {0}").format(result['url']))
                else:
                    # TRANSLATORS: Do not translate the {} format marker.
                    print(_("Successfully sent, server response"
                            ": {0}").format(result))
            except TransportError as exc:
                print(str(exc))

    def maybe_rerun_jobs(self):
        def rerun_predicate(job_state):
            return job_state.result.outcome in (
                IJobResult.OUTCOME_FAIL, IJobResult.OUTCOME_CRASH)
        # create a list of jobs that qualify for rerunning
        rerun_candidates = []
        for job in self.manager.state.run_list:
            if rerun_predicate(self.manager.state.job_state_map[job.id]):
                rerun_candidates.append(job)
        # bail-out early if no job qualifies for rerunning
        if not rerun_candidates:
            return False
        tree = SelectableJobTreeNode.create_tree(
            self.manager.state, rerun_candidates)
        # deselect all by default
        tree.set_descendants_state(False)
        self.display.run(ShowRerun(tree, _("Select jobs to re-run")))
        wanted_set = frozenset(tree.selection)
        if not wanted_set:
            # nothing selected - nothing to run
            return False
        rerun_job_list = [job for job in self.manager.state.run_list
                          if job in wanted_set]
        # reset outcome of jobs that are selected for re-running
        for job in wanted_set:
            from plainbox.impl.result import MemoryJobResult
            self.manager.state.job_state_map[job.id].result = \
                MemoryJobResult({})
        self.run_all_selected_jobs()
        return True
