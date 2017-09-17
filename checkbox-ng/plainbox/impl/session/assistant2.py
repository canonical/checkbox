# This file is part of Checkbox.
#
# Copyright 2017 Canonical Ltd.
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
import queue
import time
import sys
from collections import namedtuple
from threading import Thread, Lock

from plainbox.impl.ctrl import RootViaSudoWithPassExecutionController
from plainbox.impl.ctrl import UserJobExecutionController
from plainbox.impl.session.assistant import SessionAssistant
from plainbox.impl.session.assistant import SA_RESTARTABLE
from plainbox.impl.secure.sudo_broker import SudoBroker, EphemeralKey
from plainbox.impl.commands.inv_run import SilentUI
from plainbox.impl.result import MemoryJobResult
from plainbox.abc import IJobResult

_ = gettext.gettext

_logger = logging.getLogger("plainbox.session.assistant2")

Interaction = namedtuple('Interaction', ['kind', 'message'])

Idle = 'idle'
Started = 'started'
Bootstrapping = 'bootstrapping'
Bootstrapped = 'bootstrapped'
Running = 'running'
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


class SessionAssistant2():
    """Remote execution enabling wrapper for the SessionAssistant"""
    # TODO: the name?

    def __init__(self, cmd_callback):
        _logger.debug("__init__()")
        self._state = Idle
        self._sa = SessionAssistant('service', api_flags={SA_RESTARTABLE})
        self._sa.configure_application_restart(cmd_callback)
        self._sudo_broker = SudoBroker()
        self._sudo_password = None
        self._sa.use_alternate_execution_controllers([
            (
                RootViaSudoWithPassExecutionController,
                (),
                {'password_provider_cls': self.get_decrypted_password}
            ),
            (UserJobExecutionController, [], {}),
        ])
        self._sa.select_providers('*')
        self._session_change_lock = Lock()
        self._operator_lock = Lock()
        self._be = None
        self._session_id = ""
        self._jobs_count = 0
        self._job_index = 0
        self._currently_running_job = None  # XXX: yuck!
        self.buffered_ui = BufferedUI()
        self._last_response = None

    @property
    def session_change_lock(self):
        return self._session_change_lock

    def allowed_when(state):
        def wrap(f):
            def fun(self, *args):
                if self._state != state:
                    raise AssertionError(
                        "expected %s, is %s" % (self._state, state))
                return f(self, *args)
            return fun
        return wrap

    @allowed_when(Idle)
    def start_session(self, configuration):
        _logger.debug("start_session: %r", configuration)
        self._sa.start_new_session('checkbox-service')
        self._session_id = self._sa.get_session_id()
        tps = self._sa.get_test_plans()
        response = zip(tps, [self._sa.get_test_plan(tp).name for tp in tps])
        self._state = Started
        self._available_testplans = sorted(
            response, key=lambda x: x[1])  # sorted by name
        return self._available_testplans

    @allowed_when(Started)
    def bootstrap(self, test_plan_id):
        _logger.debug("bootstrap: %r", test_plan_id)
        self._sa.update_app_blob(json.dumps(
            {'testplan_id': test_plan_id, }).encode("UTF-8"))
        self._sa.select_test_plan(test_plan_id)
        self._sa.bootstrap()
        self._jobs_count = len(self._sa.get_static_todo_list())
        self._state = Bootstrapped
        return self._sa.get_static_todo_list()

    @allowed_when(Bootstrapped)
    def run_job(self, job_id):
        """
        Depending on the type of the job, run_job can yield different number
        of Interaction instances.
        """
        _logger.debug("run_job: %r", job_id)
        self._job_index = self._jobs_count - len(
            self._sa.get_dynamic_todo_list()) + 1
        self._currently_running_job = job_id
        job = self._sa.get_job(job_id)
        if job.plugin in [
                'manual', 'user-interact-verify', 'user-interact']:
            self._current_interaction = Interaction('purpose', job.tr_purpose)
            yield self._current_interaction
        if job.user and not self._sudo_password:
            self._ephemeral_key = EphemeralKey()
            self._current_interaction = Interaction(
                'sudo_input', self._ephemeral_key.public_key)
            yield self._current_interaction
            assert(self._sudo_password is not None)
        self._state = Running
        self._be = BackgroundExecutor(self, job_id, self._sa.run_job)

    @allowed_when(Running)
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
        if self._be.is_alive():
            return ('running', self.buffered_ui.get_output())
        else:
            return ('done', self._be.outcome())
        return 'running' if self._be.is_alive() else 'done'

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
        if self._state == Started:
            payload = self._available_testplans
        return self._state, payload

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
        self._sudo_password = cyphertext

    def get_decrypted_password(self):
        """Return decrypted password"""
        assert(self._sudo_password)
        return self._sudo_broker.decrypt_password(self._sudo_password)

    def finish_job(self):
        # assert the thread completed
        self._sa.use_job_result(
            self._currently_running_job, self._be.wait().get_result())
        self._session_change_lock.release()
        if not self._sa.get_dynamic_todo_list():
            self._state = Idle
        else:
            self._state = Bootstrapped

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
        self._state = Bootstrapped

    def finalize_session(self):
        self._sa.finalize_session()
        self._state = Idle
