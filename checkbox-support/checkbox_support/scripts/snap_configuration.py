#!/usr/bin/env python3
# Copyright 2017 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Jonathan Cave <jonathan.cave@canonical.com>

import argparse
import sys

from checkbox_support.snap_utils.config import (get_configuration,
                                                set_configuration)


def main():
    desc = 'Query snapd for configuration details of an installed snap'
    parser = argparse.ArgumentParser(description=desc)

    subparsers = parser.add_subparsers(dest='action')
    subparsers.required = True

    parser_get = subparsers.add_parser('get', help='Get configuration item')
    parser_get.add_argument('snap', type=str, help='snap name')
    parser_get.add_argument('key', type=str, help='configuration item key')

    parser_set = subparsers.add_parser('set', help='Set configuration item')
    parser_set.add_argument('snap', type=str, help='snap name')
    parser_set.add_argument('key', type=str, help='configuration item key')
    parser_set.add_argument('value', type=str, help='new value')

    parser_test = subparsers.add_parser(
        'test', help='Test configuration item is set to the expected value')
    parser_test.add_argument('snap', type=str, help='snap name')
    parser_test.add_argument('key', type=str, help='configuration item key')
    parser_test.add_argument('expected_value', type=str,
                             help='the expected value')

    args = parser.parse_args()
    if args.action == 'get':
        value = get_configuration(args.snap, args.key)
        print(value)
    if args.action == 'set':
        result = set_configuration(args.snap, args.key, args.value)
        print(result)
    if args.action == 'test':
        print('Expected value: {}'.format(args.expected_value))
        value = get_configuration(args.snap, args.key)
        print('Value found on the {} snap: {}'.format(args.snap, value))
        if args.expected_value != value:
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
