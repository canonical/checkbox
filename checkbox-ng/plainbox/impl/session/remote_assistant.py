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
import json
import gettext
import logging
import os
import queue
import time
import sys
from collections import namedtuple
from threading import Thread, Lock
from subprocess import DEVNULL, CalledProcessError, check_call

from plainbox.impl.ctrl import RootViaSudoWithPassExecutionController
from plainbox.impl.ctrl import UserJobExecutionController
from plainbox.impl.launcher import DefaultLauncherDefinition
from plainbox.impl.session.assistant import SessionAssistant
from plainbox.impl.session.assistant import SA_RESTARTABLE
from plainbox.impl.secure.sudo_broker import SudoBroker, EphemeralKey
from plainbox.impl.result import JobResultBuilder
from plainbox.impl.result import MemoryJobResult
from plainbox.abc import IJobResult

from checkbox_ng.launcher.run import SilentUI

_ = gettext.gettext

_logger = logging.getLogger("plainbox.session.assistant2")

Interaction = namedtuple('Interaction', ['kind', 'message', 'extra'])


class Interaction(namedtuple('Interaction', ['kind', 'message', 'extra'])):
    __slots__ = ()

    def __new__(cls, kind, message="", extra=None):
        return super(Interaction, cls).__new__(cls, kind, message, extra)

Idle = 'idle'
Started = 'started'
Bootstrapping = 'bootstrapping'
Bootstrapped = 'bootstrapped'
TestsSelected = 'testsselected'
Running = 'running'
Interacting = 'interacting'
Finalizing = 'finalizing'


class BufferedUI(SilentUI):
    """UI type that queues the output for later reading."""

    # XXX: using as string as a buffer and one lock over it
    #      might be a cleaner approach than those queues
    def __init__(self):
        super().__init__()
        self.clear_buffers()

    def got_program_output(self, stream_name, line):
        self._queue.put(line.decode(sys.stdout.encoding))
        self._whole_queue.put(line)

    def whole_output(self):
        """Returns all the output since last clear_buffers() call."""
        while not self._whole_queue.empty():
            self._whole_output += self._whole_queue.get()
        return self._whole_output

    def get_output(self):
        """Returns all the output queued up since previous call."""
        output = ''
        while not self._queue.empty():
            output += self._queue.get()
        return output

    def clear_buffers(self):
        self._queue = queue.Queue()
        self._whole_queue = queue.Queue()
        self._whole_output = ""


class BackgroundExecutor(Thread):
    def __init__(self, sa, job_id, real_run):
        super().__init__()
        self._sa = sa
        self._job_id = job_id
        self._real_run = real_run
        self._builder = None
        self._sa.session_change_lock.acquire()
        self.start()
        _logger.debug("BackgroundExecutor started for %s" % job_id)

    def wait(self):
        while self.is_alive():
            # return control to RPC server
            time.sleep(0.1)
        self.join()
        return self._builder

    def run(self):
        self._builder = self._real_run(
            self._job_id, self._sa.buffered_ui, False)
        _logger.debug("Finished running")

    def outcome(self):
        return self._builder.outcome


class RemoteSessionAssistant():
    """Remote execution enabling wrapper for the SessionAssistant"""

    REMOTE_API_VERSION = 1

    def __init__(self, cmd_callback):
        _logger.debug("__init__()")
        self._cmd_callback = cmd_callback
        self._sudo_broker = SudoBroker()
        self._sudo_password = None
        self._session_change_lock = Lock()
        self._operator_lock = Lock()
        self.buffered_ui = BufferedUI()
        self._reset_sa()
        self._passwordless_sudo = is_passwordless_sudo()
        self.terminate_cb = None

    def _reset_sa(self):
        self._state = Idle
        self._sa = SessionAssistant('service', api_flags={SA_RESTARTABLE})
        self._sa.configure_application_restart(self._cmd_callback)
        self._sa.use_alternate_execution_controllers([
            (
                RootViaSudoWithPassExecutionController,
                (),
                {'password_provider_cls': self.get_decrypted_password}
            ),
            (UserJobExecutionController, [], {}),
        ])
        self._be = None
        self._session_id = ""
        self._jobs_count = 0
        self._job_index = 0
        self._currently_running_job = None  # XXX: yuck!
        self._current_comments = ""
        self._last_response = None

    @property
    def session_change_lock(self):
        return self._session_change_lock

    def allowed_when(*states):
        def wrap(f):
            def fun(self, *args):
                if self._state not in states:
                    raise AssertionError(
                        "expected %s, is %s" % (states, self._state))
                return f(self, *args)
            return fun
        return wrap

    def interact(self, interaction):
        self._state = Interacting
        self._current_interaction = interaction
        yield self._current_interaction

    @allowed_when(Interacting)
    def remember_users_response(self, response):
        if response == 'rollback':
            self._currently_running_job = None
            self.session_change_lock.acquire(blocking=False)
            self.session_change_lock.release()
            self._current_comments = ""
            self._state = TestsSelected
            return
        self._last_response = response
        self._state = Running

    @allowed_when(Idle)
    def start_session(self, configuration):
        _logger.debug("start_session: %r", configuration)
        self._launcher = DefaultLauncherDefinition()
        if configuration['launcher']:
            self._launcher.read_string(configuration['launcher'])
        self._sa.use_alternate_configuration(self._launcher)
        self._sa.select_providers(*self._launcher.providers)
        self._sa.start_new_session('checkbox-service')
        self._session_id = self._sa.get_session_id()
        tps = self._sa.get_test_plans()
        response = zip(tps, [self._sa.get_test_plan(tp).name for tp in tps])
        self._state = Started
        self._available_testplans = sorted(
            response, key=lambda x: x[1])  # sorted by name
        return self._available_testplans

    @allowed_when(Started)
    def prepare_bootstrapping(self, test_plan_id):
        """
        Go through the list of bootstrapping jobs, and return True
        if sudo password will be needed for any bootstrapping job.
        """
        _logger.debug("prepare_bootstrapping: %r", test_plan_id)
        self._sa.update_app_blob(json.dumps(
            {'testplan_id': test_plan_id, }).encode("UTF-8"))
        self._sa.select_test_plan(test_plan_id)
        for job_id in self._sa.get_bootstrap_todo_list():
            job = self._sa.get_job(job_id)
            if job.user is not None:
                # job requires sudo controller
                return True
        return False

    @allowed_when(Started)
    def get_bootstrapping_todo_list(self):
        return self._sa.get_bootstrap_todo_list()

    def finish_bootstrap(self):
        self._sa.finish_bootstrap()
        self._jobs_count = len(self._sa.get_static_todo_list())
        self._state = Bootstrapped
        return self._sa.get_static_todo_list()

    def save_todo_list(self, chosen_jobs):
        self._sa.use_alternate_selection(chosen_jobs)
        self._state = TestsSelected

    @allowed_when(TestsSelected)
    def run_job(self, job_id):
        """
        Depending on the type of the job, run_job can yield different number
        of Interaction instances.
        """
        _logger.debug("run_job: %r", job_id)
        self._job_index = self._jobs_count - len(
            self._sa.get_dynamic_todo_list()) + 1
        self._currently_running_job = job_id
        self._current_comments = ""
        job = self._sa.get_job(job_id)
        if job.plugin in [
                'manual', 'user-interact-verify', 'user-interact']:
            may_comment = True
            while may_comment:
                may_comment = False
                if job.tr_description() and not job.tr_purpose():
                    yield from self.interact(
                        Interaction('description', job.tr_description()))
                if job.tr_purpose():
                    yield from self.interact(
                        Interaction('purpose', job.tr_purpose()))
                if job.tr_steps():
                    yield from self.interact(Interaction('steps', job.tr_steps()))
                if self._last_response == 'comment':
                    yield from self.interact(Interaction('comment'))
                    if self._last_response:
                        self._current_comments += self._last_response
                    may_comment = True
                    continue
            if self._last_response == 'skip':
                result_builder = JobResultBuilder(
                    outcome=IJobResult.OUTCOME_SKIP,
                    comments=_("Explicitly skipped before" " execution"))
                if self._current_comments != "":
                    result_builder.comments = self._current_comments
                self.finish_job(result_builder.get_result())
                return
        if job.command:
            if (job.user and not self._passwordless_sudo
                    and not self._sudo_password):
                self._ephemeral_key = EphemeralKey()
                self._current_interaction = Interaction(
                    'sudo_input', self._ephemeral_key.public_key)
                pass_is_correct = False
                while not pass_is_correct:
                    self.state = Interacting
                    yield self._current_interaction
                    pass_is_correct = validate_pass(
                        self._sudo_broker.decrypt_password(
                            self._sudo_password))
                assert(self._sudo_password is not None)
            self._state = Running
            self._be = BackgroundExecutor(self, job_id, self._sa.run_job)
        else:
            def undecided_builder(*args, **kwargs):
                return JobResultBuilder(outcome=IJobResult.OUTCOME_UNDECIDED)
            self._be = BackgroundExecutor(self, job_id, undecided_builder)
        if self._sa.get_job(self._currently_running_job).plugin in [
                'manual', 'user-interact-verify']:
            rb = self._be.wait()
            # by this point the ui will handle adding comments via
            # ResultBuilder.add_comment method that adds \n in front
            # of the addition, let's rstrip it
            rb.comments = self._current_comments.rstrip()
            yield from self.interact(
                Interaction('verification', job.verification, rb))
            self.finish_job(rb.get_result())

    @allowed_when(Started, Bootstrapping)
    def run_bootstrapping_job(self, job_id):
        self._currently_running_job = job_id
        self._state = Bootstrapping
        self._be = BackgroundExecutor(self, job_id, self._sa.run_job)

    @allowed_when(Running, Bootstrapping, Interacting)
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
            return ('running', self.buffered_ui.get_output())
        else:
            return ('done', self.buffered_ui.get_output())
        return 'running' if self._be.is_alive() else 'done'

    def get_remote_api_version(self):
        return self.REMOTE_API_VERSION

    def whats_up(self):
        """
        Check what is remote-service up to
        :returns:
            (state, payload) tuple.
        """
        _logger.debug("whats_up()")
        payload = None
        if self._state == Running:
            payload = (
                self._job_index, self._jobs_count, self._currently_running_job
            )
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
            "done": [],
            "todo": self._sa.get_dynamic_todo_list(),
        }

    def get_master_public_key(self):
        """Expose the master public key"""
        return self._sudo_broker.master_public

    def save_password(self, cyphertext):
        """Store encrypted password"""
        if validate_pass(self._sudo_broker.decrypt_password(cyphertext)):
            self._sudo_password = cyphertext
            return True
        return False

    def get_decrypted_password(self):
        """Return decrypted password"""
        if self._passwordless_sudo:
            return ''
        assert(self._sudo_password)
        return self._sudo_broker.decrypt_password(self._sudo_password)

    def finish_job(self, result=None):
        # assert the thread completed
        self.session_change_lock.acquire(blocking=False)
        self._session_change_lock.release()
        if self._sa.get_job(self._currently_running_job).plugin in [
                'manual', 'user-interact-verify'] and not result:
            # for manually verified jobs we don't set the outcome here
            # it is already determined
            return
        if not result:
            result = self._be.wait().get_result()
        self._sa.use_job_result(self._currently_running_job, result)
        if self._state != Bootstrapping:
            if not self._sa.get_dynamic_todo_list():
                self._state = Idle
            else:
                self._state = TestsSelected

    def get_jobs_repr(self, job_ids):
        """
        Translate jobs into a {'field': 'val'} representations.

        :param job_ids:
            list of job ids to get and translate
        :returns:
            list of dicts representing jobs
        """
        test_info_list = tuple()
        for job_id in job_ids:
            job = self._sa.get_job(job_id)
            cat_id = self._sa.get_job_state(job.id).effective_category_id
            duration_txt = _('No estimated duration provided for this job')
            if job.estimated_duration is not None:
                duration_txt = '{} {}'.format(job.estimated_duration, _(
                    'seconds'))
            # the next dict is only to get test_info generating code tidier
            automated_desc = {
                True: _('this job is fully automated'),
                False: _('this job requires some manual interaction')
            }
            test_info = {
                "id": job.id,
                "partial_id": job.partial_id,
                "name": job.tr_summary(),
                "category_id": cat_id,
                "category_name": self._sa.get_category(cat_id).tr_name(),
                "automated": automated_desc[job.automated],
                "duration": duration_txt,
                "description": (job.tr_description() or
                                _('No description provided for this job')),
                "outcome": self._sa.get_job_state(job.id).result.outcome,
                "user": job.user,
                "command": job.command,
            }
            test_info_list = test_info_list + ((test_info, ))
        return test_info_list

    def resume_last(self):
        last = next(self._sa.get_resumable_sessions())
        meta = self._sa.resume_session(last.id)
        app_blob = json.loads(meta.app_blob.decode("UTF-8"))
        test_plan_id = app_blob['testplan_id']
        self._sa.select_test_plan(test_plan_id)
        self._sa.bootstrap()
        result = MemoryJobResult({
            'outcome': IJobResult.OUTCOME_PASS,
            'comments': _("Passed after resuming execution")
        })
        last_job = meta.running_job_name
        if last_job:
            try:
                self._sa.use_job_result(last_job, result)
            except KeyError:
                raise SystemExit(last_job)
        self._state = TestsSelected

    def finalize_session(self):
        self._sa.finalize_session()
        self._reset_sa()

    @property
    def manager(self):
        return self._sa._manager

    @property
    def passwordless_sudo(self):
        return self._passwordless_sudo


def is_passwordless_sudo():
    """
    Check if system can run sudo without pass.
    """
    # running sudo with -A will try using ASKPASS envvar that should specify
    # the program to use when asking for password
    # If the system is configured to not ask for password, this will silently
    # succeed. If the pass is required, it'll return 1 and not ask for pass,
    # as the askpass program is not provided
    try:
        check_call(['sudo', '-A', 'true'], stdout=DEVNULL, stderr=DEVNULL)
    except CalledProcessError:
        return False
    return True


def validate_pass(password):
    cmd = ['sudo', '--prompt=', '--reset-timestamp', '--stdin',
           '--user', 'root', 'true']
    r, w = os.pipe()
    os.write(w, (password + "\n").encode('utf-8'))
    os.close(w)
    try:
        check_call(cmd, stdin=r, stdout=DEVNULL, stderr=DEVNULL)
        return True
    except CalledProcessError:
        return False
