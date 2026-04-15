# This file is part of Checkbox.
#
# Copyright 2019-2026 Canonical Ltd.
# Written by:
#    Jonathan Cave <jonathan.cave@canonical.com>
#    Massimiliano Girardi <massimiliano.girardi@canonical.com>
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

import http.client
import json
import socket
import time


class AsyncException(Exception):
    def __init__(self, message, abort_message=""):
        self.message = message
        self.abort_message = abort_message


class SnapdRequestError(Exception):
    def __init__(self, message, kind):
        self.message = message
        self.kind = kind

    @classmethod
    def from_response(cls, response_body):
        result = json.loads(response_body)["result"]
        return cls(result["message"], result.get("kind", ""))


class SnapdResponse:

    def __init__(self, headers, text):
        self.headers = headers
        self.text = text


class SnapdConnection(http.client.HTTPConnection):

    def __init__(self, sock_path="/run/snapd.socket"):
        super().__init__("localhost")
        self.sock_path = sock_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.sock_path)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Snapd:

    _snaps = "/v2/snaps"
    _find = "/v2/find"
    _changes = "/v2/changes"
    _system_info = "/v2/system-info"
    _interfaces = "/v2/interfaces"
    _assertions = "/v2/assertions"

    def __init__(self, task_timeout=30, poll_interval=1, verbose=False):
        self._task_timeout = task_timeout
        self._poll_interval = poll_interval
        self._verbose = verbose

    def _info(self, msg):
        if self._verbose:
            print("(info) {}".format(msg), flush=True)

    def _request(self, method, path, data=None, params=None, decode=True):
        if params:
            path = "{}?{}".format(path, params)
        with SnapdConnection() as conn:
            headers = {}
            if data is not None:
                headers["Content-Type"] = "application/json"
            conn.request(method, path, body=data, headers=headers)
            resp = conn.getresponse()
            body = resp.read().decode()
            if resp.status >= 400:
                raise SnapdRequestError.from_response(body)
            if decode:
                return json.loads(body)
            return SnapdResponse(resp.headers, body)

    def _get(self, path, params=None, decode=True):
        return self._request("GET", path, params=params, decode=decode)

    def _post(self, path, data=None, decode=True):
        return self._request("POST", path, data=data, decode=decode)

    def _put(self, path, data=None, decode=True):
        return self._request("PUT", path, data=data, decode=decode)

    def _poll_change(self, change_id):
        maxtime = time.time() + self._task_timeout
        while True:
            status = self.change(change_id)
            if status == "Done":
                return True
            if time.time() > maxtime:
                abort_result = self._abort_change(change_id)
                raise AsyncException(status, abort_result)
            for task in self.tasks(change_id):
                if task["status"] == "Doing":
                    if task["progress"]["label"]:
                        done = task["progress"]["done"]
                        total = task["progress"]["total"]
                        total_progress = done / total * 100
                        message = "({}) {} ({:.1f}%)".format(
                            task["status"], task["summary"], total_progress
                        )
                    else:
                        message = "({}) {}".format(
                            task["status"], task["summary"]
                        )
                    self._info(message)
                elif task["status"] == "Wait":
                    self._info(
                        "({}) {}".format(task["status"], task["summary"])
                    )
                    return
                elif task["status"] == "Error":
                    self._info(
                        "({}) {}".format(task["status"], task["summary"])
                    )
                    raise AsyncException(task.get("log"))
            time.sleep(self._poll_interval)

    def _abort_change(self, change_id):
        path = self._changes + "/" + change_id
        data = {"action": "abort"}
        r = self._post(path, json.dumps(data))
        return r["result"]["status"]

    def list(self, snap=None):
        path = self._snaps
        if snap is not None:
            path += "/" + snap
        try:
            return self._get(path)["result"]
        except SnapdRequestError as exc:
            if exc.kind == "snap-not-found":
                return None
            raise

    def install(self, snap, channel="stable", revision=None):
        path = self._snaps + "/" + snap
        data = {"action": "install", "channel": channel}
        if revision is not None:
            data["revision"] = revision
        r = self._post(path, json.dumps(data))
        if r["type"] == "async" and r["status"] == "Accepted":
            self._poll_change(r["change"])
        return r

    def remove(self, snap, revision=None):
        path = self._snaps + "/" + snap
        data = {"action": "remove"}
        if revision is not None:
            data["revision"] = revision
        r = self._post(path, json.dumps(data))
        if r["type"] == "async" and r["status"] == "Accepted":
            self._poll_change(r["change"])
        return r

    def find(self, search, exact=False):
        if exact:
            p = "name={}".format(search)
        else:
            p = "q={}".format(search)
        return self._get(self._find, params=p)["result"]

    def info(self, snap):
        return self.find(snap, exact=True)[0]

    def refresh(self, snap, channel="stable", revision=None, reboot=False):
        path = self._snaps + "/" + snap
        data = {"action": "refresh", "channel": channel}
        if revision is not None:
            data["revision"] = revision
        r = self._post(path, json.dumps(data))
        if r["type"] == "async" and r["status"] == "Accepted" and not reboot:
            self._poll_change(r["change"])
        return r

    def change(self, change_id):
        path = self._changes + "/" + change_id
        r = self._get(path)
        return r["result"]["status"]

    def tasks(self, change_id):
        path = self._changes + "/" + change_id
        r = self._get(path)
        return r["result"]["tasks"]

    def revert(self, snap, channel="stable", revision=None, reboot=False):
        path = self._snaps + "/" + snap
        data = {"action": "revert", "channel": channel}
        if revision is not None:
            data["revision"] = revision
        r = self._post(path, json.dumps(data))
        if r["type"] == "async" and r["status"] == "Accepted" and not reboot:
            self._poll_change(r["change"])
        return r

    def get_configuration(self, snap, key):
        path = self._snaps + "/" + snap + "/conf"
        p = "keys={}".format(key)
        return self._get(path, params=p)["result"][key]

    def set_configuration(self, snap, key, value):
        path = self._snaps + "/" + snap + "/conf"
        data = {key: value}
        r = self._post(path, json.dumps(data))
        if r["type"] == "async" and r["status"] == "Accepted":
            self._poll_change(r["change"])

    def interfaces(self):
        return self._get(self._interfaces)["result"]

    def connect_or_disconnect(
        self, slot_snap, slot_slot, plug_snap, plug_plug, action="connect"
    ):
        data = {
            "action": action,
            "slots": [{"snap": slot_snap, "slot": slot_slot}],
            "plugs": [{"snap": plug_snap, "plug": plug_plug}],
        }
        r = self._post(self._interfaces, json.dumps(data))
        if r["type"] == "async" and r["status"] == "Accepted":
            self._poll_change(r["change"])

    def connect(self, slot_snap, slot_slot, plug_snap, plug_plug):
        self.connect_or_disconnect(slot_snap, slot_slot, plug_snap, plug_plug)

    def disconnect(self, slot_snap, slot_slot, plug_snap, plug_plug):
        self.connect_or_disconnect(
            slot_snap,
            slot_slot,
            plug_snap,
            plug_plug,
            action="disconnect",
        )

    def get_assertions(self, assertion_type):
        path = self._assertions + "/" + assertion_type
        return self._get(path, decode=False)

    def get_system_info(self):
        return self._get(self._system_info)["result"]
