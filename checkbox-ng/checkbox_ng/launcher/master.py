# This file is part of Checkbox.
#
# Copyright 2017-2019 Canonical Ltd.
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
import gettext
import logging
import os
import select
import socket
import time
import signal
import sys

from collections import namedtuple
from functools import partial
from tempfile import SpooledTemporaryFile

from guacamole import Command
from plainbox.impl.color import Colorizer
from plainbox.impl.launcher import DefaultLauncherDefinition
from plainbox.impl.secure.sudo_broker import SudoProvider
from plainbox.impl.session.remote_assistant import RemoteSessionAssistant
from plainbox.impl.session.restart import RemoteSnappyRestartStrategy
from plainbox.vendor import rpyc
from plainbox.vendor.rpyc.utils.server import ThreadedServer
from checkbox_ng.urwid_ui import test_plan_browser
from checkbox_ng.urwid_ui import CategoryBrowser
from checkbox_ng.urwid_ui import ReRunBrowser
from checkbox_ng.urwid_ui import interrupt_dialog
from checkbox_ng.urwid_ui import resume_dialog
from checkbox_ng.launcher.run import NormalUI
from checkbox_ng.launcher.stages import MainLoopStage
from checkbox_ng.launcher.stages import ReportsStage
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
        print(SimpleUI.C.header(header, fill='-'))

    def green_text(text, end='\n'):
        print(SimpleUI.C.GREEN(text), end=end)

    def red_text(text, end='\n'):
        print(SimpleUI.C.RED(text), end=end)

    def horiz_line():
        print(SimpleUI.C.WHITE('-' * 80))

    @property
    def is_interactive(self):
        return True

    @property
    def sa(self):
        None


class RemoteMaster(Command, ReportsStage, MainLoopStage):
    """
    This class implements the part that presents UI to the operator and
    steers the session.
    """

    name = 'remote-control'

    @property
    def is_interactive(self):
        return (self.launcher.ui_type == 'interactive' and
                sys.stdin.isatty() and sys.stdout.isatty())

    @property
    def C(self):
        return self._C

    @property
    def sa(self):
        return self._sa

    def invoked(self, ctx):
        self._C = Colorizer()
        self._override_exporting(self.local_export)
        self._launcher_text = ''
        self._password_entered = False
        self._is_bootstrapping = False
        self._target_host = ctx.args.host
        self._sudo_provider = None
        self.launcher = DefaultLauncherDefinition()
        if ctx.args.launcher:
            expanded_path = os.path.expanduser(ctx.args.launcher)
            if not os.path.exists(expanded_path):
                raise SystemExit(_("{} launcher file was not found!").format(
                    expanded_path))
            with open(expanded_path, 'rt') as f:
                self._launcher_text = f.read()
            self.launcher.read_string(self._launcher_text)
        timeout = 600
        deadline = time.time() + timeout
        port = 18871
        print(_("Connecting to {}:{}. Timeout: {}s").format(
            ctx.args.host, port, timeout))
        while time.time() < deadline:
            try:
                self.connect_and_run(ctx.args.host, port)
                break
            except (ConnectionRefusedError, socket.timeout, OSError):
                print('.', end='', flush=True)
                time.sleep(1)
        else:
            print(_("\nConnection timed out."))

    def connect_and_run(self, host, port=18871):
        config = rpyc.core.protocol.DEFAULT_CONFIG.copy()
        config['allow_all_attrs'] = True
        keep_running = False
        self._prepare_transports()
        interrupted = False
        while True:
            try:
                if interrupted:
                    _logger.info("master: Session interrupted")
                    interrupted = False  # we are handling the interruption ATM
                    # next line can raise exception due to connection being
                    # lost so let's set the default behavior to quitting
                    keep_running = False
                    keep_running = self._handle_interrupt()
                    if not keep_running:
                        break
                conn = rpyc.connect(host, port, config=config)
                keep_running = True
                self._sa = conn.root.get_sa()
                self.sa.conn = conn
                if not self._sudo_provider:
                    self._sudo_provider = SudoProvider(
                        self.sa.get_master_public_key())
                try:
                    slave_api_version = self.sa.get_remote_api_version()
                except AttributeError:
                    raise SystemExit(_("Slave doesn't declare Remote API"
                                       " version. Update Checkbox on the Slave!"))
                master_api_version = RemoteSessionAssistant.REMOTE_API_VERSION
                if slave_api_version != master_api_version:
                    raise SystemExit(_("Remote API version mismatch. "
                                       "Slave uses: {}. Master uses: {}").format(
                        slave_api_version, master_api_version))
                state, payload = self.sa.whats_up()
                _logger.info("master: Main dispatch with state: %s", state)
                keep_running = {
                    'idle': self.new_session,
                    'running': self.wait_and_continue,
                    'finalizing': self.finish_session,
                    'testsselected': partial(
                        self.run_jobs, resumed_session_info=payload),
                    'bootstrapping': self.restart,
                    'bootstrapped': partial(
                        self.select_jobs, all_jobs=payload),
                    'started': self.restart,
                    'interacting': partial(
                        self.resume_interacting, interaction=payload),
                }[state]()
            except EOFError as exc:
                print("Connection lost!")
                _logger.info("master: Connection lost due to: %s", exc)
                time.sleep(1)
            except (ConnectionRefusedError, socket.timeout, OSError) as exc:
                _logger.info("master: Connection lost due to: %s", exc)
                if not keep_running:
                    raise
                # it's reconnecting, so we can ignore refuses
                print('Reconnecting...')
                time.sleep(0.5)
            except KeyboardInterrupt:
                interrupted = True

            if not keep_running:
                break

    def new_session(self):
        _logger.info("master: Starting new session.")
        configuration = dict()
        configuration['launcher'] = self._launcher_text

        tps = self.sa.start_session(configuration)
        _logger.debug("master: Session started. Available TPs:\n%s",
                      '\n'.join(['  ' + tp[0] for tp in tps]))
        if self.launcher.test_plan_forced:
            self.select_tp(self.launcher.test_plan_default_selection)
            self.select_jobs(self.jobs)
        else:
            self.interactively_choose_tp(tps)

    def interactively_choose_tp(self, tps):
        _logger.info("master: Interactively choosing TP.")
        tp_names = [tp[1] for tp in tps]
        selected_index = test_plan_browser(
            "Select test plan", tp_names, 0)
        if selected_index is None:
            print(_("Nothing selected"))
            raise SystemExit(0)

        self.select_tp(tps[selected_index][0])
        if not self.jobs:
            print(self.C.RED(_("There were no tests to select from!")))
            self.sa.finalize_session()
            return
        self.select_jobs(self.jobs)

    def password_query(self):
        if not self._password_entered and not self.sa.passwordless_sudo:
            wrong_pass = True
            while wrong_pass:
                if not self.sa.save_password(
                        self._sudo_provider.encrypted_password):
                    self._sudo_provider.clear_password()
                    print(_("Sorry, try again"))
                else:
                    wrong_pass = False

    def select_tp(self, tp):
        _logger.info("master: Selected test plan: %s", tp)
        pass_required = self.sa.prepare_bootstrapping(tp)
        if pass_required:
            self.password_query()

        self._is_bootstrapping = True
        bs_todo = self.sa.get_bootstrapping_todo_list()
        for job_no, job_id in enumerate(bs_todo, start=1):
            print(self.C.header(
                _('Bootstrap {} ({}/{})').format(
                    job_id, job_no, len(bs_todo), fill='-')))
            self.sa.run_bootstrapping_job(job_id)
            self.wait_for_job()
        self._is_bootstrapping = False
        self.jobs = self.sa.finish_bootstrap()

    def select_jobs(self, all_jobs):
        _logger.info("master: Selecting jobs.")
        if self.launcher.test_selection_forced:
            _logger.debug("master: Force-seleced jobs: %s", all_jobs)
            self.sa.save_todo_list(all_jobs)
            self.run_jobs()
        else:
            reprs = self.sa.get_jobs_repr(all_jobs)
            wanted_set = CategoryBrowser(
                "Choose tests to run on your system:", reprs).run()
            # wanted_set may have bad order, let's use it as a filter to the
            # original list
            todo_list = [job for job in all_jobs if job in wanted_set]
            _logger.debug("master: Selected jobs: %s", todo_list)
            self.sa.save_todo_list(todo_list)
            self.run_jobs()
        return False

    def register_arguments(self, parser):
        parser.add_argument('host', help=_("target host"))
        parser.add_argument('launcher', nargs='?', help=_(
            "launcher definition file to use"))

    def _handle_interrupt(self):
        """
        Returns True if the master should keep running.
        And False if it should quit.
        """
        if self.launcher.ui_type == 'silent':
            self._sa.terminate()
            return False
        response = interrupt_dialog(self._target_host)
        if response == 'cancel':
            return True
        elif response == 'kill-master':
            return False
        elif response == 'kill-service':
            self._sa.terminate()
            return False
        elif response == 'abandon':
            self._sa.finalize_session()
            return True

    def finish_session(self):
        print(self.C.header("Results"))
        if self.launcher.local_submission:
            # Disable SIGINT while we save local results
            tmp_sig = signal.signal(signal.SIGINT, signal.SIG_IGN)
            self._export_results()
            signal.signal(signal.SIGINT, tmp_sig)
        self.sa.finalize_session()
        return False

    def wait_and_continue(self):
        progress = self.sa.whats_up()[1]
        print("Rejoined session.")
        print("In progress: {} ({}/{})".format(
            progress[2], progress[0], progress[1]))
        self.wait_for_job()
        self.run_jobs()

    def _handle_last_job_after_resume(self, resumed_session_info):
        if self.launcher.ui_type == 'silent':
            time.sleep(20)
        else:
            resume_dialog(10)
        jobs_repr = self.sa.get_jobs_repr([resumed_session_info['last_job']])
        job = jobs_repr[-1]
        SimpleUI.header(job['name'])
        print(_("ID: {0}").format(job['id']))
        print(_("Category: {0}").format(job['category_name']))
        SimpleUI.horiz_line()
        print(
            _("Outcome") + ": " +
            SimpleUI.C.result(self.sa.get_job_result(job['id'])))

    def run_jobs(self, resumed_session_info=None):
        if resumed_session_info:
            self._handle_last_job_after_resume(resumed_session_info)
        _logger.info("master: Running jobs.")
        jobs = self.sa.get_session_progress()
        _logger.debug("master: Jobs to be run:\n%s",
                      '\n'.join(['  ' + job for job in jobs]))
        total_num = len(jobs['done']) + len(jobs['todo'])

        jobs_repr = self.sa.get_jobs_repr(jobs['todo'], len(jobs['done']))
        if any([x['user'] is not None for x in jobs_repr]):
            self.password_query()

        self._run_jobs(jobs_repr, total_num)
        rerun_candidates = self.sa.get_rerun_candidates('manual')
        if rerun_candidates:
            if self.launcher.ui_type == 'interactive':
                while True:
                    if not self._maybe_manual_rerun_jobs():
                        break
        if self.launcher.auto_retry:
            while True:
                if not self._maybe_auto_rerun_jobs():
                    break
        self.finish_session()

    def resume_interacting(self, interaction):
        self.sa.remember_users_response('rollback')
        self.run_jobs()

    def wait_for_job(self, dont_finish=False):
        _logger.info("master: Waiting for job to finish.")
        while True:
            state, payload = self.sa.monitor_job()
            if payload and not self._is_bootstrapping:
                for stream, line in payload:
                    if stream == 'stderr':
                        SimpleUI.red_text(line, end='')
                    else:
                        SimpleUI.green_text(line, end='')
            if state == 'running':
                time.sleep(0.5)
                while True:
                    res = select.select([sys.stdin], [], [], 0)
                    if not res[0]:
                        break
                    # XXX: this assumes that sys.stdin is chunked in lines
                    self.sa.transmit_input(res[0][0].readline())

            else:
                if dont_finish:
                    return
                self.finish_job()
                break

    def finish_job(self, result=None):
        _logger.info("master: Finishing job with a result: %s", result)
        job_result = self.sa.finish_job(result)
        if not self._is_bootstrapping:
            SimpleUI.horiz_line()
            print(_("Outcome") + ": " + SimpleUI.C.result(job_result))

    def abandon(self):
        _logger.info("master: Abandoning session.")
        self.sa.finalize_session()

    def restart(self):
        _logger.info("master: Restarting session.")
        self.abandon()
        self.new_session()

    def local_export(self, exporter_id, transport, options=()):
        _logger.info("master: Exporting locally'")
        exporter = self._sa.manager.create_exporter(exporter_id, options)
        exported_stream = SpooledTemporaryFile(max_size=102400, mode='w+b')
        async_dump = rpyc.async_(exporter.dump_from_session_manager)
        res = async_dump(self._sa.manager, exported_stream)
        res.wait()
        exported_stream.seek(0)
        result = transport.send(exported_stream)
        return result

    def _maybe_auto_rerun_jobs(self):
        # create a list of jobs that qualify for rerunning
        rerun_candidates = self.sa.get_rerun_candidates('auto')
        # bail-out early if no job qualifies for rerunning
        if not rerun_candidates:
            return False
        # we wait before retrying
        delay = self.launcher.delay_before_retry
        _logger.info(_("Waiting {} seconds before retrying failed"
                       " jobs...".format(delay)))
        time.sleep(delay)
        # include resource jobs that jobs to retry depend on

        candidates = self.sa.prepare_rerun_candidates(rerun_candidates)
        self._run_jobs(self.sa.get_jobs_repr(candidates), len(candidates))
        return True

    def _maybe_manual_rerun_jobs(self):
        rerun_candidates = self.sa.get_rerun_candidates('manual')
        if not rerun_candidates:
            return False
        test_info_list = self.sa.get_jobs_repr(
            [j.id for j in rerun_candidates])
        wanted_set = ReRunBrowser(
            _("Select jobs to re-run"), test_info_list, rerun_candidates).run()
        if not wanted_set:
            return False
        candidates = self.sa.prepare_rerun_candidates([
            job for job in rerun_candidates if job.id in wanted_set])
        self._run_jobs(self.sa.get_jobs_repr(candidates), len(candidates))
        return True

    def _run_jobs(self, jobs_repr, total_num=0):
        for job in jobs_repr:
            SimpleUI.header(
                _('Running job {} / {}').format(
                    job['num'], total_num,
                    fill='-'))
            SimpleUI.header(job['name'])
            print(_("ID: {0}").format(job['id']))
            print(_("Category: {0}").format(job['category_name']))
            SimpleUI.horiz_line()
            next_job = False
            for interaction in self.sa.run_job(job['id']):
                if interaction.kind == 'sudo_input':
                    self.sa.save_password(
                        self._sudo_provider.encrypted_password)
                if interaction.kind == 'purpose':
                    SimpleUI.description(_('Purpose:'), interaction.message)
                elif interaction.kind in ['description', 'steps']:
                    SimpleUI.description(_('Steps:'), interaction.message)
                    if job['command'] is None:
                        cmd = 'run'
                    else:
                        cmd = SimpleUI(None).wait_for_interaction_prompt(None)
                    if cmd == 'skip':
                        next_job = True
                    self.sa.remember_users_response(cmd)
                elif interaction.kind == 'verification':
                    self.wait_for_job(dont_finish=True)
                    if interaction.message:
                        SimpleUI.description(
                            _('Verification:'), interaction.message)
                    JobAdapter = namedtuple('job_adapter', ['command'])
                    job = JobAdapter(job['command'])
                    cmd = SimpleUI(None)._interaction_callback(
                        job, interaction.extra)
                    self.sa.remember_users_response(cmd)
                    self.finish_job(interaction.extra.get_result())
                    next_job = True
                elif interaction.kind == 'comment':
                    new_comment = input(SimpleUI.C.BLUE(
                        _('Please enter your comments:') + '\n'))
                    self.sa.remember_users_response(new_comment + '\n')
            if next_job:
                continue
            self.wait_for_job()
