# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Jonathan Cave <jonathan.cave@canonical.com>

import json
import time

import requests_unixsocket


class AsyncException(Exception):

    def __init__(self, message, abort_message=''):
        self.message = message
        self.abort_message = abort_message


class Snapd():

    _url = 'http+unix://%2Frun%2Fsnapd.socket'

    _snaps = '/v2/snaps'
    _find = '/v2/find'
    _changes = '/v2/changes'
    _system_info = '/v2/system-info'
    _interfaces = '/v2/interfaces'
    _assertions = '/v2/assertions'

    def __init__(self, task_timeout=30, poll_interval=1, verbose=False):
        self._session = requests_unixsocket.Session()
        self._task_timeout = task_timeout
        self._poll_interval = poll_interval
        self._verbose = verbose

    def _info(self, msg):
        if self._verbose:
            print('(info) {}'.format(msg), flush=True)

    def _get(self, path, params=None, decode=True):
        r = self._session.get(self._url + path, params=params)
        r.raise_for_status()
        if decode:
            return r.json()
        return r

    def _post(self, path, data=None, decode=True):
        r = self._session.post(self._url + path, data=data)
        r.raise_for_status()
        if decode:
            return r.json()
        return r

    def _put(self, path, data=None, decode=True):
        r = self._session.put(self._url + path, data=data)
        r.raise_for_status()
        if decode:
            return r.json()
        return r

    def _poll_change(self, change_id):
        maxtime = time.time() + self._task_timeout
        while True:
            status = self.change(change_id)
            if status == 'Done':
                return True
            if time.time() > maxtime:
                abort_result = self._abort_change(change_id)
                raise AsyncException(status, abort_result)
            for task in self.tasks(change_id):
                if task['status'] == 'Doing':
                    self._info(task['summary'])
            time.sleep(self._poll_interval)

    def _abort_change(self, change_id):
        path = self._changes + '/' + change_id
        data = {'action': 'abort'}
        r = self._post(path, json.dumps(data))
        return r['result']['status']

    def list(self, snap=None):
        path = self._snaps
        if snap is not None:
            path += '/' + snap
        return self._get(path)['result']

    def install(self, snap, channel='stable', revision=None):
        path = self._snaps + '/' + snap
        data = {'action': 'install', 'channel': channel}
        if revision is not None:
            data['revision'] = revision
        r = self._post(path, json.dumps(data))
        if r['type'] == 'async' and r['status'] == 'Accepted':
            self._poll_change(r['change'])

    def remove(self, snap, revision=None):
        path = self._snaps + '/' + snap
        data = {'action': 'remove'}
        if revision is not None:
            data['revision'] = revision
        r = self._post(path, json.dumps(data))
        if r['type'] == 'async' and r['status'] == 'Accepted':
            self._poll_change(r['change'])

    def find(self, search, exact=False):
        if exact:
            p = 'name={}'.format(search)
        else:
            p = 'q={}'.format(search)
        return self._get(self._find, params=p)['result']

    def info(self, snap):
        return self.find(snap, exact=True)[0]

    def refresh(self, snap, channel='stable', revision=None):
        path = self._snaps + '/' + snap
        data = {'action': 'refresh', 'channel': channel}
        if revision is not None:
            data['revision'] = revision
        r = self._post(path, json.dumps(data))
        if r['type'] == 'async' and r['status'] == 'Accepted':
            self._poll_change(r['change'])

    def change(self, change_id):
        path = self._changes + '/' + change_id
        r = self._get(path)
        return r['result']['status']

    def tasks(self, change_id):
        path = self._changes + '/' + change_id
        r = self._get(path)
        return r['result']['tasks']

    def revert(self, snap, channel='stable', revision=None):
        path = self._snaps + '/' + snap
        data = {'action': 'revert', 'channel': channel}
        if revision is not None:
            data['revision'] = revision
        r = self._post(path, json.dumps(data))
        if r['type'] == 'async' and r['status'] == 'Accepted':
            self._poll_change(r['change'])

    def get_configuration(self, snap, key):
        path = self._snaps + '/' + snap + '/conf'
        p = 'keys={}'.format(key)
        return self._get(path, params=p)['result'][key]

    def set_configuration(self, snap, key, value):
        path = self._snaps + '/' + snap + '/conf'
        data = {key: value}
        r = self._post(path, json.dumps(data))
        if r['type'] == 'async' and r['status'] == 'Accepted':
            self._poll_change(r['change'])

    def interfaces(self):
        return self._get(self._interfaces)['result']

    def connect(self, slot_snap, slot_slot, plug_snap, plug_plug):
        data = {
            'action': 'connect',
            'slots': [{'snap': slot_snap, 'slot': slot_slot}],
            'plugs': [{'snap': plug_snap, 'plug': plug_plug}]
        }
        r = self._post(self._interfaces, json.dumps(data))
        if r['type'] == 'async' and r['status'] == 'Accepted':
            self._poll_change(r['change'])

    def get_assertions(self, assertion_type):
        path = self._assertions + '/' + assertion_type
        return self._get(path, decode=False)
