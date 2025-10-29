# This file is part of Checkbox.
#
# Copyright 2017-2023 Canonical Ltd.
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
This module contains implementation of the controller end of the remote execution
functionality.
"""
import contextlib
import getpass
import gettext
import ipaddress
import json
import logging
import os
import select
import socket
import time
import signal
import sys
import itertools

from collections import namedtuple
from contextlib import suppress
from functools import partial
from tempfile import SpooledTemporaryFile

from plainbox.abc import IJobResult
from plainbox.impl.result import MemoryJobResult
from plainbox.impl.color import Colorizer
from plainbox.impl.config import Configuration
from plainbox.impl.session.state import SessionMetaData
from plainbox.impl.session.resume import (
    IncompatibleJobError,
    CorruptedSessionError,
)
from plainbox.impl.session.remote_assistant import (
    RemoteSessionAssistant,
    RemoteSessionStates,
)
from plainbox.vendor import rpyc
from checkbox_ng.resume_menu import ResumeMenu
from checkbox_ng.urwid_ui import (
    TestPlanBrowser,
    CategoryBrowser,
    ManifestBrowser,
    ReRunBrowser,
    interrupt_dialog,
    resume_dialog,
    ResumeInstead,
)
from checkbox_ng.utils import (
    generate_resume_candidate_description,
    newline_join,
    request_comment,
)
from checkbox_ng.launcher.run import NormalUI, ReRunJob
from checkbox_ng.launcher.stages import MainLoopStage
from checkbox_ng.launcher.stages import ReportsStage
from tqdm import tqdm

_ = gettext.gettext
_logger = logging.getLogger("controller")


class SimpleUI(NormalUI, MainLoopStage):
    """
    Simplified version of the NormalUI from checkbox_ng.launcher.run.

    The simplification is mainly about just dealing with text that is to be
    displayed, instead of the plainbox abstractions like job, job state, etc.

    It's a class just for namespacing purposes.
    """

    C = Colorizer()

    # XXX: evaluate other ways of aggregating those functions

    def description(header, text):
        print(SimpleUI.C.WHITE(header))
        print()
        print(SimpleUI.C.CYAN(text))
        print()

    def header(header):
        print(SimpleUI.C.header(header, fill="-"))

    def green_text(text, end="\n"):
        print(SimpleUI.C.GREEN(text), end=end, file=sys.stdout)

    def red_text(text, end="\n"):
        print(SimpleUI.C.RED(text), end=end, file=sys.stderr)

    def black_text(text, end="\n"):
        print(SimpleUI.C.BLACK(text), end=end, file=sys.stdout)

    def horiz_line():
        print(SimpleUI.C.WHITE("-" * 80))

    @property
    def is_interactive(self):
        return True

    @property
    def sa(self):
        None


class RemoteController(ReportsStage, MainLoopStage):
    """
    Control remote agent instance

    This class implements the part that presents UI to the operator and
    steers the session.
    """

    name = "remote-control"

    @classmethod
    def connection_strategy(cls):
        """
        This is the action the controller takes when connecting to an agent.

        Given that the session may be on-going, the state will not always be
        RemoteSessionStates.Idle but may vary. All functions declared here
        must take two parameters, self + payload. Both state and payload are
        returned from the agent
        """
        return {
            RemoteSessionStates.Idle: cls.resume_or_start_new_session,
            RemoteSessionStates.Started: cls.restart,
            RemoteSessionStates.SettingUp: cls.setup_and_continue,
            RemoteSessionStates.SetupCompleted: cls.restart,
            RemoteSessionStates.Bootstrapping: cls.restart,
            RemoteSessionStates.Bootstrapped: cls.resume_select_jobs,
            RemoteSessionStates.TestsSelected: cls.run_interactable_jobs,
            RemoteSessionStates.Running: cls.wait_and_continue,
            RemoteSessionStates.Interacting: cls.resume_interacting,
            RemoteSessionStates.Finalizing: cls.finish_session,
        }

    @property
    def is_interactive(self):
        return (
            self.launcher.get_value("ui", "type") == "interactive"
            and sys.stdin.isatty()
            and sys.stdout.isatty()
        )

    @property
    def C(self):
        return self._C

    @property
    def sa(self) -> RemoteSessionAssistant:
        return self._sa

    def invoked(self, ctx):
        self._C = Colorizer()
        self._override_exporting(self.local_export)
        self._launcher_text = ""
        self._has_anything_failed = False
        self._target_host = ctx.args.host
        self._normal_user = ""
        self.launcher = Configuration()
        if ctx.args.launcher:
            expanded_path = os.path.expanduser(ctx.args.launcher)
            if not os.path.exists(expanded_path):
                raise SystemExit(
                    _("{} launcher file was not found!").format(expanded_path)
                )
            with open(expanded_path, "rt") as f:
                self._launcher_text = f.read()
            self.launcher = Configuration.from_text(
                self._launcher_text, "Controller:{}".format(expanded_path)
            )
        if ctx.args.user:
            self._normal_user = ctx.args.user
        timeout = 600
        deadline = time.time() + timeout
        port = ctx.args.port

        if not is_hostname_a_loopback(ctx.args.host):
            print(
                _("Connecting to {}:{}. Timeout: {}s").format(
                    ctx.args.host, port, timeout
                )
            )
        while time.time() < deadline:
            try:
                return self.connect_and_run(ctx.args.host, port)
            except (ConnectionRefusedError, socket.timeout, OSError):
                print(".", end="", flush=True)
                time.sleep(1)
        else:
            raise SystemExit(_("\nConnection timed out."))

    def check_remote_api_match(self):
        """
        Check that agent and controller are running on the same
        REMOTE_API_VERSION else exit checkbox with an error
        """
        try:
            agent_api_version = self.sa.get_remote_api_version()
        except AttributeError:
            raise SystemExit(
                _(
                    "Agent doesn't declare Remote API"
                    " version. Update Checkbox on the"
                    " DUT!"
                )
            )
        controller_api_version = RemoteSessionAssistant.REMOTE_API_VERSION

        if agent_api_version == controller_api_version:
            return

        newer_msg = _(
            "The controller that you are using is newer than the agent "
            "you are trying to connect to.\n"
            "To solve this, upgrade the agent to the controller version.\n"
            "If you are unsure about the nomenclature or what any of this "
            "means, see:\n"
            "https://checkbox.readthedocs.io/en/latest/reference/"
            "glossary.html\n\n"
            "Error: (Agent version: {}, Controller version {})"
        )

        older_msg = _(
            "The controller that you are using is older than the agent "
            "you are trying to connect to.\n"
            "To solve this, upgrade the controller to the agent version.\n"
            "If you are unsure about the nomenclature or what any of this "
            "means, see:\n"
            "https://checkbox.readthedocs.io/en/latest/reference/"
            "glossary.html\n\n"
            "Error: (Agent version: {}, Controller version {})"
        )

        if controller_api_version > agent_api_version:
            problem_msg = newer_msg
        else:
            problem_msg = older_msg

        raise SystemExit(
            problem_msg.format(agent_api_version, controller_api_version)
        )

    def connect_and_run(self, host, port=18871):
        config = rpyc.core.protocol.DEFAULT_CONFIG.copy()
        config["allow_all_attrs"] = True
        # this is the max client to server attr accessing speed, unbounded (-1)
        # to avoid timing out on any attr request on an enstablished call. This
        # way even particularly slow @properties won't fail
        config["sync_request_timeout"] = -1

        keep_running = False
        server_msg = None
        self._prepare_transports()
        interrupted = False
        # Used to cleanly print reconnecting
        #  this is used to print reconnecting
        printed_reconnecting = False
        #  check if ever disconnected
        ever_disconnected = False
        #  this to animate the dash
        spinner = itertools.cycle("-\\|/")
        #  this tracks the disconnection time
        disconnection_time = 0
        connection_strategy = self.connection_strategy()
        while True:
            try:
                if interrupted:
                    _logger.info("controller: Session interrupted")
                    interrupted = False  # we are handling the interruption ATM
                    # next line can raise exception due to connection being
                    # lost so let's set the default behavior to quitting
                    keep_running = False
                    keep_running = self._handle_interrupt()
                    if not keep_running:
                        break
                conn = rpyc.connect(host, port, config=config, keepalive=True)
                keep_running = True

                def quitter(msg):
                    # this will be called when the agent decides to disconnect
                    # this controller
                    nonlocal server_msg
                    nonlocal keep_running
                    keep_running = False
                    server_msg = msg

                with contextlib.suppress(AttributeError):
                    # TODO: REMOTE_API
                    # when bumping the remote api make this bit obligatory
                    # i.e. remove the suppressing
                    conn.root.register_controller_blaster(quitter)
                self._sa = conn.root.get_sa()
                self.sa.conn = conn
                # TODO: REMOTE API RAPI: Remove this API on the next RAPI bump
                # the check and bailout is not needed if the agent as up to
                # date as this controller, so after bumping RAPI we can assume
                # that agent is always passwordless
                if not self.sa.passwordless_sudo:
                    raise SystemExit(
                        _(
                            "This version of Checkbox requires the agent"
                            " to be run as root"
                        )
                    )

                self.check_remote_api_match()

                state, payload = self.sa.whats_up()
                _logger.info("controller: Main dispatch with state: %s", state)
                if printed_reconnecting and ever_disconnected:
                    print(
                        "...\nReconnected (took: {}s)".format(
                            int(time.time() - disconnection_time)
                        )
                    )
                    printed_reconnecting = False
                keep_running = self.continue_session()
            except EOFError as exc:
                if keep_running:
                    print("Connection lost!")
                    # this is yucky but it works, in case of explicit
                    # connection closing by the agent we get this msg
                    _logger.info("controller: Connection lost due to: %s", exc)
                    if str(exc) == "stream has been closed":
                        print(
                            "Agent explicitly disconnected you. Possible "
                            "reason: new controller connected to the agent"
                        )
                        break
                    print(exc)
                    time.sleep(1)
                else:
                    # if keep_running got set to False it means that the
                    # network interruption was planned, AKA agent disconnected
                    # this controller
                    print(server_msg)
                    break
            except (ConnectionRefusedError, socket.timeout, OSError) as exc:
                _logger.info("controller: Connection lost due to: %s", exc)
                if not keep_running:
                    raise
                # it's reconnecting, so we can ignore refuses
                if not printed_reconnecting:
                    print("Reconnecting ", end="")
                    disconnection_time = time.time()
                    ever_disconnected = True
                    printed_reconnecting = True
                print(next(spinner), end="\b", flush=True)
                time.sleep(0.25)
            except KeyboardInterrupt:
                interrupted = True

            if not keep_running:
                break
        return self._has_anything_failed

    def should_start_via_launcher(self):
        """
        Determines if the controller should automatically select a test plan
        if given a launcher. Raises if the launcher tries to skip the test plan
        selection without providing the test plan that must be automatically
        selected
        """
        tp_forced = self.launcher.get_value("test plan", "forced")
        chosen_tp = self.launcher.get_value("test plan", "unit")
        if tp_forced and not chosen_tp:
            raise SystemExit(
                "The test plan selection was forced but no unit was provided"
            )  # split me into lines
        return tp_forced

    @contextlib.contextmanager
    def _resumed_session(self, session_id):
        """
        Used to temporarily resume a session to inspect it, abandoning it
        before exiting the context
        """
        try:
            yield self.sa.prepare_resume_session(session_id)
        except rpyc.core.vinegar.GenericException as e:
            # cast back the (custom) remote exception for IncompatibleJobError
            # (that is of type GenericException due to rpyc)
            # so that it can be treated as a normal "local" exception"
            if "plainbox.impl.session.resume.IncompatibleJobError" in str(e):
                raise IncompatibleJobError(*e.args)
            if "plainbox.impl.session.resume.CorruptedSessionError" in str(e):
                raise CorruptedSessionError(*e.args)
            raise
        finally:
            self.sa.abandon_session()

    def should_start_via_autoresume(self) -> bool:
        """
        Determines if the controller should automatically resume a previously
        abandoned session.

        A session is automatically resumed if:
        - A testplan was selected before abandoning
        - A job was in progress when the session was abandoned
        - The ongoing test was shell job
        """
        try:
            last_abandoned_session = next(self.sa.get_resumable_sessions())
        except StopIteration:
            # no session to resume
            return False
        # Resume the session if the last session was abandoned during the setup
        if (
            SessionMetaData.FLAG_SETTING_UP
            in last_abandoned_session.metadata.flags
        ):
            return True
        # resume session in agent to be able to peek at the latest job run
        # info
        # FIXME: IncompatibleJobError is raised if the resume candidate is
        #        invalid, this is a workaround till get_resumable_sessions is
        #        fixed
        with contextlib.suppress(IncompatibleJobError), contextlib.suppress(
            CorruptedSessionError
        ), self._resumed_session(last_abandoned_session.id) as metadata:
            app_blob = json.loads(metadata.app_blob.decode("UTF-8"))

            if not app_blob.get("testplan_id"):
                return False

            self.sa.select_test_plan(app_blob["testplan_id"])
            self.sa.bootstrap()

            if not metadata.running_job_name:
                return False

            job_state = self.sa.get_job_state(metadata.running_job_name)
            if job_state.job.plugin != "shell":
                return False
            return True
        # last resumable session is incompatible
        return False

    def bootstrap_and_continue(self, resume_payload=None):
        self.bootstrap(resume_payload=resume_payload)
        if not self.jobs:
            self.sa.finalize_session()
            raise SystemExit("There were no tests to select from!")
        self.select_jobs(self.jobs)
        return self.run_interactable_jobs()

    def setup_and_continue(self, resume_payload=None):
        self.setup(resume_payload=resume_payload)
        self.bootstrap_and_continue()

    def automatically_start_via_launcher_and_continue(self):
        _ = self.start_session()
        test_plan_unit = self.launcher.get_value("test plan", "unit")
        self.select_test_plan(test_plan_unit)
        return self.setup_and_continue()

    def resume_last_session_and_continue(self):
        last_abandoned_session = next(self.sa.get_resumable_sessions())
        return self.resume_by_id(last_abandoned_session.id)

    def start_session(self):
        _logger.info("controller: Starting new session.")
        configuration = dict()
        configuration["launcher"] = self._launcher_text
        configuration["normal_user"] = self._normal_user
        try:
            _logger.info("remote: Starting new session.")
            tps = self.sa.start_session_json(json.dumps(configuration))
            tps = json.loads(tps)
            if self.sa.sideloaded_providers:
                _logger.warning("Agent is using sideloaded providers")
        except RuntimeError as exc:
            raise SystemExit(exc.args[0]) from exc
        return tps

    def resume_or_start_new_session(self, *args):
        if self.should_start_via_autoresume():
            return self.resume_last_session_and_continue()
        elif self.should_start_via_launcher():
            return self.automatically_start_via_launcher_and_continue()
        else:
            return self.interactively_choose_test_plan_and_continue()

        # this should be unreachable, inner functions must exit!
        raise SystemExit("Invalid session flow, failed to terminate")

    def resume_by_id(self, session_id, result_dict={}):
        self.sa.resume_by_id(session_id, result_dict)
        # resume_by_id will get us to a resumable state, lets see how to
        # continue
        self.continue_session()

    def continue_session(self):
        """
        Continue the session as instructed from the remote assistant.
        """
        state, payload = self.sa.whats_up()
        state = RemoteSessionStates(state)
        return self.connection_strategy()[state](self, payload)

    def _resume_session(self, resume_params):
        metadata = self.sa.prepare_resume_session(resume_params.session_id)
        if "testplanless" not in metadata.flags:
            app_blob = json.loads(metadata.app_blob.decode("UTF-8"))
            test_plan_id = app_blob["testplan_id"]
            self.sa.select_test_plan(test_plan_id)
            self.sa.bootstrap()
        last_job = metadata.running_job_name
        is_cert_blocker = (
            self.sa.get_job_state(last_job).effective_certification_status
            == "blocker"
        )
        # If we resumed maybe not rerun the same, probably broken job
        result_dict = {
            "comments": resume_params.comments,
        }
        if resume_params.action == "pass":
            result_dict["comments"] = newline_join(
                result_dict["comments"], "Passed after resuming execution"
            )

            result_dict["outcome"] = IJobResult.OUTCOME_PASS
        elif resume_params.action == "fail":
            if is_cert_blocker and not resume_params.comments:
                # cert blockers must be commented when failing
                result_dict["comments"] = request_comment("why it failed.")
            else:
                result_dict["comments"] = newline_join(
                    result_dict["comments"], "Failed after resuming execution"
                )

            result_dict["outcome"] = IJobResult.OUTCOME_FAIL
        elif resume_params.action == "skip":
            if is_cert_blocker and not resume_params.comments:
                # cert blockers must be commented when skipped
                result_dict["comments"] = request_comment(
                    "why you want to skip it."
                )
            else:
                result_dict["comments"] = newline_join(
                    result_dict["comments"], "Skipped after resuming execution"
                )
            result_dict["outcome"] = IJobResult.OUTCOME_SKIP
        elif resume_params.action == "rerun":
            # if the job outcome is set to none it will be rerun
            result_dict["outcome"] = None
        return self.resume_by_id(resume_params.session_id, result_dict)

    def interactively_choose_test_plan_and_continue(self):
        tps = self.start_session()
        _logger.info("controller: Interactively choosing TP.")
        while True:
            resumable_sessions = list(self.sa.get_resumable_sessions())
            with suppress(ResumeInstead):
                self.select_test_plan_via_menu(tps, resumable_sessions)
                return self.setup_and_continue()
            if self.resume_session_via_menu_and_continue(resumable_sessions):
                return False

    def setup(self, resume_payload=None):
        setup_jobs = json.loads(self.sa.start_setup_json())
        starting_index = 0
        if resume_payload:
            last_running_job = resume_payload["last_job"]
            # this can't fail as we have adopted the result when this is set
            # so if the job doesn't exist, it will crash before
            starting_index = next(
                i
                for (i, job_id) in enumerate(setup_jobs)
                if job_id == last_running_job
            )
            # if the job outcome was already decided (either interactively or
            # by the resume process) go on
            if self.sa.get_job_result(last_running_job).outcome is not None:
                starting_index += 1
        self.run_uninteractable_jobs(
            setup_jobs,
            "Setup",
            starting_index=starting_index,
            suppress_output=False,
        )
        failed_setups = self.sa.finish_setup()
        return failed_setups

    def select_test_plan_via_menu(self, tps, resumable_sessions):
        """
        Displays the test plan selection menu and selects the test plan.

        Raises ResumeInstead if the resume menu is requested.
        """
        tp_info_list = [{"id": tp[0], "name": tp[1]} for tp in tps]
        if not tp_info_list:
            _logger.error(_("There were no test plans to select from!"))
            raise SystemExit(0)
        selected_tp = TestPlanBrowser(
            _("Select test plan"),
            tp_info_list,
            self.launcher.get_value("test plan", "unit"),
            len(resumable_sessions),
        ).run()
        if selected_tp is None:
            print(_("Nothing selected"))
            raise SystemExit(0)
        self.select_test_plan(selected_tp)

    def resume_session_via_menu_and_continue(self, resumable_sessions):
        """
        Run the interactive resume menu.
        Returns True if a session was resumed, False otherwise.
        """
        entries = [
            (
                candidate.id,
                generate_resume_candidate_description(candidate),
            )
            for candidate in resumable_sessions
        ]
        while True:
            # let's loop until someone selects something else than "delete"
            # in other words, after each delete action let's go back to the
            # resume menu

            resume_params = ResumeMenu(entries).run()
            if resume_params.action == "delete":
                self.sa.delete_sessions([resume_params.session_id])
                self.resume_candidates = list(self.sa.get_resumable_sessions())

                # the entries list is just a copy of the resume_candidates,
                # and it's not updated when we delete a session, so we need
                # to update it manually
                entries = [
                    en for en in entries if en[0] != resume_params.session_id
                ]

                if not entries:
                    # if everything got deleted let's go back to the test plan
                    # selection menu
                    return False
            else:
                break

        if resume_params.session_id:
            self._resume_session(resume_params)
            return True
        return False

    def bootstrap(self, resume_payload=None):
        """
        This is the bootstrap job-running UI

        This is different from calling self.sa.bootstrap because this shows
        progress (currently running job and result) while that is silent
        """
        if resume_payload is not None:
            raise SystemExit("not supported")
        bs_todo = json.loads(self.sa.start_bootstrap_json())
        self.run_uninteractable_jobs(
            bs_todo, "Bootstrap", starting_index=0, suppress_output=True
        )
        self.jobs = json.loads(self.sa.finish_bootstrap_json())
        return self.jobs

    def select_test_plan(self, testplan_id):
        _logger.info("controller: Selected test plan: %s", testplan_id)
        try:
            self.sa.select_test_plan(testplan_id)
        except KeyError as e:
            _logger.error('The test plan "%s" is not available!', testplan_id)
            raise SystemExit(1)

    def _strtobool(self, val):
        return val.lower() in ("y", "yes", "t", "true", "on", "1")

    def _save_manifest(self, interactive):
        manifest_repr = self.sa.get_manifest_repr_json()
        manifest_repr = json.loads(manifest_repr)
        if not manifest_repr:
            _logger.info("Skipping saving of the manifest")
            return

        if interactive and ManifestBrowser.has_visible_manifests(
            manifest_repr
        ):
            # Ask the user the values
            to_save_manifest = ManifestBrowser(
                "System Manifest:", manifest_repr
            ).run()
        else:
            # Use the one provided in repr (either non-interactive or no visible manifests)
            to_save_manifest = ManifestBrowser.get_flattened_values(
                manifest_repr
            )

        self.sa.save_manifest_json(json.dumps(to_save_manifest))

    def resume_select_jobs(self, all_jobs_json):
        return self.select_jobs(json.loads(all_jobs_json))

    def select_jobs(self, all_jobs):
        if self.launcher.get_value("test selection", "forced"):
            if self.launcher.manifest:
                self._save_manifest(interactive=False)
        else:
            _logger.info("controller: Selecting jobs.")
            reprs = json.loads(
                self.sa.get_jobs_repr_json(json.dumps(all_jobs))
            )
            wanted_set = CategoryBrowser(
                "Choose tests to run on your system:", reprs
            ).run()
            # no need to set an alternate selection if the job list not changed
            if len(reprs) != len(wanted_set):
                # wanted_set may have bad order, let's use it as a filter to
                # the original list
                chosen_jobs = [job for job in all_jobs if job in wanted_set]
                _logger.debug("controller: Selected jobs: %s", chosen_jobs)
                self.sa.modify_todo_list_json(json.dumps(chosen_jobs))
            self._save_manifest(interactive=True)
        self.sa.finish_job_selection()

    def register_arguments(self, parser):
        parser.add_argument("host", help=_("target host"))
        parser.add_argument(
            "launcher", nargs="?", help=_("launcher definition file to use")
        )
        parser.add_argument(
            "--port", type=int, default=18871, help=_("port to connect to")
        )
        parser.add_argument(
            "-u", "--user", help=_("normal user to run non-root jobs")
        )

    def _handle_interrupt(self):
        """
        Returns True if the controller should keep running.
        And False if it should quit.
        """
        if self.launcher.get_value("ui", "type") == "silent":
            self._sa.terminate()
            return False
        response = interrupt_dialog(self._target_host)
        if response == "cancel":
            return True
        elif response == "kill-controller":
            return False
        elif response == "kill-agent":
            self._sa.terminate()
            return False
        elif response == "abandon":
            self._sa.finalize_session()
            return True
        elif response == "kill-command":
            self._sa.send_signal(signal.SIGKILL.value)
            return True

    def finish_session(self, *args):
        print(self.C.header("Results"))
        if self.launcher.get_value("launcher", "local_submission"):
            # Disable SIGINT while we save local results
            with contextlib.ExitStack() as stack:
                tmp_sig = signal.signal(signal.SIGINT, signal.SIG_IGN)
                stack.callback(signal.signal, signal.SIGINT, tmp_sig)
                self._export_results()
        # let's see if any of the jobs failed, if so, let's return an error code of 1
        self._has_anything_failed = self.sa.has_any_job_failed()
        self.sa.finalize_session()
        return False

    def wait_and_continue(self, progress):
        print("Rejoined session.")
        print(
            "In progress: {} ({}/{})".format(
                progress[2], progress[0], progress[1]
            )
        )
        self.wait_for_job()
        self.run_interactable_jobs()

    def _handle_last_job_after_resume(self, resumed_session_info):
        if self.launcher.get_value("ui", "type") != "silent":
            resume_dialog(10)
        jobs_repr = json.loads(
            self.sa.get_jobs_repr([resumed_session_info["last_job"]])
        )
        job = jobs_repr[-1]
        SimpleUI.header(job["name"])
        print(_("ID: {0}").format(job["id"]))
        print(_("Category: {0}").format(job["category_name"]))
        SimpleUI.horiz_line()
        print(
            _("Outcome")
            + ": "
            + SimpleUI.C.result(self.sa.get_job_result(job["id"]))
        )

    def run_uninteractable_jobs(
        self, job_ids, step_name, starting_index=0, suppress_output=False
    ):
        """
        Runs the jobs in order and prints a UI that tracks the progression.

        This assumes all jobs are non-interactive jobs like during
        bootstrap
        """
        # we may start not from 0 because we are resuming
        total_jobs = len(job_ids)
        job_ids = job_ids[starting_index:]
        for job_no, job_id in enumerate(job_ids, start=starting_index):
            print(
                self.C.header(
                    _("{} {} ({}/{})").format(
                        step_name, job_id, job_no + 1, total_jobs, fill="-"
                    )
                )
            )
            self.sa.run_uninteractable_job(job_id)
            self.wait_for_job(suppress_output=suppress_output)

    def run_interactable_jobs(self, resumed_ongoing_session_info=None):
        """
        Runs the desired job list in normal mode (post bootstrap).
        """
        if (
            resumed_ongoing_session_info
            and resumed_ongoing_session_info["last_job"]
        ):
            self._handle_last_job_after_resume(resumed_ongoing_session_info)
        _logger.info("controller: Running jobs.")
        jobs = json.loads(self.sa.get_session_progress_json())
        _logger.debug(
            "controller: Jobs to be run:\n%s",
            "\n".join(["  " + job for job in jobs]),
        )
        total_num = len(jobs["done"]) + len(jobs["todo"])

        jobs_repr = json.loads(
            self.sa.get_jobs_repr_json(
                json.dumps(jobs["todo"]), len(jobs["done"])
            )
        )

        self._run_interactable_jobs(jobs_repr, total_num)
        rerun_candidates = self.sa.get_rerun_candidates("manual")
        if rerun_candidates:
            if self.launcher.get_value("ui", "type") == "interactive":
                while True:
                    if not self._maybe_manual_rerun_jobs():
                        break
        if self.launcher.get_value("ui", "auto_retry"):
            while True:
                if not self._maybe_auto_rerun_jobs():
                    break
        self.finish_session()

    def resume_interacting(self, interaction):
        self.sa.remember_users_response("rollback")
        self.run_interactable_jobs()

    def wait_for_job(self, dont_finish=False, suppress_output=False):
        _logger.info("controller: Waiting for job to finish.")
        polling_backoff = [0, 0.1, 0.2, 0.5]
        polling_i = 0
        while True:
            state, payload = self.sa.monitor_job()
            if payload and not suppress_output:
                polling_i = 0
                for line in payload.splitlines():
                    if line.startswith("stderr"):
                        SimpleUI.red_text(line[6:])
                    elif line.startswith("stdout"):
                        SimpleUI.green_text(line[6:])
                    else:
                        SimpleUI.black_text(line[6:])
            if state == "running":
                time.sleep(polling_backoff[polling_i])
                polling_i = min(polling_i + 1, len(polling_backoff) - 1)
                while True:
                    res = select.select([sys.stdin], [], [], 0)
                    if not res[0]:
                        break
                    # XXX: this assumes that sys.stdin is chunked in lines
                    buff = res[0][0].readline()
                    self.sa.transmit_input(buff)
                    if not buff:
                        break
            else:
                if dont_finish:
                    return
                self.finish_job()
                break

    def finish_job(self, result=None):
        _logger.info("controller: Finishing job with a result: %s", result)
        job_result = self.sa.finish_job(result)
        SimpleUI.horiz_line()
        print(_("Outcome") + ": " + SimpleUI.C.result(job_result))

    def abandon(self):
        _logger.info("controller: Abandoning session.")
        self.sa.finalize_session()

    def restart(self, *args):
        _logger.info("controller: Restarting session.")
        self.abandon()
        self.resume_or_start_new_session()

    def local_export(self, exporter_id, transport, options=()):
        _logger.info("controller: Exporting locally'")
        rf = self.sa.cache_report(exporter_id, options)
        exported_stream = SpooledTemporaryFile(max_size=102400, mode="w+b")
        chunk_size = 160 * 1024
        with tqdm(
            total=rf.tell(),
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            disable=not self.is_interactive,
        ) as pbar:
            rf.seek(0)
            while True:
                buf = rf.read(chunk_size)
                pbar.set_postfix(file=transport.url, refresh=False)
                pbar.update(chunk_size)
                if not buf:
                    break
                exported_stream.write(buf)
        exported_stream.seek(0)
        result = transport.send(exported_stream)
        return result

    def _maybe_auto_rerun_jobs(self):
        # create a list of jobs that qualify for rerunning
        rerun_candidates = self.sa.get_rerun_candidates("auto")
        # bail-out early if no job qualifies for rerunning
        if not rerun_candidates:
            return False
        # we wait before retrying
        delay = self.launcher.get_value("ui", "delay_before_retry")
        _logger.info(
            _(
                "Waiting {} seconds before retrying failed"
                " jobs...".format(delay)
            )
        )
        time.sleep(delay)
        # include resource jobs that jobs to retry depend on

        candidates = self.sa.prepare_rerun_candidates(rerun_candidates)
        self._run_interactable_jobs(
            json.loads(self.sa.get_jobs_repr(candidates)), len(candidates)
        )
        return True

    def _maybe_manual_rerun_jobs(self):
        rerun_candidates = self.sa.get_rerun_candidates("manual")
        if not rerun_candidates:
            return False
        test_info_list = json.loads(
            self.sa.get_jobs_repr([j.id for j in rerun_candidates])
        )
        wanted_set = ReRunBrowser(
            _("Select jobs to re-run"), test_info_list, rerun_candidates
        ).run()
        if not wanted_set:
            return False
        candidates = self.sa.prepare_rerun_candidates(
            [job for job in rerun_candidates if job.id in wanted_set]
        )
        self._run_interactable_jobs(
            json.loads(self.sa.get_jobs_repr(candidates)), len(candidates)
        )
        return True

    def _run_interactable_jobs(self, jobs_repr, total_num=0):
        for job in jobs_repr:
            job_state = self.sa.get_job_state(job["id"])
            # Note: job_state is a remote object, no need to json encode it
            self.sa.note_metadata_starting_job_json(json.dumps(job), job_state)
            SimpleUI.header(
                _("Running job {} / {}").format(
                    job["num"], total_num, fill="-"
                )
            )
            SimpleUI.header(job["name"])
            print(_("ID: {0}").format(job["id"]))
            print(_("Category: {0}").format(job["category_name"]))
            SimpleUI.horiz_line()
            next_job = False
            while next_job is False:
                for interaction in self.sa.run_job(job["id"]):
                    # interaction is a netref, cache attributes here
                    kind = interaction.kind
                    message = interaction.message
                    if kind == "purpose":
                        SimpleUI.description(_("Purpose:"), message)
                    elif kind == "description":
                        SimpleUI.description(_("Description:"), message)
                        if job["command"] is None:
                            cmd = "run"
                        else:
                            cmd = SimpleUI(None).wait_for_interaction_prompt(
                                None
                            )
                        if cmd == "skip":
                            next_job = True
                        elif cmd == "quit":
                            self.sa.remember_users_response(cmd)
                            raise SystemExit("Session paused by the user")
                        self.sa.remember_users_response(cmd)
                        self.wait_for_job(dont_finish=True)
                    elif kind in "steps":
                        SimpleUI.description(_("Steps:"), message)
                        if job["command"] is None:
                            cmd = "run"
                        else:
                            cmd = SimpleUI(None).wait_for_interaction_prompt(
                                None
                            )
                        if cmd == "skip":
                            next_job = True
                        elif cmd == "quit":
                            self.sa.remember_users_response(cmd)
                            raise SystemExit("Session paused by the user")
                        self.sa.remember_users_response(cmd)
                    elif kind == "verification":
                        self.wait_for_job(dont_finish=True)
                        if message:
                            SimpleUI.description(_("Verification:"), message)
                        JobAdapter = namedtuple("job_adapter", ["command"])
                        job_lite = JobAdapter(job["command"])
                        try:
                            cmd = SimpleUI(None)._interaction_callback(
                                job_lite, job_state, interaction.extra._builder
                            )
                            self.sa.remember_users_response(cmd)
                            self.finish_job(
                                interaction.extra._builder.get_result()
                            )
                            next_job = True
                            break
                        except ReRunJob:
                            next_job = False
                            self.sa.rerun_job(
                                job["id"],
                                interaction.extra._builder.get_result(),
                            )
                            break
                    elif kind == "comment":
                        new_comment = input(
                            SimpleUI.C.BLUE(
                                _("Please enter your comments:") + "\n"
                            )
                        )
                        self.sa.remember_users_response(new_comment + "\n")
                    elif kind == "skip":
                        if (
                            job_state.effective_certification_status
                            == "blocker"
                            and not isinstance(
                                interaction.extra._builder.comments, str
                            )
                        ):
                            print(
                                self.C.RED(
                                    _(
                                        "This job is required in order"
                                        " to issue a certificate."
                                    )
                                )
                            )
                            print(
                                self.C.RED(
                                    _(
                                        "Please add a comment to explain"
                                        " why you want to skip it."
                                    )
                                )
                            )
                            next_job = False
                            self.sa.rerun_job(
                                job["id"],
                                interaction.extra._builder.get_result(),
                            )
                            break
                        else:
                            self.finish_job(
                                interaction.extra._builder.get_result()
                            )
                            next_job = True
                            break
                else:
                    self.wait_for_job()
                    break
            if next_job:
                continue


def is_hostname_a_loopback(hostname):
    """
    Check if hostname is a loopback address
    """
    try:
        ip_address = ipaddress.ip_address(socket.gethostbyname(hostname))
    except socket.gaierror:
        return False
    return ip_address.is_loopback
