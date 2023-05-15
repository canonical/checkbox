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
This module contains implementation of the master end of the remote execution
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
from functools import partial
from tempfile import SpooledTemporaryFile

from plainbox.impl.color import Colorizer
from plainbox.impl.config import Configuration
from plainbox.impl.session.remote_assistant import RemoteSessionAssistant
from plainbox.vendor import rpyc
from checkbox_ng.urwid_ui import TestPlanBrowser
from checkbox_ng.urwid_ui import CategoryBrowser
from checkbox_ng.urwid_ui import ManifestBrowser
from checkbox_ng.urwid_ui import ReRunBrowser
from checkbox_ng.urwid_ui import interrupt_dialog
from checkbox_ng.urwid_ui import resume_dialog
from checkbox_ng.launcher.run import NormalUI, ReRunJob
from checkbox_ng.launcher.stages import MainLoopStage
from checkbox_ng.launcher.stages import ReportsStage
from tqdm import tqdm

_ = gettext.gettext
_logger = logging.getLogger("master")


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


class RemoteMaster(ReportsStage, MainLoopStage):
    """
    Control remote slave instance

    This class implements the part that presents UI to the operator and
    steers the session.
    """

    name = "remote-control"

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
    def sa(self):
        return self._sa

    def invoked(self, ctx):
        self._C = Colorizer()
        self._override_exporting(self.local_export)
        self._launcher_text = ""
        self._is_bootstrapping = False
        self._target_host = ctx.args.host
        self._normal_user = ""
        self._dry_run = ctx.args.dry_run
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
                self._launcher_text, "Remote:{}".format(expanded_path)
            )
        if ctx.args.user:
            self._normal_user = ctx.args.user
        timeout = 600
        deadline = time.time() + timeout
        port = ctx.args.port
        if not ipaddress.ip_address(ctx.args.host).is_loopback:
            print(
                _("Connecting to {}:{}. Timeout: {}s").format(
                    ctx.args.host, port, timeout
                )
            )
        while time.time() < deadline:
            try:
                self.connect_and_run(ctx.args.host, port)
                break
            except (ConnectionRefusedError, socket.timeout, OSError):
                print(".", end="", flush=True)
                time.sleep(1)
        else:
            print(_("\nConnection timed out."))

    def connect_and_run(self, host, port=18871):
        config = rpyc.core.protocol.DEFAULT_CONFIG.copy()
        config["allow_all_attrs"] = True
        config["sync_request_timeout"] = 120
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
        spinner = itertools.cycle('-\\|/')
        #  this tracks the disconnection time
        disconnection_time = 0
        while True:
            try:
                if interrupted:
                    _logger.info("remote: Session interrupted")
                    interrupted = False  # we are handling the interruption ATM
                    # next line can raise exception due to connection being
                    # lost so let's set the default behavior to quitting
                    keep_running = False
                    keep_running = self._handle_interrupt()
                    if not keep_running:
                        break
                conn = rpyc.connect(host, port, config=config)
                keep_running = True

                def quitter(msg):
                    # this will be called when the slave decides to disconnect
                    # this master
                    nonlocal server_msg
                    nonlocal keep_running
                    keep_running = False
                    server_msg = msg

                with contextlib.suppress(AttributeError):
                    # TODO: REMOTE_API
                    # when bumping the remote api make this bit obligatory
                    # i.e. remove the suppressing
                    conn.root.register_master_blaster(quitter)
                self._sa = conn.root.get_sa()
                self.sa.conn = conn
                # TODO: REMOTE API RAPI: Remove this API on the next RAPI bump
                # the check and bailout is not needed if the slave as up to
                # date as this master, so after bumping RAPI we can assume
                # that slave is always passwordless
                if not self.sa.passwordless_sudo:
                    raise SystemExit(
                        _(
                            "This version of Checkbox requires the service"
                            " to be run as root"
                        )
                    )
                try:
                    slave_api_version = self.sa.get_remote_api_version()
                except AttributeError:
                    raise SystemExit(
                        _(
                            "Service doesn't declare Remote API"
                            " version. Update Checkbox on the"
                            " SUT!"
                        )
                    )
                master_api_version = RemoteSessionAssistant.REMOTE_API_VERSION
                if slave_api_version != master_api_version:
                    raise SystemExit(
                        _(
                            "Remote API version mismatch. Service "
                            "uses: {}. Remote uses: {}"
                        ).format(slave_api_version, master_api_version)
                    )
                state, payload = self.sa.whats_up()
                _logger.info("remote: Main dispatch with state: %s", state)
                if printed_reconnecting and ever_disconnected:
                    print(
                        "...\nReconnected (took: {}s)".format(
                            int(time.time() - disconnection_time)
                        )
                    )
                    printed_reconnecting = False
                keep_running = {
                    "idle": self.new_session,
                    "running": self.wait_and_continue,
                    "finalizing": self.finish_session,
                    "testsselected": partial(
                        self.run_jobs, resumed_session_info=payload
                    ),
                    "bootstrapping": self.restart,
                    "bootstrapped": partial(
                        self.select_jobs, all_jobs=payload
                    ),
                    "started": self.restart,
                    "interacting": partial(
                        self.resume_interacting, interaction=payload
                    ),
                }[state]()
            except EOFError as exc:
                if keep_running:
                    print("Connection lost!")
                    # this is yucky but it works, in case of explicit
                    # connection closing by the slave we get this msg
                    _logger.info("remote: Connection lost due to: %s", exc)
                    if str(exc) == "stream has been closed":
                        print(
                            "Service explicitly disconnected you. Possible "
                            "reason: new remote connected to the service"
                        )
                        break
                    print(exc)
                    time.sleep(1)
                else:
                    # if keep_running got set to False it means that the
                    # network interruption was planned, AKA slave disconnected
                    # this master
                    print(server_msg)
                    break
            except (ConnectionRefusedError, socket.timeout, OSError) as exc:
                _logger.info("remote: Connection lost due to: %s", exc)
                if not keep_running:
                    raise
                # it's reconnecting, so we can ignore refuses
                if not printed_reconnecting:
                    print("Reconnecting ", end="")
                    disconnection_time = time.time()
                    ever_disconnected = True
                    printed_reconnecting = True
                print(next(spinner), end="\b", flush=True)
                time.sleep(.25)
            except KeyboardInterrupt:
                interrupted = True

            if not keep_running:
                break

    def new_session(self):
        _logger.info("remote: Starting new session.")
        configuration = dict()
        configuration["launcher"] = self._launcher_text
        configuration["normal_user"] = self._normal_user
        configuration["dry-run"] = self._dry_run

        try:
            tps = self.sa.start_session(configuration)
            if self.sa.sideloaded_providers:
                _logger.warning("Agent is using sideloaded providers")
        except RuntimeError as exc:
            raise SystemExit(exc.args[0]) from exc
        if self.launcher.get_value("test plan", "forced"):
            tp_unit = self.launcher.get_value("test plan", "unit")
            if not tp_unit:
                _logger.error(
                    _(
                        "The test plan selection was forced but no unit was provided"
                    )
                )
                raise SystemExit(1)
            self.select_tp(tp_unit)
            self.select_jobs(self.jobs)
        else:
            self.interactively_choose_tp(tps)

    def interactively_choose_tp(self, tps):
        _logger.info("remote: Interactively choosing TP.")
        tp_info_list = [{"id": tp[0], "name": tp[1]} for tp in tps]
        if not tp_info_list:
            _logger.error(_("There were no test plans to select from!"))
            raise SystemExit(0)
        selected_tp = TestPlanBrowser(
            _("Select test plan"),
            tp_info_list,
            self.launcher.get_value("test plan", "unit"),
        ).run()
        if selected_tp is None:
            print(_("Nothing selected"))
            raise SystemExit(0)

        self.select_tp(selected_tp)
        if not self.jobs:
            _logger.error(self.C.RED(_("There were no tests to select from!")))
            self.sa.finalize_session()
            return
        self.select_jobs(self.jobs)

    def select_tp(self, tp):
        _logger.info("remote: Selected test plan: %s", tp)
        try:
            self.sa.prepare_bootstrapping(tp)
        except KeyError as e:
            _logger.error('The test plan "%s" is not available!', tp)
            raise SystemExit(1)
        self._is_bootstrapping = True
        bs_todo = self.sa.get_bootstrapping_todo_list()
        for job_no, job_id in enumerate(bs_todo, start=1):
            print(
                self.C.header(
                    _("Bootstrap {} ({}/{})").format(
                        job_id, job_no, len(bs_todo), fill="-"
                    )
                )
            )
            self.sa.run_bootstrapping_job(job_id)
            self.wait_for_job()
        self._is_bootstrapping = False
        self.jobs = self.sa.finish_bootstrap()

    def _strtobool(self, val):
        return val.lower() in ("y", "yes", "t", "true", "on", "1")

    def _save_manifest(self, interactive):
        manifest_repr = self.sa.get_manifest_repr()
        if not manifest_repr:
            _logger.info("Skipping saving of the manifest")
            return
        if interactive:
            # Ask the user the values
            to_save_manifest = ManifestBrowser(
                "System Manifest:", manifest_repr
            ).run()
        else:
            # Use the one provided in repr
            # repr is question : [manifests]
            #   manifest ex m1 is [conf_m1_1, conf_m1_2, ...]
            # here we recover [conf_m1_1, conf_m1_2, ..., conf_m2_1, ...]
            all_preconf = (
                conf
                for conf_list in manifest_repr.values()
                for conf in conf_list
            )
            to_save_manifest = {
                conf["id"]: conf["value"] for conf in all_preconf
            }
        self.sa.save_manifest(to_save_manifest)

    def select_jobs(self, all_jobs):
        if self.launcher.get_value("test selection", "forced"):
            if self.launcher.manifest:
                self._save_manifest(interactive=False)
        else:
            _logger.info("remote: Selecting jobs.")
            reprs = json.loads(self.sa.get_jobs_repr(all_jobs))
            wanted_set = CategoryBrowser(
                "Choose tests to run on your system:", reprs
            ).run()
            # no need to set an alternate selection if the job list not changed
            if len(reprs) != len(wanted_set):
                # wanted_set may have bad order, let's use it as a filter to
                # the original list
                chosen_jobs = [job for job in all_jobs if job in wanted_set]
                _logger.debug("remote: Selected jobs: %s", chosen_jobs)
                self.sa.modify_todo_list(chosen_jobs)
            self._save_manifest(interactive=True)
        self.sa.finish_job_selection()
        self.run_jobs()

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
        parser.add_argument("-n", "--dry-run", default=False, action="store_true", help=_(
            "don't actually do anything"))

    def _handle_interrupt(self):
        """
        Returns True if the remote should keep running.
        And False if it should quit.
        """
        if self.launcher.get_value("ui", "type") == "silent":
            self._sa.terminate()
            return False
        response = interrupt_dialog(self._target_host)
        if response == "cancel":
            return True
        elif response == "kill-master":
            return False
        elif response == "kill-service":
            self._sa.terminate()
            return False
        elif response == "abandon":
            self._sa.finalize_session()
            return True
        elif response == "kill-command":
            self._sa.send_signal(signal.SIGKILL.value)
            return True

    def finish_session(self):
        print(self.C.header("Results"))
        if self.launcher.get_value("launcher", "local_submission"):
            # Disable SIGINT while we save local results
            with contextlib.ExitStack() as stack:
                tmp_sig = signal.signal(signal.SIGINT, signal.SIG_IGN)
                stack.callback(signal.signal, signal.SIGINT, tmp_sig)
                self._export_results()
        self.sa.finalize_session()
        return False

    def wait_and_continue(self):
        progress = self.sa.whats_up()[1]
        print("Rejoined session.")
        print(
            "In progress: {} ({}/{})".format(
                progress[2], progress[0], progress[1]
            )
        )
        self.wait_for_job()
        self.run_jobs()

    def _handle_last_job_after_resume(self, resumed_session_info):
        if self.launcher.get_value("ui", "type") == "silent":
            time.sleep(20)
        else:
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

    def run_jobs(self, resumed_session_info=None):
        if resumed_session_info and resumed_session_info["last_job"]:
            self._handle_last_job_after_resume(resumed_session_info)
        _logger.info("remote: Running jobs.")
        jobs = self.sa.get_session_progress()
        _logger.debug(
            "remote: Jobs to be run:\n%s",
            "\n".join(["  " + job for job in jobs]),
        )
        total_num = len(jobs["done"]) + len(jobs["todo"])

        jobs_repr = json.loads(
            self.sa.get_jobs_repr(jobs["todo"], len(jobs["done"]))
        )

        self._run_jobs(jobs_repr, total_num)
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
        self.run_jobs()

    def wait_for_job(self, dont_finish=False):
        _logger.info("remote: Waiting for job to finish.")
        while True:
            state, payload = self.sa.monitor_job()
            if payload and not self._is_bootstrapping:
                for line in payload.splitlines():
                    if line.startswith("stderr"):
                        SimpleUI.red_text(line[6:])
                    elif line.startswith("stdout"):
                        SimpleUI.green_text(line[6:])
                    else:
                        SimpleUI.black_text(line[6:])
            if state == "running":
                time.sleep(0.5)
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
        _logger.info("remote: Finishing job with a result: %s", result)
        job_result = self.sa.finish_job(result)
        if not self._is_bootstrapping:
            SimpleUI.horiz_line()
            print(_("Outcome") + ": " + SimpleUI.C.result(job_result))

    def abandon(self):
        _logger.info("remote: Abandoning session.")
        self.sa.finalize_session()

    def restart(self):
        _logger.info("remote: Restarting session.")
        self.abandon()
        self.new_session()

    def local_export(self, exporter_id, transport, options=()):
        _logger.info("remote: Exporting locally'")
        rf = self.sa.cache_report(exporter_id, options)
        exported_stream = SpooledTemporaryFile(max_size=102400, mode="w+b")
        chunk_size = 16384
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
        self._run_jobs(
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
        self._run_jobs(
            json.loads(self.sa.get_jobs_repr(candidates)), len(candidates)
        )
        return True

    def _run_jobs(self, jobs_repr, total_num=0):
        for job in jobs_repr:
            job_state = self.sa._sa.get_job_state(job["id"])
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
                    if interaction.kind == "purpose":
                        SimpleUI.description(
                            _("Purpose:"), interaction.message
                        )
                    elif interaction.kind == "description":
                        SimpleUI.description(
                            _("Description:"), interaction.message
                        )
                        if job["command"] is None:
                            cmd = "run"
                        else:
                            cmd = SimpleUI(None).wait_for_interaction_prompt(
                                None
                            )
                        if cmd == "skip":
                            next_job = True
                        self.sa.remember_users_response(cmd)
                        self.wait_for_job(dont_finish=True)
                    elif interaction.kind in "steps":
                        SimpleUI.description(_("Steps:"), interaction.message)
                        if job["command"] is None:
                            cmd = "run"
                        else:
                            cmd = SimpleUI(None).wait_for_interaction_prompt(
                                None
                            )
                        if cmd == "skip":
                            next_job = True
                        self.sa.remember_users_response(cmd)
                    elif interaction.kind == "verification":
                        self.wait_for_job(dont_finish=True)
                        if interaction.message:
                            SimpleUI.description(
                                _("Verification:"), interaction.message
                            )
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
                    elif interaction.kind == "comment":
                        new_comment = input(
                            SimpleUI.C.BLUE(
                                _("Please enter your comments:") + "\n"
                            )
                        )
                        self.sa.remember_users_response(new_comment + "\n")
                    elif interaction.kind == "skip":
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
