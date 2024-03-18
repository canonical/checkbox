#!/usr/bin/env python3

import json
import argparse
import subprocess as sp
import shlex
import re
from checkbox_support.snap_utils.snapd import Snapd
from checkbox_support.snap_utils.system import get_gadget_snap


def parse_json_file(filepath, filter=False, xtest=None):
    with open(filepath, 'r') as file:
        data = json.load(file)
    for test in data:
        if (filter and test['suite'] == 'pkcs11') or \
           (not filter and test['suite'] not in ['pkcs11']):
            print_test_info(test, xtest)


def print_test_info(test, xtest):
    print("suite: {}".format(test['suite']))
    print("test_id: {}".format(test['test_id']))
    print("description: {}".format(test['test_description']))
    print("tool: {}\n".format(xtest))


def look_up_xtest():
    if Snapd().list("x-test"):
        xtest = "x-test.xtest"
    elif look_up_gadget() is not False:
        xtest = look_up_gadget()
    else:
        xtest = None
    return xtest


def look_up_gadget():
    gadget = get_gadget_snap()
    cmd = "snap info {}".format(gadget)
    gadget_info = sp.run(shlex.split(cmd),
                         stdout=sp.PIPE,
                         stderr=sp.PIPE,
                         text=True,
                         timeout=10)
    xtest = "{}.xtest".format(gadget)
    if re.findall(xtest, gadget_info.stdout):
        return xtest
    else:
        return False


def main():
    parser = argparse.ArgumentParser(description='Parse a JSON file.')
    parser.add_argument('-f', '--filepath',
                        help='The path of the file to parse.')
    parser.add_argument('-p', '--pkcs11',
                        help='To filter out PKCS11 for the suite.'
                        'field in JSON.',
                        action='store_true')
    args = parser.parse_args()
    xtest = look_up_xtest()
    if args.filepath is None:
        print(xtest)
    else:
        parse_json_file(args.filepath, args.pkcs11, xtest)


if __name__ == "__main__":
    main()
