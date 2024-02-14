# This file is part of Checkbox.
#
# Copyright 2021 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
import re
import shlex
import threading
import time

from loguru import logger
import metabox.core.keys as keys
from metabox.core.utils import ExecuteResult
from ws4py.client.threadedclient import WebSocketClient


base_env = {
    "PYTHONUNBUFFERED": "1",
    "DISABLE_URWID_ESCAPE_CODES": "1",
    "XDG_RUNTIME_DIR": "/run/user/1000",
}
login_shell = ["sudo", "--user", "ubuntu", "--login"]


class InteractiveWebsocket(WebSocketClient):
    # https://stackoverflow.com/a/14693789/1154487
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stdout_data = bytearray()
        self.stdout_data_full = bytearray()
        self.stdout_lock = threading.Lock()
        self._new_data = False
        self._lookup_by_id = False
        self._connection_closed = False

    def received_message(self, message):
        if len(message.data) == 0:
            self.close()
            self._connection_closed = True
        if self.verbose:
            raw_msg = self.ansi_escape.sub(
                "", message.data.decode("utf-8", errors="ignore")
            )
            logger.trace(raw_msg.rstrip())
        with self.stdout_lock:
            self.stdout_data += message.data
            self.stdout_data_full += message.data
            self._new_data = True

    def expect(self, data, timeout=0):
        found = False
        start_time = time.time()
        if isinstance(data, str):
            data = data.encode("utf-8")

        try:
            # custom classes, like _re, provide this functionality and are a
            # valid input
            search = data.search
            split = data.split
        except AttributeError:

            def search(stream):
                return data in stream

            split = bytes.split

        while not found:
            time.sleep(0.1)
            check = search(self.stdout_data)
            if check:
                # truncate the history because subsequent expect should not
                # re-match the same text
                with self.stdout_lock:
                    self.stdout_data = split(
                        self.stdout_data, data, maxsplit=1
                    )[-1]
                found = True
            elif timeout and time.time() > start_time + timeout:
                msg = "'{}' not found! Timeout is reached (set to {})".format(
                    data, timeout
                )
                logger.warning(msg)
                raise TimeoutError(msg)
            elif self._connection_closed:
                # this could have been updated from the other thread, lets
                # check before exiting the loop
                found = found or data in self.stdout_data
                break
        return found

    def expect_not(self, data, timeout=0):
        return not self.expect(data, timeout)

    def select_test_plan(self, data, timeout=0):
        if not self._lookup_by_id:
            self.send(("i" + keys.KEY_HOME).encode("utf-8"), binary=True)
            self._lookup_by_id = True
        else:
            self.send(keys.KEY_HOME.encode("utf-8"), binary=True)
        not_found = True
        max_attemps = 10
        attempt = 0
        still_on_first_screen = True
        old_stdout_data = b""
        if len(data) > 67:
            data = data[:67] + "   │\r\n│        " + data[67:]
        while attempt < max_attemps:
            if self._new_data and self.stdout_data:
                if old_stdout_data == self.stdout_data:
                    break
                check = data.encode("utf-8") in self.stdout_data
                if not check:
                    self._new_data = False
                    with self.stdout_lock:
                        old_stdout_data = self.stdout_data
                        self.stdout_data = bytearray()
                    stdin_payload = keys.KEY_PAGEDOWN + keys.KEY_SPACE
                    self.send(stdin_payload.encode("utf-8"), binary=True)
                    still_on_first_screen = False
                    attempt = 0
                else:
                    not_found = False
                    break
            else:
                time.sleep(0.1)
                attempt += 1
        if not_found:
            logger.warning("test plan {} not found!", data)
            return False
        data = "(X) " + data
        attempt = 0
        if still_on_first_screen:
            self.send(keys.KEY_PAGEDOWN.encode("utf-8"), binary=True)
        while attempt < max_attemps:
            if self._new_data and self.stdout_data:
                check = data.encode("utf-8") in self.stdout_data
                if not check:
                    self._new_data = False
                    with self.stdout_lock:
                        self.stdout_data = bytearray()
                    stdin_payload = keys.KEY_UP + keys.KEY_SPACE
                    self.send(stdin_payload.encode("utf-8"), binary=True)
                    attempt = 0
                else:
                    not_found = False
                    with self.stdout_lock:
                        self.stdout_data = bytearray()
                    break
            else:
                time.sleep(0.1)
                attempt += 1
        return not_found is False

    def send_signal(self, signal):
        self.ctl.send(json.dumps({"command": "signal", "signal": signal}))

    @property
    def container(self):
        return self._container

    @container.setter
    def container(self, container):
        self._container = container

    @property
    def ctl(self):
        return self._ctl

    @ctl.setter
    def ctl(self, ctl):
        self._ctl = ctl

    @property
    def verbose(self):
        return self._verbose

    @verbose.setter
    def verbose(self, verbose):
        self._verbose = verbose


def env_wrapper(env):
    env_cmd = ["env"]
    env.update(base_env)
    env_cmd += [
        "{key}={value}".format(key=key, value=value)
        for key, value in sorted(env.items())
    ]
    return env_cmd


def timeout_wrapper(timeout):
    if timeout:
        return ["timeout", "--signal=KILL", str(timeout)]
    else:
        return []


def interactive_execute(container, cmd, env={}, verbose=False, timeout=0):
    if verbose:
        logger.trace(cmd)
    ws_urls = container.raw_interactive_execute(
        login_shell + env_wrapper(env) + shlex.split(cmd)
    )

    base_websocket_url = container.client.websocket_url
    ctl = WebSocketClient(base_websocket_url)
    ctl.resource = ws_urls["control"]
    ctl.connect()
    pts = InteractiveWebsocket(base_websocket_url)
    pts.resource = ws_urls["ws"]
    pts.verbose = verbose
    pts.container = container
    pts.ctl = ctl
    pts.connect()
    return pts


def run_or_raise(container, cmd, env={}, verbose=False, timeout=0):
    stdout_data = []
    stderr_data = []
    # Full cronological stdout/err output
    outdata_full = []

    def on_stdout(msg):
        nonlocal stdout_data, outdata_full
        stdout_data.append(msg)
        outdata_full.append(msg)
        logger.trace(msg.rstrip())

    def on_stderr(msg):
        nonlocal stderr_data, outdata_full
        stderr_data.append(msg)
        outdata_full.append(msg)
        logger.trace(msg.rstrip())

    if verbose:
        logger.trace(cmd)
    res = container.execute(
        login_shell
        + env_wrapper(env)
        + timeout_wrapper(timeout)
        + shlex.split(cmd),  # noqa 503
        stdout_handler=on_stdout,
        stderr_handler=on_stderr,
        stdin_payload=open(__file__),
    )
    if timeout and res.exit_code == 137:
        logger.warning("{} Timeout is reached (set to {})", cmd, timeout)
        raise TimeoutError
    elif res.exit_code:
        msg = "Failed to run command in the container! Command: \n"
        msg += cmd + " " + res.stderr
        # raise SystemExit(msg)
    return ExecuteResult(
        res.exit_code,
        "".join(stdout_data),
        "".join(stderr_data),
        "".join(outdata_full),
    )
