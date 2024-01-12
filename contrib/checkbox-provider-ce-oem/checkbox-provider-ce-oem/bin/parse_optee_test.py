#!/usr/bin/env python3

import json
import argparse


def parse_json_file(filename, filter=False):
    with open(filename, 'r') as file:
        data = json.load(file)
    for test in data:
        if (filter and test['suite'] == 'pkcs11') or \
           (not filter and test['suite'] not in ['pkcs11']):
            print_test_info(test)


def print_test_info(test):
    print("suite: {}".format(test['suite']))
    print("test_id: {}".format(test['test_id']))
    print("description: {}\n".format(test['test_description']))


def main():
    parser = argparse.ArgumentParser(description='Parse a JSON file.')
    parser.add_argument('filename', help='The name of the file to parse.')
    parser.add_argument('-p', '--pkcs11',
                        help='To filter out PKCS11 for the suite'
                        'field in JSON.',
                        action='store_true')
    args = parser.parse_args()
    parse_json_file(args.filename, args.pkcs11)


if __name__ == "__main__":
    main()
