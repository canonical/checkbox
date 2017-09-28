#!/usr/bin/env python3
# Copyright 2017 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Jonathan Cave <jonathan.cave@canonical.com>

import argparse
import json
import sys

import requests
import requests_unixsocket

SNAPD_BASE_URL = 'http+unix://%2Frun%2Fsnapd.socket'


class SnapdQuery():

    def __init__(self):
        self._session = requests_unixsocket.Session()

    def get(self, path, params=None):
        r = self._session.get(SNAPD_BASE_URL + path, params=params)
        if r.status_code != requests.codes.ok:
            sys.stderr.write('Got error {} attempting to access {}\n'.format(
                r.status_code, path))
            sys.exit(1)
        return r

    def post(self, path, data=None):
        res = self._session.post(SNAPD_BASE_URL + path, data=data)
        if not res.ok:
            sys.stderr.write('Got error {} attempting to post to {}\n'.format(
                res.status_code, path))
            sys.exit(1)
        return res.json()

    def put(self, path, data=None):
        res = self._session.put(SNAPD_BASE_URL + path, data=data)
        if not res.ok:
            sys.stderr.write('Got error {} attempting to put to {}\n'.format(
                res.status_code, path))
            sys.exit(1)
        return res.json()


def _get_configuration(args):
    path = '/v2/snaps/{}/conf'.format(args.snap)
    params = 'keys={}'.format(args.key)
    query = SnapdQuery()
    result = query.get(path, params).json()['result'][args.key]
    return result


def get_configuration(args):
    result = _get_configuration(args)
    print(result)


def set_configuration(args):
    path = '/v2/snaps/{}/conf'.format(args.snap)
    json_data = json.dumps({args.key: args.value})
    query = SnapdQuery()
    result = query.put(path, json_data)['status']
    print(result)


def test_configuration(args):
    print('Expected value: {}'.format(args.expected_value))
    snap_value = _get_configuration(args)
    print('Value found on the {} snap: {}'.format(args.snap, snap_value))
    if args.expected_value != snap_value:
        return 1


def main():
    desc = 'Query snapd for configuration details of an installed snap'
    parser = argparse.ArgumentParser(description=desc)

    subparsers = parser.add_subparsers(dest='action')
    subparsers.required = True

    parser_get = subparsers.add_parser('get', help='Get configuration item')
    parser_get.add_argument('snap', type=str, help='snap name')
    parser_get.add_argument('key', type=str, help='configuration item key')
    parser_get.set_defaults(func=get_configuration)

    parser_set = subparsers.add_parser('set', help='Set configuration item')
    parser_set.add_argument('snap', type=str, help='snap name')
    parser_set.add_argument('key', type=str, help='configuration item key')
    parser_set.add_argument('value', type=str, help='new value')
    parser_set.set_defaults(func=set_configuration)

    parser_test = subparsers.add_parser(
        'test', help='Test configuration item is set to the expected value')
    parser_test.add_argument('snap', type=str, help='snap name')
    parser_test.add_argument('key', type=str, help='configuration item key')
    parser_test.add_argument('expected_value', type=str,
                             help='the expected value')
    parser_test.set_defaults(func=test_configuration)

    args = parser.parse_args()

    if args.func:
        sys.exit(args.func(args))


if __name__ == '__main__':
    sys.exit(main())
