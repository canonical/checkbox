#!/usr/bin/env python3

# Copyright (C) 2012 Canonical, Ltd.

import re
import subprocess
import argparse
import sys


def get_time_difference(device):
    """
    Returns the difference in seconds between the last resume from suspend (S3)
    and the time it took to reconnect to Wifi.  If there is a problem finding
    the information, None is returned.
    """
    resume_time = get_resume_time()
    if resume_time is None:
        print("Unable to obtain wakeup/resume time from dmesg."
              "Please be sure the system has been suspended", file=sys.stderr)
        return None
    if device == "wifi":
        reconnect_times = list(get_wifi_reconnect_times())
    elif device == "wired":
        reconnect_times = list(get_wired_reconnect_times())

    if not reconnect_times:
        print("Unable to obtain %s connection time after a S3. Please be sure"
              " that the system has been suspended" % device, file=sys.stderr)
        return None

    # since some wifi & wired tests can disconnect and reconnect us multiple
    # times after a suspend, we need to find the reconnect that occurs
    # immediately after the resume from S3
    for reconnect_time in reconnect_times:
        if reconnect_time >= resume_time:
            return round((reconnect_time - resume_time), 2)
    return None


def get_wifi_reconnect_times():
    """
    Returns a list of all the timestamps for wifi reconnects.
    """
    data = subprocess.check_output(['dmesg'], universal_newlines=True)
    syntax = re.compile("\[(.*)\] wlan.* associated")
    results = re.findall(syntax, data)
    return map(float, results)

def get_wired_reconnect_times():
    """
    Returns a list of all the timestamps for wired reconnects.
    """
    data = subprocess.check_output(['dmesg'], universal_newlines=True)
    syntax = re.compile("\[(.*)\].*eth.* Link is [uU]p")
    results = re.findall(syntax, data)
    return map(float, results)


def get_resume_time():
    """
    Returns the last (most recent) timestamp for an ACPI resume from sleep (S3)
    If no resume is found, None is returned.
    """
    data = subprocess.check_output(['dmesg'], universal_newlines=True)
    syntax = re.compile("\[(.*)\].ACPI: Waking up from system sleep state S3")
    results = re.findall(syntax, data)
    if not results:
        return None
    else:
        return float(results[-1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--timeout',
                        type=int,
                        help="Specified max time allowed for Wifi/Wired to"
                             " reconnect in seconds",
                        required=True)
    parser.add_argument('-d', '--device',
                        help="Specify the device to test either,  eth or wlan",
                        required=True,
                        choices=['wifi', 'wired'])
    args = parser.parse_args()

    timedif = get_time_difference(args.device)
    
    if not timedif:
        return 0

    print("Your %s resumed in %s seconds after the last suspend" % (
        args.device, timedif))
    if timedif > args.timeout:
        print("FAIL: the network failed to reconnect within the allotted time")
        return 1
    else:
        print("PASS: the network connected within the allotted time")
        return 0

if __name__ == "__main__":
    sys.exit(main())
