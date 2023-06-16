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
This module contains implementation of the agent end of the remote execution
functionality.
"""
import gettext
import logging
import os
import socket
import sys
from plainbox.impl.secure.sudo_broker import is_passwordless_sudo
from plainbox.impl.session.remote_assistant import RemoteSessionAssistant
from plainbox.impl.session.restart import RemoteDebRestartStrategy
from plainbox.impl.session.restart import RemoteSnappyRestartStrategy
from plainbox.vendor import rpyc
from plainbox.vendor.rpyc.utils.server import ThreadedServer

_ = gettext.gettext
_logger = logging.getLogger("agent")


class SessionAssistantAgent(rpyc.Service):

    session_assistant = None
    controlling_controller_conn = None
    controller_blaster = None

    def exposed_get_sa(*args):
        return SessionAssistantAgent.session_assistant

    def exposed_register_controller_blaster(self, callable):
        """
        Register a callable that will be called when the agent decides to
        disconnect the controller. This should be used to prepare the controller for
        the disconnection, so it can differentiate between network failures
        and a planned disconnect.
        The callable will be called with one param - a string with a reason
        for the disconnect.
        """
        SessionAssistantAgent.controller_blaster = callable

    def on_connect(self, conn):
        try:
            if SessionAssistantAgent.controller_blaster:
                msg = 'Forcefully disconnected by new controller from {}:{}'.format(
                    conn._config['endpoints'][1][0], conn._config['endpoints'][1][1])
                SessionAssistantAgent.controller_blaster(msg)
                old_controller = SessionAssistantAgent.controlling_controller_conn
                if old_controller is not None:
                    old_controller.close()
                SessionAssistantAgent.controller_blaster = None

            SessionAssistantAgent.controlling_controller_conn = conn
        except TimeoutError as exc:
            # this happens when the reference to .controller_blaster times out,
            # meaning the controller is blocked on an urwid screen or some other
            # thread blocking operation. In any case it means there was a
            # previous controller, so we need to kill it
            old_controller = SessionAssistantAgent.controlling_controller_conn
            SessionAssistantAgent.controller_blaster = None
            old_controller.close()
            SessionAssistantAgent.controlling_controller_conn = conn

    def on_disconnect(self, conn):
        SessionAssistantAgent.controller_blaster = None
        self.controlling_controller_conn = None


class RemoteAgent():
    """
    Run checkbox instance as a agent

    RemoteAgent implements functionality for the half that's actually running
    the tests - the one that was summoned using `checkbox-cli run-agent`. This
    part should be run on system-under-test.
    """

    name = 'agent'

    def invoked(self, ctx):
        if os.geteuid():
            raise SystemExit(_("Checkbox agent must be run by root!"))
        if not is_passwordless_sudo():
            raise SystemExit(
                _("System is not configured to run sudo without a password!"))
        agent_port = ctx.args.port

        # Check if able to connect to the agent port as indicator of there
        # already being a agent running
        def agent_port_open():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(('127.0.0.1', agent_port))
            sock.close()
            return result
        if agent_port_open() == 0:
            raise SystemExit(_("Found port {} is open. Is Checkbox agent"
                               " already running?").format(agent_port))

        SessionAssistantAgent.session_assistant = RemoteSessionAssistant(
            lambda s: [sys.argv[0] + 'agent'])
        snap_data = os.getenv('SNAP_DATA')
        snap_rev = os.getenv('SNAP_REVISION')
        remote_restart_strategy_debug = os.getenv('REMOTE_RESTART_DEBUG')
        if (snap_data and snap_rev) or ctx.args.resume:
            if remote_restart_strategy_debug:
                strategy = RemoteSnappyRestartStrategy(debug=True)
            else:
                strategy = RemoteSnappyRestartStrategy()
            if os.path.exists(strategy.session_resume_filename):
                with open(strategy.session_resume_filename, 'rt') as f:
                    session_id = f.readline()
                SessionAssistantAgent.session_assistant.resume_by_id(
                    session_id)
            elif ctx.args.resume:
                # XXX: explicitly passing None to not have to bump Remote API
                # TODO: remove on the next Remote API bump
                SessionAssistantAgent.session_assistant.resume_by_id(None)
        else:
            _logger.info("RemoteDebRestartStrategy")
            if remote_restart_strategy_debug:
                strategy = RemoteDebRestartStrategy(debug=True)
            else:
                strategy = RemoteDebRestartStrategy()
            if os.path.exists(strategy.session_resume_filename):
                with open(strategy.session_resume_filename, 'rt') as f:
                    session_id = f.readline()
                _logger.info(
                    "RemoteDebRestartStrategy resume_by_id %r", session_id)
                SessionAssistantAgent.session_assistant.resume_by_id(
                    session_id)
        self._server = ThreadedServer(
            SessionAssistantAgent,
            port=agent_port,
            protocol_config={
                "allow_all_attrs": True,
                "allow_setattr": True,
                "sync_request_timeout": 1,
                "propagate_SystemExit_locally": True
            },
        )
        SessionAssistantAgent.session_assistant.terminate_cb = (
            self._server.close)
        self._server.start()

    def register_arguments(self, parser):
        parser.add_argument('--resume', action='store_true', help=_(
            "resume last session"))
        parser.add_argument('--port', type=int, default=18871, help=_(
            "port to listen on"))
