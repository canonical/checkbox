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

from contextlib import suppress
from subprocess import CalledProcessError

from urllib import parse
from loguru import logger
import metabox.core.keys as keys
from metabox.core.utils import ExecuteResult
from ws4py.client.threadedclient import WebSocketClient
from metabox.core.utils import _re
from pylxd.models.operation import Operation


base_env = {
    "PYTHONUNBUFFERED": "1",
    "DISABLE_URWID_ESCAPE_CODES": "1",
    "XDG_RUNTIME_DIR": "/run/user/1000",
}
login_shell = ["sudo", "--user", "ubuntu", "--login"]


class SafeWebSocketClient(WebSocketClient):
    def __init__(self, *args, resource="", **kwargs):
        super().__init__(*args, **kwargs)
        self.resource = resource

    def send(self, *args, **kwargs):
        """
        This makes it so send will raise ConnectionError when send fails
        """
        # there is a race condition in the base WebSocketClient that leads
        # calls to send on terminated connections to raise an AttributeError.
        # This mainly happens when the process crashes in an unexpected step
        try:
            return super().send(*args, **kwargs)
        except AttributeError as e:
            raise ConnectionError("Unable to send, process crashed") from e


class InteractiveWebsocket(SafeWebSocketClient):
    # https://stackoverflow.com/a/14693789/1154487
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def __init__(
        self,
        cmd,
        *args,
        ctl=None,
        verbose=False,
        container=None,
        operation_id=0,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.cmd = cmd
        self.ctl = ctl
        self.verbose = verbose
        self.container = container
        self.operation_id = operation_id

        self.stdout_data: str = ""
        self.stdout_data_full: str = ""
        self.stdout_lock = threading.Lock()
        self._new_data = False
        self._lookup_by_id = False
        self._connection_closed = False
        self.result = None
        self._result_lock = threading.Lock()

    def received_message(self, message):
        if len(message.data) == 0:
            self.close()
            self._connection_closed = True
        message_data_str = message.data.decode("utf-8", errors="ignore")
        raw_msg = message_data_str = self.ansi_escape.sub("", message_data_str)
        if self.verbose:
            logger.trace(raw_msg.rstrip())
        with self.stdout_lock:
            self.stdout_data += message_data_str
            self.stdout_data_full += message_data_str
            self._new_data = True

    def result_fetching_daemon(self):
        while True:
            operation = self.client.operations.get(self.operation_id)
            try:
                result = operation.metadata["return"]
                # don't get the lock when the operation fails
                with self._result_lock:
                    self.result = result
                return
            except KeyError:
                time.sleep(0.1)

    def check(self, timeout=0):
        deadline = time.time() + timeout
        while True:
            with self._result_lock:
                result = self.result
            if result == 0:
                return True
            elif result == 137:
                raise TimeoutError(
                    f"Timeout expired while waiting for cmd: '{self.cmd}'"
                )
            elif result is not None:
                raise CalledProcessError(
                    result, self.cmd, output=self.stdout_data_full
                )
            elif timeout and time.time() > deadline:
                raise TimeoutError(
                    "Check timeout has expired, unable to fetch result"
                )
            time.sleep(0.1)

    def connect(self):
        result_fetcher = threading.Thread(
            target=self.result_fetching_daemon, daemon=True
        )
        result_fetcher.start()
        super().connect()

    def get_search_split(self, search_pattern):
        if isinstance(search_pattern, _re):
            search = search_pattern.search
            split_first = search_pattern.split
        elif isinstance(search_pattern, str):

            def search(buffer):
                return search_pattern in buffer

            def split_first(buffer):
                return buffer.split(search_pattern, maxsplit=1)

        else:
            raise TypeError(
                "Unsupported search pattern type: {}".format(
                    type(search_pattern)
                )
            )

        return (search, split_first)

    def expect(self, pattern, timeout=0):
        found = False
        start_time = time.time()

        search, split_first = self.get_search_split(pattern)

        while not found:
            time.sleep(0.1)
            check = search(self.stdout_data)
            if check:
                # truncate the history because subsequent expect should not
                # re-match the same text
                with self.stdout_lock:
                    self.stdout_data = split_first(self.stdout_data)[-1]
                found = True
            elif timeout and time.time() > start_time + timeout:
                msg = "'{}' not found! Timeout is reached (set to {})".format(
                    pattern, timeout
                )
                raise TimeoutError(msg)
            elif self._connection_closed:
                # this could have been updated from the other thread, lets
                # check before exiting the loop
                found = found or search(self.stdout_data)
                break
        return found

    def expect_not(self, data, timeout=0):
        with suppress(TimeoutError):
            return not self.expect(data, timeout)
        return True

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
        old_stdout_data = ""
        postfix = data[:-6]  # used to search
        self.send(f"/{postfix}\ni".encode("utf8"), binary=True)
        if len(data) > 67:
            data = data[:67] + "   │\r\n│        " + data[67:]
        while attempt < max_attemps:
            if self._new_data and self.stdout_data:
                if old_stdout_data == self.stdout_data:
                    break
                check = data in self.stdout_data
                if not check:
                    self._new_data = False
                    with self.stdout_lock:
                        old_stdout_data = self.stdout_data
                        self.stdout_data = ""
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
                check = data in self.stdout_data
                if not check:
                    self._new_data = False
                    with self.stdout_lock:
                        self.stdout_data = ""
                    stdin_payload = keys.KEY_UP + keys.KEY_SPACE
                    self.send(stdin_payload.encode("utf-8"), binary=True)
                    attempt = 0
                else:
                    not_found = False
                    with self.stdout_lock:
                        self.stdout_data = ""
                    break
            else:
                time.sleep(0.1)
                attempt += 1
        return not_found is False

    def send_signal(self, signal):
        self.ctl.send(json.dumps({"command": "signal", "signal": signal}))


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
    ws_urls = raw_interactive_execute(
        container,
        timeout_wrapper(timeout) + shlex.split(cmd),
        environment=env,
        user=1000,
    )

    base_websocket_url = container.client.websocket_url
    ctl = SafeWebSocketClient(base_websocket_url, resource=ws_urls["control"])
    ctl.connect()
    pts = InteractiveWebsocket(
        cmd,
        base_websocket_url,
        ctl=ctl,
        verbose=verbose,
        container=container,
        operation_id=ws_urls["operation_id"],
        resource=ws_urls["ws"],
    )
    pts.client = container.client
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


# https://github.com/canonical/pylxd/blob/main/pylxd/models/instance.py#L526
# Fork of the upstream raw_interactive_execute that also returns the
# operation_id, we need this to query the outcome of a command in interactive
# mode, we have to do this instead of use execute because it doesn't support to
# interactively send commands, even the stdio parameter fd is read whole
# before sending it
def raw_interactive_execute(
    container, commands, environment=None, user=None, group=None, cwd=None
):
    if environment is None:
        environment = {}

    response = container.api["exec"].post(
        json={
            "command": commands,
            "environment": environment,
            "wait-for-websocket": True,
            "interactive": True,
            "user": user,
            "group": group,
            "cwd": cwd,
        }
    )

    fds = response.json()["metadata"]["metadata"]["fds"]
    operation_id = response.json()["operation"].split("/")[-1].split("?")[0]
    parsed = parse.urlparse(
        container.client.api.operations[operation_id].websocket._api_endpoint
    )

    return {
        "ws": f"{parsed.path}?secret={fds['0']}",
        "control": f"{parsed.path}?secret={fds['control']}",
        "operation_id": Operation.extract_operation_id(operation_id),
    }
