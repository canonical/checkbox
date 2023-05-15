# This file is part of Checkbox.
#
# Copyright 2018 Canonical Ltd.
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
import fnmatch
import io
import json
import gettext
import logging
import os
import pwd
import time
from collections import namedtuple
from contextlib import suppress
from tempfile import SpooledTemporaryFile
from threading import Thread, Lock
from plainbox.impl.config import Configuration
from plainbox.impl.execution import UnifiedRunner
from plainbox.impl.session.assistant import SessionAssistant
from plainbox.impl.session.assistant import SA_RESTARTABLE
from plainbox.impl.session.jobs import InhibitionCause
from plainbox.impl.session.storage import WellKnownDirsHelper
from plainbox.impl.secure.sudo_broker import is_passwordless_sudo
from plainbox.impl.result import JobResultBuilder
from plainbox.impl.result import MemoryJobResult
from plainbox.abc import IJobResult

from checkbox_ng.config import load_configs
from checkbox_ng.launcher.run import SilentUI
from checkbox_ng.user_utils import check_user_exists
from checkbox_ng.user_utils import guess_normal_user


import psutil

_ = gettext.gettext

_logger = logging.getLogger("plainbox.session.remote_assistant")

Interaction = namedtuple("Interaction", ["kind", "message", "extra"])


class Interaction(namedtuple("Interaction", ["kind", "message", "extra"])):
    __slots__ = ()

    def __new__(cls, kind, message="", extra=None):
        return super(Interaction, cls).__new__(cls, kind, message, extra)


Idle = "idle"
Started = "started"
Bootstrapping = "bootstrapping"
Bootstrapped = "bootstrapped"
TestsSelected = "testsselected"
Running = "running"
Interacting = "interacting"
Finalizing = "finalizing"


class BufferedUI(SilentUI):
    """UI type that queues the output for later reading."""

    def __init__(self):
        super().__init__()
        self.lock = Lock()
        self._output = io.StringIO()

    def _ignore_program_output(self, stream_name, line):
        pass

    def got_program_output(self, stream_name, line):
        with self.lock:
            try:
                self._output.write(stream_name + line.decode("UTF-8"))
            except UnicodeDecodeError:
                # Don't start a slave->master transfer for binary attachments
                self._output.write("hidden(Hiding binary test output)\n")
                self.got_program_output = self._ignore_program_output

    def get_output(self):
        """Returns all the output queued up since previous call."""
        with self.lock:
            output = self._output.getvalue()
            self._output = io.StringIO()
            return output


class RemoteSilentUI(SilentUI):
    """SilentUI + fake get_output."""

    def __init__(self):
        super().__init__()
        self._msg = "hidden(Command output hidden)"

    def get_output(self):
        msg = self._msg
        self._msg = ""
        return msg


class BackgroundExecutor(Thread):
    def __init__(self, sa, job_id, real_run, ui=RemoteSilentUI()):
        super().__init__()
        self._sa = sa
        self._job_id = job_id
        self._real_run = real_run
        self._ui = ui
        self._builder = None
        self._started_real_run = False
        self._sa.session_change_lock.acquire()
        self.start()
        _logger.debug("BackgroundExecutor started for %s" % job_id)

    def wait(self):
        while self.is_alive() or not self._started_real_run:
            # return control to RPC server
            time.sleep(0.1)
        self.join()
        return self._builder

    def run(self):
        self._started_real_run = True
        self._builder = self._real_run(self._job_id, self._ui, False)
        _logger.debug("Finished running")

    def outcome(self):
        return self._builder.outcome


class RemoteSessionAssistant:
    """Remote execution enabling wrapper for the SessionAssistant"""

    REMOTE_API_VERSION = 12

    def __init__(self, cmd_callback):
        _logger.debug("__init__()")
        self._cmd_callback = cmd_callback
        self._session_change_lock = Lock()
        self._operator_lock = Lock()
        self._ui = BufferedUI()
        self._input_piping = os.pipe()
        self._passwordless_sudo = is_passwordless_sudo()
        self.terminate_cb = None
        self._pipe_from_master = open(self._input_piping[1], "w")
        self._pipe_to_subproc = open(self._input_piping[0])
        self._reset_sa()
        self._currently_running_job = None

    def _reset_sa(self):
        _logger.info("Resetting RSA")
        self._state = Idle
        self._sa = SessionAssistant("service", api_flags={SA_RESTARTABLE})
        self._be = None
        self._session_id = ""
        self._jobs_count = 0
        self._job_index = 0
        self._currently_running_job = None  # XXX: yuck!
        self._last_job = None
        self._current_comments = ""
        self._last_response = None
        self._normal_user = ""
        self.session_change_lock.acquire(blocking=False)
        self.session_change_lock.release()

    @property
    def session_change_lock(self):
        return self._session_change_lock

    @property
    def config(self):
        return self._sa.config

    def update_app_blob(self, app_blob):
        self._sa.update_app_blob(app_blob)

    def allowed_when(*states):
        def wrap(f):
            def fun(self, *args):
                if self._state not in states:
                    raise AssertionError(
                        "expected %s, is %s" % (states, self._state)
                    )
                return f(self, *args)

            return fun

        return wrap

    def interact(self, interaction):
        self._state = Interacting
        self._current_interaction = interaction
        yield self._current_interaction

    @allowed_when(Interacting)
    def remember_users_response(self, response):
        if response == "rollback":
            self._currently_running_job = None
            self.session_change_lock.acquire(blocking=False)
            self.session_change_lock.release()
            self._current_comments = ""
            self._state = TestsSelected
            return
        self._last_response = response
        self._state = Running

    def _set_envvar_from_proc(self, name):
        for path in os.listdir("/proc/"):
            with suppress(Exception):
                env = (
                    open(os.path.join("/proc/", path, "environ"))
                    .read()
                    .split("\0")
                )
                for key, val in [item.split("=") for item in env]:
                    if key == name:
                        return val
        return ""

    def _prepare_display_without_psutil(self):
        uid = pwd.getpwnam(self._normal_user).pw_uid
        return {
            "DISPLAY": self._set_envvar_from_proc("DISPLAY"),
            "WAYLAND_DISPLAY": self._set_envvar_from_proc("WAYLAND_DISPLAY"),
            "XAUTHORITY": self._set_envvar_from_proc("XAUTHORITY"),
            "XDG_SESSION_TYPE": self._set_envvar_from_proc("XDG_SESSION_TYPE"),
            "XDG_RUNTIME_DIR": "/run/user/{}".format(uid),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/{}/bus".format(
                uid
            ),
        }

    def prepare_extra_env(self):
        extra_env = {}
        # If possible also set the DISPLAY env var
        # i.e when a user desktop session is running
        for p in psutil.pids():
            try:
                p_environ = psutil.Process(p).environ()
                p_user = psutil.Process(p).username()
            except psutil.AccessDenied:
                continue
            except AttributeError:
                # psutil < 4.0.0 doesn't provide Process.environ()
                return self._prepare_display_without_psutil()
            except psutil.NoSuchProcess:
                # quietly ignore the process that died before we had a chance
                # to read the environment from them
                continue
            if (
                "DISPLAY" in p_environ
                and "XAUTHORITY" in p_environ
                and "XDG_SESSION_TYPE" in p_environ
                and p_user != "gdm"
            ):  # gdm uses :1024
                uid = pwd.getpwnam(self._normal_user).pw_uid
                extra_env["DISPLAY"] = p_environ["DISPLAY"]
                extra_env["XAUTHORITY"] = p_environ["XAUTHORITY"]
                extra_env["XDG_SESSION_TYPE"] = p_environ["XDG_SESSION_TYPE"]
                extra_env["XDG_RUNTIME_DIR"] = "/run/user/{}".format(uid)
                extra_env[
                    "DBUS_SESSION_BUS_ADDRESS"
                ] = "unix:path=/run/user/{}/bus".format(uid)
            if "WAYLAND_DISPLAY" in p_environ:
                extra_env["WAYLAND_DISPLAY"] = p_environ["WAYLAND_DISPLAY"]

        return extra_env

    @allowed_when(Idle)
    def start_session(self, configuration):
        self._reset_sa()
        _logger.info("start_session: %r", configuration)
        session_title = "remote"
        session_desc = "remote session"
        session_type = "remote"

        self._launcher = load_configs()
        if configuration["launcher"]:
            launcher_from_controller = Configuration.from_text(
                configuration["launcher"], "Remote launcher"
            )
            self._launcher.update_from_another(
                launcher_from_controller, "Remote launcher")
            session_title = (
                self._launcher.get_value("launcher", "session_title")
                or session_title
            )
            session_desc = (
                self._launcher.get_value("launcher", "session_desc")
                or session_desc
            )

        self._sa.use_alternate_configuration(self._launcher)
        self._normal_user = self._launcher.get_value("daemon", "normal_user")
        if self._normal_user:
            if not check_user_exists(self._normal_user):
                raise RuntimeError(
                    "User '{}' doesn't exist!".format(self._normal_user)
                )
        else:
            self._normal_user = guess_normal_user()
        runner_kwargs = {
            "dry_run" : configuration.get("dry-run", False),
            "normal_user_provider": lambda: self._normal_user,
            "stdin": self._pipe_to_subproc,
            "extra_env": self.prepare_extra_env,
        }
        self._sa.start_new_session(session_title, UnifiedRunner, runner_kwargs)
        new_blob = json.dumps(
            {
                "description": session_desc,
                "type": session_type,
                "launcher": configuration["launcher"],
                "effective_normal_user": self._normal_user,
            }
        ).encode("UTF-8")
        self._sa.update_app_blob(new_blob)
        self._sa.configure_application_restart(self._cmd_callback)

        self._session_id = self._sa.get_session_id()
        tps = self._sa.get_test_plans()
        filtered_tps = set()
        for filter in self._launcher.get_value("test plan", "filter"):
            filtered_tps.update(fnmatch.filter(tps, filter))
        filtered_tps = list(filtered_tps)
        response = zip(
            filtered_tps,
            [self._sa.get_test_plan(tp).name for tp in filtered_tps],
        )
        self._state = Started
        self._available_testplans = sorted(
            response, key=lambda x: x[1]
        )  # sorted by name
        return self._available_testplans

    @allowed_when(Started)
    def prepare_bootstrapping(self, test_plan_id):
        """Save picked test plan to the app blob."""
        _logger.debug("prepare_bootstrapping: %r", test_plan_id)
        self._sa.update_app_blob(
            json.dumps(
                {
                    "testplan_id": test_plan_id,
                }
            ).encode("UTF-8")
        )
        self._sa.select_test_plan(test_plan_id)
        # TODO: REMOTE API RAPI: Change this API on the next RAPI bump
        # previously the function returned bool signifying the need for sudo
        # password. With slave being guaranteed to never need it anymor
        # we can make this funciton return nothing
        return False

    @allowed_when(Started)
    def get_bootstrapping_todo_list(self):
        return self._sa.get_bootstrap_todo_list()

    def finish_bootstrap(self):
        self._sa.finish_bootstrap()
        self._state = Bootstrapped
        if self._launcher.get_value("ui", "auto_retry"):
            for job_id in self._sa.get_static_todo_list():
                job_state = self._sa.get_job_state(job_id)
                job_state.attempts = self._launcher.get_value(
                    "ui", "max_attempts"
                )
        return self._sa.get_static_todo_list()

    def get_manifest_repr(self):
        return self._sa.get_manifest_repr()

    def save_manifest(self, manifest_answers):
        return self._sa.save_manifest(manifest_answers)

    def modify_todo_list(self, chosen_jobs):
        self._sa.use_alternate_selection(chosen_jobs)

    def finish_job_selection(self):
        self._jobs_count = len(self._sa.get_dynamic_todo_list())
        self._state = TestsSelected

    @allowed_when(Interacting)
    def rerun_job(self, job_id, result):
        self._sa.use_job_result(job_id, result)
        self.session_change_lock.acquire(blocking=False)
        self.session_change_lock.release()
        self._state = TestsSelected

    def _get_ui_for_job(self, job):
        show_out = True
        if (
            self._launcher.get_value("ui", "output")
            == "hide-resource-and-attachment"
        ):
            if job.plugin in ("local", "resource", "attachment"):
                show_out = False
        elif self._launcher.get_value("ui", "output") in [
            "hide",
            "hide-automated",
        ]:
            if job.plugin in ("shell", "local", "resource", "attachment"):
                show_out = False
        if "suppress-output" in job.get_flag_set():
            show_out = False
        if show_out:
            self._ui = BufferedUI()
        else:
            self._ui = RemoteSilentUI()
        return self._ui

    @allowed_when(TestsSelected)
    def run_job(self, job_id):
        """
        Depending on the type of the job, run_job can yield different number
        of Interaction instances.
        """
        _logger.debug("run_job: %r", job_id)
        self._job_index = (
            self._jobs_count - len(self._sa.get_dynamic_todo_list()) + 1
        )
        self._currently_running_job = job_id
        self._current_comments = ""
        job = self._sa.get_job(job_id)
        job_state = self._sa.get_job_state(job_id)

        if not job_state.can_start():
            outcome = IJobResult.OUTCOME_NOT_SUPPORTED
            for inhibitor in job_state.readiness_inhibitor_list:
                if (
                    inhibitor.cause == InhibitionCause.FAILED_RESOURCE
                    and "fail-on-resource" in job.get_flag_set()
                ):
                    outcome = IJobResult.OUTCOME_FAIL
                    break
                elif inhibitor.cause != InhibitionCause.FAILED_DEP:
                    continue
                related_job_state = self._sa._context.state.job_state_map[
                    inhibitor.related_job.id
                ]
                if related_job_state.result.outcome == IJobResult.OUTCOME_SKIP:
                    outcome = IJobResult.OUTCOME_SKIP

            def cant_start_builder(*args, **kwargs):
                result_builder = JobResultBuilder(
                    outcome=outcome,
                    comments=job_state.get_readiness_description(),
                )
                return result_builder

            self._be = BackgroundExecutor(self, job_id, cant_start_builder)
            yield from self.interact(Interaction("skip", None, self._be))

        if job.plugin in ["manual", "user-interact-verify", "user-interact"]:
            may_comment = True
            while may_comment:
                may_comment = False
                if job.tr_description() and not job.tr_purpose():
                    yield from self.interact(
                        Interaction("description", job.tr_description())
                    )
                if job.tr_purpose():
                    yield from self.interact(
                        Interaction("purpose", job.tr_purpose())
                    )
                if job.tr_steps():
                    yield from self.interact(
                        Interaction("steps", job.tr_steps())
                    )
                if self._last_response == "comment":
                    yield from self.interact(Interaction("comment"))
                    if self._last_response:
                        self._current_comments += self._last_response
                    may_comment = True
                    continue
            if self._last_response == "skip":

                def skipped_builder(*args, **kwargs):
                    result_builder = JobResultBuilder(
                        outcome=IJobResult.OUTCOME_SKIP
                    )
                    if self._current_comments != "":
                        result_builder.comments = self._current_comments
                    elif job_state.effective_certification_status != "blocker":
                        result_builder.comments = (
                            "Explicitly skipped before execution"
                        )
                    return result_builder

                self._be = BackgroundExecutor(self, job_id, skipped_builder)
                yield from self.interact(
                    Interaction("skip", job.verification, self._be)
                )
        if job.command:
            self._state = Running
            ui = self._get_ui_for_job(job)
            self._be = BackgroundExecutor(self, job_id, self._sa.run_job, ui)
        else:

            def undecided_builder(*args, **kwargs):
                return JobResultBuilder(outcome=IJobResult.OUTCOME_UNDECIDED)

            self._be = BackgroundExecutor(self, job_id, undecided_builder)
        if self._sa.get_job(self._currently_running_job).plugin in [
            "manual",
            "user-interact-verify",
        ]:
            yield from self.interact(
                Interaction("verification", job.verification, self._be)
            )

    @allowed_when(Started, Bootstrapping)
    def run_bootstrapping_job(self, job_id):
        self._currently_running_job = job_id
        self._state = Bootstrapping
        self._be = BackgroundExecutor(self, job_id, self._sa.run_job)

    @allowed_when(Running, Bootstrapping, Interacting, TestsSelected)
    def monitor_job(self):
        """
        Check the state of the currently running job.

        :returns:
            (state, payload) tuple.
            Payload conveys detailed info that's characteristic
            to the current state.
        """
        _logger.debug("monitor_job()")
        # either return [done, running, awaiting response]
        # TODO: handle awaiting_response (reading from stdin by the job)
        if self._be and self._be.is_alive():
            return ("running", self._ui.get_output())
        else:
            return ("done", self._ui.get_output())

    def get_remote_api_version(self):
        return self.REMOTE_API_VERSION

    def whats_up(self):
        """
        Check what is remote-service up to
        :returns:
            (state, payload) tuple.
        """
        _logger.debug("whats_up() -> %r", self._state)
        payload = None
        if self._state == Running:
            payload = (
                self._job_index,
                self._jobs_count,
                self._currently_running_job,
            )
        if self._state == TestsSelected and not self._currently_running_job:
            payload = {"last_job": self._last_job}
        elif self._state == Started:
            payload = self._available_testplans
        elif self._state == Interacting:
            payload = self._current_interaction
        elif self._state == Bootstrapped:
            payload = self._sa.get_static_todo_list()
        return self._state, payload

    def terminate(self):
        if self.terminate_cb:
            self.terminate_cb()

    def get_session_progress(self):
        """Return list of completed and not completed jobs in a dict."""

        _logger.debug("get_session_progress()")
        return {
            "done": self._sa.get_dynamic_done_list(),
            "todo": self._sa.get_dynamic_todo_list(),
        }

    def finish_job(self, result=None):
        # assert the thread completed
        self.session_change_lock.acquire(blocking=False)
        self.session_change_lock.release()
        if (
            self._sa.get_job(self._currently_running_job).plugin
            in ["manual", "user-interact-verify"]
            and not result
        ):
            # for manually verified jobs we don't set the outcome here
            # it is already determined
            return
        if not result:
            result = self._be.wait().get_result()
        self._sa.use_job_result(self._currently_running_job, result)
        if self._state != Bootstrapping:
            if not self._sa.get_dynamic_todo_list():
                if self._launcher.get_value(
                    "ui", "auto_retry"
                ) and self.get_rerun_candidates("auto"):
                    self._state = TestsSelected
                else:
                    self._state = Idle
            else:
                self._state = TestsSelected
        return result

    def get_rerun_candidates(self, session_type="manual"):
        return self._sa.get_rerun_candidates(session_type)

    def prepare_rerun_candidates(self, rerun_candidates):
        candidates = self._sa.prepare_rerun_candidates(rerun_candidates)
        self._state = TestsSelected
        return candidates

    def get_job_result(self, job_id):
        return self._sa.get_job_state(job_id).result

    def get_jobs_repr(self, job_ids, offset=0):
        """
        Translate jobs into a {'field': 'val'} representations.

        :param job_ids:
            list of job ids to get and translate
        :param offset:
            apply an offset to the job number if for instance the job list
            is being requested part way through a session
        :returns:
            list of dicts representing jobs
        """
        test_info_list = tuple()
        for job_no, job_id in enumerate(job_ids, start=offset + 1):
            job = self._sa.get_job(job_id)
            cat_id = self._sa.get_job_state(job.id).effective_category_id
            duration_txt = _("No estimated duration provided for this job")
            if job.estimated_duration is not None:
                duration_txt = "{} {}".format(
                    job.estimated_duration, _("seconds")
                )
            # the next dict is only to get test_info generating code tidier
            automated_desc = {
                True: _("this job is fully automated"),
                False: _("this job requires some manual interaction"),
            }
            test_info = {
                "id": job.id,
                "partial_id": job.partial_id,
                "name": job.tr_summary(),
                "category_id": cat_id,
                "category_name": self._sa.get_category(cat_id).tr_name(),
                "automated": automated_desc[job.automated],
                "duration": duration_txt,
                "description": (
                    job.tr_description()
                    or _("No description provided for this job")
                ),
                "outcome": self._sa.get_job_state(job.id).result.outcome,
                "user": job.user,
                "command": job.command,
                "num": job_no,
                "plugin": job.plugin,
            }
            test_info_list = test_info_list + ((test_info,))
        return json.dumps(test_info_list)

    def resume_by_id(self, session_id=None):
        _logger.info("resume_by_id: %r", session_id)
        self._launcher = load_configs()
        resume_candidates = list(self._sa.get_resumable_sessions())
        if not session_id:
            if not resume_candidates:
                print("No session to resume")
                return
            session_id = resume_candidates[0].id
        if session_id not in [s.id for s in resume_candidates]:
            print("Requested session not found")
            return
        _logger.warning("Resuming session: %r", session_id)
        runner_kwargs = {
            "normal_user_provider": lambda: self._normal_user,
            "stdin": self._pipe_to_subproc,
            "extra_env": self.prepare_extra_env,
        }
        meta = self._sa.resume_session(session_id, runner_kwargs=runner_kwargs)
        app_blob = json.loads(meta.app_blob.decode("UTF-8"))
        launcher = app_blob["launcher"]
        launcher_from_controller = Configuration.from_text(
            app_blob["launcher"], "Remote launcher"
        )
        self._launcher.update_from_another(
            launcher_from_controller, "Remote launcher")
        self._sa.use_alternate_configuration(self._launcher)

        self._normal_user = app_blob.get(
            "effective_normal_user",
            self._launcher.get_value("daemon", "normal_user"),
        )
        _logger.info(
            "normal_user after loading metadata: %r", self._normal_user
        )
        test_plan_id = app_blob["testplan_id"]
        self._sa.select_test_plan(test_plan_id)
        self._sa.bootstrap()
        self._last_job = meta.running_job_name

        result_dict = {
            "outcome": IJobResult.OUTCOME_PASS,
            "comments": _("Automatically passed after resuming execution"),
        }
        session_share = WellKnownDirsHelper.session_share(
            self._sa._manager.storage.id
        )
        result_path = os.path.join(session_share, "__result")
        if os.path.exists(result_path):
            try:
                with open(result_path, "rt") as f:
                    result_dict = json.load(f)
                    # the only really important field in the result is
                    # 'outcome' so let's make sure it doesn't contain
                    # anything stupid
                    if result_dict.get("outcome") not in [
                        "pass",
                        "fail",
                        "skip",
                    ]:
                        result_dict["outcome"] = IJobResult.OUTCOME_PASS
            except json.JSONDecodeError:
                pass
        result = MemoryJobResult(result_dict)
        if self._last_job:
            try:
                self._sa.use_job_result(self._last_job, result, True)
            except KeyError:
                raise SystemExit(self._last_job)

        # some jobs have already been run, so we need to update the attempts
        # count for future auto-rerunning
        if self._launcher.get_value("ui", "auto_retry"):
            for job_id in [
                job.id for job in self.get_rerun_candidates("auto")
            ]:
                job_state = self._sa.get_job_state(job_id)
                job_state.attempts = self._launcher.get_value(
                    "ui", "max_attempts"
                ) - len(job_state.result_history)

        self._state = TestsSelected

    def finalize_session(self):
        self._sa.finalize_session()
        self._reset_sa()

    def transmit_input(self, text):
        if not text:
            self._pipe_from_master.close()
            return
        self._pipe_from_master.write(text)
        self._pipe_from_master.flush()

    def send_signal(self, signal):
        if not self._currently_running_job:
            return
        target_user = self._sa.get_job(self._currently_running_job).user
        self._sa.send_signal(signal, target_user)

    @property
    def manager(self):
        return self._sa._manager

    @property
    def passwordless_sudo(self):
        # TODO: REMOTE API RAPI: Remove this API on the next RAPI bump
        # if the slave is still running it means it's very passwordless
        return True

    @property
    def sideloaded_providers(self):
        return self._sa.sideloaded_providers

    def exposed_cache_report(self, exporter_id, options):
        exporter = self._sa._manager.create_exporter(exporter_id, options)
        exported_stream = SpooledTemporaryFile(max_size=102400, mode="w+b")
        exporter.dump_from_session_manager(self._sa._manager, exported_stream)
        exported_stream.flush()
        return exported_stream
