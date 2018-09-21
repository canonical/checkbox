#!/usr/bin/env python3
# Copyright 2017 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>

"""
This program connects snap plugs and lists connections between snaps.

The syntax of program parameters is A:B:C, where :

    A - plug to be connected
    B - target snap (snap the plug will connect to)
    C - target slot (slot to connect to)

    Note that originating snap is implied. $SNAP_NAME is used.

Example:
    $ sudo ./snap_connect.py udisks2:udisks2:service

running
    $ sudo ./snap_connect.py A:B:C
is equivalent to:
    $ snap connect $SNAP_NAME:A B:C

    Note that the program needs sudo if asked to connect plugs.
"""

import argparse
import json
import logging
import requests_unixsocket
import os
import sys
import time
from collections import namedtuple


Connection = namedtuple(
    'Connection',
    ['target_snap', 'target_slot', 'plug_snap', 'plug_plug'])


class BadRequest(Exception):
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'connections', nargs='+', default=[],
        metavar='plug:target_snap:target_slot')
    args = parser.parse_args()
    api = SnapdAPI()

    for conn in [spec.split(':') for spec in args.connections]:
        if len(conn) != 3:
            raise SystemExit("Bad connection description")
        assert os.environ['SNAP_NAME']
        snap = os.environ['SNAP_NAME']
        existing_connections = api.get_connections()
        new_connection = Connection(
            target_snap=conn[1], target_slot=conn[2],
            plug_snap=snap, plug_plug=conn[0])
        if new_connection not in existing_connections:
            try:
                api.connect(new_connection)
            except BadRequest as exc:
                logging.warning("Failed to connect %s to %s. %s" % (
                    conn[0], conn[1], exc))


class SnapdAPI():
    """Based on https://github.com/snapcore/snapd/wiki/REST-API"""
    SNAPD_BASE_URL = 'http+unix://%2Frun%2Fsnapd.socket'

    def __init__(self):
        self.session = requests_unixsocket.Session()

    def get_connections(self):
        data = self._get('/v2/interfaces')
        connections = []
        if 'plugs' in data:
            for plug in data['plugs']:
                if 'connections' in plug:
                    for con in plug['connections']:
                        connections.append(Connection(
                            con['snap'], con['slot'],
                            plug['snap'], plug['plug']))
        return connections

    def connect(self, con):
        json_data = json.dumps({
            'action': 'connect',
            'slots': [{'snap': con.target_snap, 'slot': con.target_slot}],
            'plugs': [{'snap': con.plug_snap, 'plug': con.plug_plug}]
        })
        res = self._post('/v2/interfaces', json_data)
        ready = False
        while not ready:
            # busy wait until snapd reports connection job as finised
            time.sleep(0.5)
            con_res = self._get('/v2/changes/{}'.format(res['change']))
            ready = con_res['ready']

    def _get(self, path):
        res = self.session.get(self.SNAPD_BASE_URL + path)
        if not res.ok:
            logging.error("Got error %i attempting to access %s",
                          res.status_code, path)
            sys.exit(1)
        return res.json()['result']

    def _post(self, path, data=None):
        res = self.session.post(self.SNAPD_BASE_URL + path, data=data)
        if not res.ok:
            full_res = json.loads(res.text)
            if res.status_code == 400:
                raise BadRequest(full_res['result']['message'])
            logging.error("Got error %i attempting to access %s",
                          res.status_code, path)
            sys.exit(1)
        return res.json()


if __name__ == '__main__':
    main()
