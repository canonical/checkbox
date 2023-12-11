# This file is part of Checkbox.
#
# Copyright 2017-2023 Canonical Ltd.
# Written by:
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
import json
import logging
import os
import socket
import sys
from checkbox_ng import app_context
from plainbox.impl.config import Configuration
from plainbox.impl.secure.sudo_broker import is_passwordless_sudo
from plainbox.impl.session.assistant import ResumeCandidate
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
                msg = "Forcefully disconnected by new controller from {}:{}".format(
                    conn._config["endpoints"][1][0],
                    conn._config["endpoints"][1][1],
                )
                SessionAssistantAgent.controller_blaster(msg)
                old_controller = (
                    SessionAssistantAgent.controlling_controller_conn
                )
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


class RemoteAgent:
    """
    Run checkbox instance as a agent

    RemoteAgent implements functionality for the half that's actually running
    the tests - the one that was summoned using `checkbox-cli run-agent`. This
    part should be run on system-under-test.
    """

    name = "agent"

    def invoked(self, ctx):
        if os.geteuid():
            raise SystemExit(_("Checkbox agent must be run by root!"))
        if not is_passwordless_sudo():
            raise SystemExit(
                _("System is not configured to run sudo without a password!")
            )
        if ctx.args.resume:
            msg = (
                "--resume is deprecated and will be removed soon. "
                "Automated sessions are now always resumed. "
                "Manual sessions can be resumed from the welcome screen."
            )
            _logger.warning(msg)

        agent_port = ctx.args.port

        exit_if_port_unavailable(agent_port)

        # The RemoteSessionAssistant required a callable that was used to
        # start the agent as a part of restart strategy. We don't need that
        # functionality, so we just pass a dummy callable that will never be
        # called. It's left in to avoid breaking the API.
        SessionAssistantAgent.session_assistant = RemoteSessionAssistant(
            lambda x: None
        )

        # the agent is meant to be run only as a service,
        # and we always resume if the session was automated,
        # so we don't need to encode check whether we should resume

        sessions = list(ctx.sa.get_resumable_sessions())
        if sessions:
            # the sessions are ordered by time, so the first one is the most
            # recent one
            if is_the_session_noninteractive(sessions[0]):
                SessionAssistantAgent.session_assistant.resume_by_id(
                    sessions[0].id
                )

        self._server = ThreadedServer(
            SessionAssistantAgent,
            port=agent_port,
            protocol_config={
                "allow_all_attrs": True,
                "allow_setattr": True,
                "sync_request_timeout": 1,
                "propagate_SystemExit_locally": True,
            },
        )
        SessionAssistantAgent.session_assistant.terminate_cb = (
            self._server.close
        )
        self._server.start()

    def register_arguments(self, parser):
        parser.add_argument(
            "--resume", action="store_true", help=_("resume last session")
        )
        parser.add_argument(
            "--port", type=int, default=18871, help=_("port to listen on")
        )


def is_the_session_noninteractive(
    resumable_session: "ResumeCandidate",
) -> bool:
    """
    Check if given session is non-interactive.

    To determine that we need to take the original launcher that had been used
    when the session was started, recreate it as a proper Launcher object, and
    check if it's in fact non-interactive.
    """
    # app blob is a bytes string with a utf-8 encoded json
    # let's decode it and parse it as json
    app_blob = json.loads(resumable_session.metadata.app_blob.decode("utf-8"))
    launcher = Configuration.from_text(app_blob["launcher"], "resumed session")
    return launcher.sections["ui"].get("type") == "silent"


def exit_if_port_unavailable(port: int) -> None:
    """
    Check if the port is available and exit if it's not.

    This is used by the agent to check if it's already running.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    result = sock.connect_ex(("127.0.0.1", port))
    sock.close()
    # the result is 0 if the port is open (which means the low level
    # connect() call succeeded), and 1 if it's closed (which means the low
    # level connect() call failed)
    if result == 0:
        raise SystemExit(
            _(
                "Found port {} is open. Is Checkbox agent" " already running?"
            ).format(port)
        )
