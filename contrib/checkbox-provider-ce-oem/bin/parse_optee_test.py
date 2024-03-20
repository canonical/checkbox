#!/usr/bin/env python3

import json
import argparse
from look_up_xtest import look_up_xtest


def parse_json_file(filepath, filter=False, xtest=None):
    with open(filepath, 'r') as file:
        data = json.load(file)
    for test in data:
        if check_suite(test['suite'], filter):
            print_test_info(test, xtest)


def check_suite(suite, filter):
    if filter:
        return suite == 'pkcs11'
    else:
        return suite != 'pkcs11'


def print_test_info(test, xtest):
    print("suite: {}".format(test['suite']))
    print("test_id: {}".format(test['test_id']))
    print("description: {}".format(test['test_description']))
    print("tool: {}\n".format(xtest))


def main():
    parser = argparse.ArgumentParser(description='Parse a JSON file.')
    parser.add_argument('filepath',
                        help='The path of the file to parse.')
    parser.add_argument('-p', '--pkcs11',
                        help='To filter out PKCS11 for the suite.'
                        'field in JSON.',
                        action='store_true')
    args = parser.parse_args()
    try:
        xtest = look_up_xtest()
    except SystemExit:
        xtest = None
    parse_json_file(args.filepath, args.pkcs11, xtest)


if __name__ == "__main__":
    main()
