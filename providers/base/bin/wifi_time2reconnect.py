#!/usr/bin/env python3

import os
import re
import sys
import time
import subprocess
from datetime import datetime
try:
    from subprocess import DEVNULL # >= python3.3
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')

IFACE = None
TIMEOUT = 30


def main():
    """
    Check the time needed to reconnect an active WIFI connection
    """
    devices = subprocess.getoutput('nmcli dev')
    match = re.search('(\w+)\s+(802-11-wireless|wifi)\s+connected', devices)
    if match:
        IFACE = match.group(1)
    else:
        print("No active wifi connection detected", file=sys.stderr)
        return 1

    try:
        dev_status = subprocess.check_output(
            ['nmcli', '-t', '-f', 'devices,uuid', 'con', 'status'],
            stderr=DEVNULL,
            universal_newlines=True)
    except subprocess.CalledProcessError:
        dev_status = subprocess.check_output(
            ['nmcli', '-t', '-f', 'device,uuid', 'con', 'show'],
            stderr=DEVNULL,
            universal_newlines=True)
    match = re.search(IFACE+':(.*)', dev_status)
    uuid = None
    if match:
        uuid = match.group(1)
    else:
        return 1

    subprocess.call(
        'nmcli dev disconnect iface %s' %IFACE,
        stdout=open(os.devnull, 'w'),
        stderr=subprocess.STDOUT,
        shell=True)

    time.sleep(2)
    start = datetime.now()

    subprocess.call(
        'nmcli con up uuid %s --timeout %s' %(uuid, TIMEOUT),
        stdout=open(os.devnull, 'w'),
        stderr=subprocess.STDOUT,
        shell=True)

    delta = datetime.now() - start
    print('%.2f Seconds' %delta.total_seconds())
    return 0


if __name__ == "__main__":
    sys.exit(main())
