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
This module contains implementation of the service end of the remote execution
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
_logger = logging.getLogger("service")


class SessionAssistantSlave(rpyc.Service):

    session_assistant = None
    controlling_master_conn = None
    master_blaster = None

    def exposed_get_sa(*args):
        return SessionAssistantSlave.session_assistant

    def exposed_register_master_blaster(self, callable):
        """
        Register a callable that will be called when the slave decides to
        disconnect the master. This should be used to prepare the master for
        the disconnection, so it can differentiate between network failures
        and a planned disconnect.
        The callable will be called with one param - a string with a reason
        for the disconnect.
        """
        SessionAssistantSlave.master_blaster = callable

    def on_connect(self, conn):
        try:
            if SessionAssistantSlave.master_blaster:
                msg = 'Forcefully disconnected by new master from {}:{}'.format(
                    conn._config['endpoints'][1][0], conn._config['endpoints'][1][1])
                SessionAssistantSlave.master_blaster(msg)
                old_master = SessionAssistantSlave.controlling_master_conn
                if old_master is not None:
                    old_master.close()
                SessionAssistantSlave.master_blaster = None

            SessionAssistantSlave.controlling_master_conn = conn
        except TimeoutError as exc:
            # this happens when the reference to .master_blaster times out,
            # meaning the master is blocked on an urwid screen or some other
            # thread blocking operation. In any case it means there was a
            # previous master, so we need to kill it
            old_master = SessionAssistantSlave.controlling_master_conn
            SessionAssistantSlave.master_blaster = None
            old_master.close()
            SessionAssistantSlave.controlling_master_conn = conn

    def on_disconnect(self, conn):
        SessionAssistantSlave.master_blaster = None
        self.controlling_master_conn = None


class RemoteSlave():
    """
    Run checkbox instance as a service

    RemoteSlave implements functionality for the half that's actually running
    the tests - the one that was summoned using `checkbox-cli service`. This
    part should be run on system-under-test.
    """

    name = 'service'

    def invoked(self, ctx):
        if os.geteuid():
            raise SystemExit(_("Checkbox service must be run by root!"))
        if not is_passwordless_sudo():
            raise SystemExit(
                _("System is not configured to run sudo without a password!"))
        slave_port = ctx.args.port

        # Check if able to connect to the slave port as indicator of there
        # already being a slave running
        def slave_port_open():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(('127.0.0.1', slave_port))
            sock.close()
            return result
        if slave_port_open() == 0:
            raise SystemExit(_("Found port {} is open. Is Checkbox service"
                               " already running?").format(slave_port))

        SessionAssistantSlave.session_assistant = RemoteSessionAssistant(
            lambda s: [sys.argv[0] + 'service'])
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
                SessionAssistantSlave.session_assistant.resume_by_id(
                    session_id)
            elif ctx.args.resume:
                # XXX: explicitly passing None to not have to bump Remote API
                # TODO: remove on the next Remote API bump
                SessionAssistantSlave.session_assistant.resume_by_id(None)
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
                SessionAssistantSlave.session_assistant.resume_by_id(
                    session_id)
        self._server = ThreadedServer(
            SessionAssistantSlave,
            port=slave_port,
            protocol_config={
                "allow_all_attrs": True,
                "allow_setattr": True,
                "sync_request_timeout": 1,
                "propagate_SystemExit_locally": True
            },
        )
        SessionAssistantSlave.session_assistant.terminate_cb = (
            self._server.close)
        self._server.start()

    def register_arguments(self, parser):
        parser.add_argument('--resume', action='store_true', help=_(
            "resume last session"))
        parser.add_argument('--port', type=int, default=18871, help=_(
            "port to listen on"))
