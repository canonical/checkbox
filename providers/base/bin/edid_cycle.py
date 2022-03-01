#!/usr/bin/env python3
"""
This program tests whether the system changes the resolution automatically
when supplied with a new EDID information.

To run the test you need Zapper board connected and set up.

The command-line argument for the program is the address of the RaspberryPi
Host (optionally with a username), e.g.: ubuntu@192.168.1.100
"""
import os
import re
import subprocess
import sys
import time


def check_resolution():
    output = subprocess.check_output('xdpyinfo')
    for line in output.decode(sys.stdout.encoding).splitlines():
        if 'dimensions' in line:
            match = re.search(r'(\d+)x(\d+)\ pixels', line)
            if match and len(match.groups()) == 2:
                return '{}x{}'.format(*match.groups())


def change_edid(host, edid_file):
    with open(edid_file, 'rb') as f:
        cmd = ['ssh', host, '\'v4l2-ctl --set-edid=file=-,'
               'format=raw --fix-edid-checksums\'']
        subprocess.check_output(cmd, input=f.read())


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: {} user@edid-host'.format(sys.argv[0]))
    failed = False
    for res in ['2560x1440', '1920x1080', '1280x1024']:
        print('changing EDID to {}'.format(res))
        edid_file = os.path.expandvars(os.path.join(
            '$PLAINBOX_PROVIDER_DATA', 'edids', '{}.edid'.format(res)))
        change_edid(sys.argv[1], edid_file)
        time.sleep(1)
        print('checking resolution... ', end='')
        actual_res = check_resolution()
        if actual_res != res:
            print('FAIL, got {} instead'.format(actual_res))
            failed = True
        else:
            print('PASS')
    return failed


if __name__ == '__main__':
    raise SystemExit(main())
