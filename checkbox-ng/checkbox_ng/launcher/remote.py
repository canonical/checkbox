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
"""
This module contains implemementation of both ends of the remote execution
functionality.

RemoteService implements functionality for the half that's actually running the
tests - the one that was summoned using `checkbox-cli remote-service`. This part
should be run on system-under-test.

RemoteControl implements the part that presents UI to the operator and steers
the session.
"""
import gettext
import socket
import time
import sys

from functools import partial

from guacamole import Command
from plainbox.impl.color import Colorizer
from plainbox.impl.secure.sudo_broker import SudoProvider
from plainbox.impl.session.assistant2 import SessionAssistant2
from plainbox.vendor import rpyc
from plainbox.vendor.rpyc.utils import server
from checkbox_ng.urwid_ui import test_plan_browser
from checkbox_ng.urwid_ui import CategoryBrowser

_ = gettext.gettext


class SimpleUI():
    """
    Simplified version of the NormalUI from plainbox.impl.commands.inv_run.

    The simplification is mainly about just dealing with text that is to be
    displayed, instead of plainbox' abstractions like job, job state, etc.

    It's a class just for namespacing purposes.
    """

    C = Colorizer()

    # XXX: evaluate other ways of aggregating those functions

    def description(header, text):
        print(SimpleUI.C.WHITE(header))
        print()
        print(SimpleUI.C.CYAN(text))
        print()


class SessionAssistantService(rpyc.Service):

    session_assistant = None

    def exposed_get_sa(*args):
        return SessionAssistantService.session_assistant


class RemoteService(Command):
    name = 'remote-service'

    def invoked(self, ctx):
        SessionAssistantService.session_assistant = SessionAssistant2(
            lambda s: [sys.argv[0] + ' remote-service --resume'])
        if ctx.args.resume:
            try:
                SessionAssistantService.session_assistant.resume_last()
            except StopIteration:
                print("Couldn't resume the session")
        rpyc.utils.server.ThreadedServer(
            SessionAssistantService,
            port=18871,
            protocol_config={
                "allow_all_attrs": True,
                "allow_setattr": True,
                "sync_request_timeout": 1,
                },
        ).start()

    def register_arguments(self, parser):
        parser.add_argument('--resume', action='store_true', help=_(
            "resume last session"))


class RemoteControl(Command):
    name = 'remote-control'

    def invoked(self, ctx):
        config = rpyc.core.protocol.DEFAULT_CONFIG.copy()
        config['sync_request_timeout'] = 1
        config['allow_all_attrs'] = True
        keep_running = False
        while True:
            try:
                conn = rpyc.connect(ctx.args.host, 18871, config=config)
                keep_running = True
                self.sa = conn.root.get_sa()
                self.sa.conn = conn
                self._sudo_provider = SudoProvider(
                    self.sa.get_master_public_key())
                state, payload = self.sa.whats_up()
                keep_running = {
                    'idle': self.new_session,
                    'running': self.wait_and_continue,
                    'finalizing': self.finish_session,
                    'bootstrapped': self.continue_session,
                    'started': partial(self.select_tp, tps=payload),
                }[state]()
            except EOFError:
                print("Connection lost!")
                time.sleep(1)
            except (ConnectionRefusedError, socket.timeout, OSError):
                if not keep_running:
                    raise
                # it's reconnecting, so we can ignore refuses
                print('Reconnecting...')
                time.sleep(0.5)
            except KeyboardInterrupt:
                self._handle_interrupt()
                # TODO: handle action properly, like:
                # action = self._handle_interrupt()

            if not keep_running:
                break

    def new_session(self):
        tps = self.sa.start_session(dict())
        self.select_tp(tps)

    def select_tp(self, tps):
        tp_names = [tp[1] for tp in tps]
        selected_index = test_plan_browser(
            "Select test plan", tp_names, 0)
        jobs = self.sa.bootstrap(tps[selected_index][0])
        reprs = self.sa.get_jobs_repr(jobs)
        wanted_set = CategoryBrowser(
            "Choose tests to run on your system:", reprs).run()
        # wanted_set may have bad order, let's use it as a filter to the
        # original list
        todo_list = [job for job in jobs if job in wanted_set]
        for job in todo_list:
            for interaction in self.sa.run_job(job):
                if interaction.kind == 'sudo_input':
                    self.sa.save_password(
                        self._sudo_provider.encrypted_password)
                if interaction.kind == 'purpose':
                    SimpleUI.description(_('Purpose:'), interaction.message)
            self.run_jobs()
        return False

    def register_arguments(self, parser):
        parser.add_argument('host', help=_("target host"))

    def _handle_interrupt(self):
        # TODO: ask whether user wants to disconnect the client or
        #      abandon the session
        while True:
            time.sleep(1)

    def finish_session(self):
        # TODO: nicer UI
        print('session over')
        self.sa.finalize_session()
        return False

    def wait_and_continue(self):
        # TODO: nicer UI
        progress = self.sa.whats_up()[1]
        print("rejoined session. Running job ({}/{}): {}".format(
            progress[0], progress[1], progress[2]))
        self.run_jobs()
        self.continue_session()

    def continue_session(self):
        todo = self.sa.get_session_progress()["todo"]
        for job in todo:
            self.sa.run_job(job)
            self.run_jobs()
        self.finish_session()

    def run_jobs(self):
        while True:
            state, payload = self.sa.monitor_job()
            if state == 'running':
                if payload:
                    print(payload, end='')
                time.sleep(0.5)
            else:
                self.sa.finish_job()
                break

    def abandon(self):
        self.sa.finalize_session()
