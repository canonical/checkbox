#!/usr/bin/env python3
# Copyright 2017 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Jonathan Cave <jonathan.cave@canonical.com>

import json

import requests
import requests_unixsocket

SNAPD_BASE_URL = 'http+unix://%2Frun%2Fsnapd.socket'


class SnapdQuery():

    def __init__(self):
        self._session = requests_unixsocket.Session()

    def get(self, path, params=None):
        r = self._session.get(SNAPD_BASE_URL + path, params=params)
        if r.status_code != requests.codes.ok:
            raise SystemExit('Got error {} attempting to access {}\n'.format(
                r.status_code, path))
        return r

    def post(self, path, data=None):
        res = self._session.post(SNAPD_BASE_URL + path, data=data)
        if not res.ok:
            raise SystemExit('Got error {} attempting to post to {}\n'.format(
                res.status_code, path))
        return res.json()

    def put(self, path, data=None):
        res = self._session.put(SNAPD_BASE_URL + path, data=data)
        if not res.ok:
            raise SystemExit('Got error {} attempting to put to {}\n'.format(
                res.status_code, path))
        return res.json()


def _get_configuration(snap, key):
    path = '/v2/snaps/{}/conf'.format(snap)
    params = 'keys={}'.format(key)
    query = SnapdQuery()
    result = query.get(path, params).json()['result'][key]
    return result


def get_configuration(snap, key):
    result = _get_configuration(snap, key)
    print(result)


def set_configuration(snap, key, value):
    path = '/v2/snaps/{}/conf'.format(snap)
    json_data = json.dumps({key: value})
    query = SnapdQuery()
    result = query.put(path, json_data)['status']
    print(result)


def test_configuration(snap, key, expected_value):
    print('Expected value: {}'.format(expected_value))
    snap_value = _get_configuration(snap, key)
    print('Value found on the {} snap: {}'.format(snap, snap_value))
    if expected_value != snap_value:
        return 1
