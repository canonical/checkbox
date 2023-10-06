#!/usr/bin/env python3

import argparse
import datetime
import os
import re
import subprocess
import select
from systemd import journal


RPMSG_ROOT = "/sys/bus/rpmsg/devices"
SOC_ROOT = "/sys/devices/soc0"


def check_rpmsg_device():
    """
    Validate the RPMSG device is available

    Raises:
        SystemExit: exit if no rpmsg_devices is available

    Returns:
        rpmsg_devices (list): a list of RPMSG device path
    """
    print("## Checking RPMSG device is available ...")

    rpmsg_devices = os.listdir(RPMSG_ROOT)
    if not rpmsg_devices:
        raise SystemExit("RPMSG device is not available")
    else:
        print("RPMSG device is available")

    return rpmsg_devices


def get_rpmsg_channel():
    """
    Get all of the RPMSG destination channel

    Raises:
        SystemExit: if rpmsg_channels is empty

    Returns:
        rpmsg_channels (list): a list of RPMSG destination channel
    """
    print("## Checking RPMSG channel ...")

    rpmsg_channels = []
    rpmsg_devices = check_rpmsg_device()
    for file_obj in rpmsg_devices:
        tmp_file = os.path.join(RPMSG_ROOT, file_obj, "dst")
        if os.path.isfile(tmp_file):
            with open(tmp_file, "r") as fp:
                rpmsg_channels.append(fp.read().strip("\n"))

    if rpmsg_channels:
        print("Available RPMSG channels is {}".format(rpmsg_channels))
    else:
        raise SystemExit("RPMSG channel is not created")

    return rpmsg_channels


def get_soc_family():
    """
    Read data from /sys/devices/soc0/family

    Returns:
        soc_family (str): SoC family.
    """
    soc_family = ""
    path = os.path.join(SOC_ROOT, "family")
    if os.path.isfile(path):
        with open(path, "r") as fp:
            soc_family = fp.read().strip()

    print("SoC family is {}".format(soc_family))
    return soc_family


def get_soc_machine():
    """
    Read data from /sys/devices/soc0/machine

    Returns:
        soc_machine (str): SoC machine.
    """
    soc_machine = ""
    path = os.path.join(SOC_ROOT, "machine")
    if os.path.isfile(path):
        with open(path, "r") as fp:
            soc_machine = fp.read().strip()

    print("SoC machine is {}".format(soc_machine))
    return soc_machine


def detect_arm_processor_type():
    """
    Check the ARM processor manufacturer

    Returns:
        arm_cpu_type (str): ARM CPU type. E.g. ti, imx
    """
    family = get_soc_family()
    machine = get_soc_machine()
    print("SoC family is {}, machine is {}".format(family, machine))

    if "i.MX" in family or "i.MX" in machine:
        arm_cpu_type = "imx"
    elif "Texas Instruments" in machine:
        arm_cpu_type = "ti"
    else:
        arm_cpu_type = "unknown"

    return arm_cpu_type


def pingpong_test(cpu_type):
    """
    Probe ping-pong kernel module for RPMSG ping-pong test

    Raises:
        SystemExit: if ping pong event count is not expected
    """

    print("## Probe pingpong kernel module")
    if cpu_type == "imx":
        kernel_module = "imx_rpmsg_pingpong"
        probe_cmd = "modprobe {}".format(kernel_module)
        check_pattern = r"get .* \(src: (\w*)\)"
        expected_count = 51
    elif cpu_type == "ti":
        kernel_module = "rpmsg_client_sample"
        probe_cmd = "modprobe {} count=100".format(kernel_module)
        check_pattern = r".*ti.ipc4.ping-pong.*src: (\w*)\)"
        expected_count = 100
    else:
        raise SystemExit("Unexpected CPU type.")
    rpmsg_end_pattern = "rpmsg.*: goodbye!"

    # Unload module is needed
    try:
        subprocess.run(
            "lsmod | grep {} && modprobe -r {}".format(
                kernel_module, kernel_module),
            shell=True
        )
    except subprocess.CalledProcessError:
        pass

    rpmsg_channels = get_rpmsg_channel()

    log_reader = journal.Reader()
    log_reader.seek_tail()
    log_reader.get_previous()

    poll = select.poll()
    poll.register(log_reader, log_reader.get_events())

    start_time = datetime.datetime.now()
    print("# start time: {}".format(start_time))
    print("# probe pingpong module with '{}'".format(probe_cmd))
    try:
        subprocess.run(probe_cmd, shell=True)
    except subprocess.CalledProcessError:
        pass

    pingpong_events = []
    needed_break = False
    while poll.poll():
        if log_reader.process() != journal.APPEND:
            continue

        for entry in log_reader:
            print(entry["MESSAGE"])
            if entry["MESSAGE"] == "":
                continue

            search_end = re.search(rpmsg_end_pattern, entry["MESSAGE"])
            search_pattern = re.search(check_pattern, entry["MESSAGE"])
            cur_time = datetime.datetime.now()

            if search_pattern and search_pattern.groups()[0] in rpmsg_channels:
                pingpong_events.append(entry["MESSAGE"])
            elif search_end or (cur_time - start_time).total_seconds() > 60:
                needed_break = True
                break

        if needed_break:
            break

    print("## Check Ping pong test is finish")

    if len(pingpong_events) != expected_count:
        print(
            "ping-pong count is not match. expected {}, actual: {}".format(
                expected_count, len(pingpong_events))
        )
        raise SystemExit("The ping-pong message is not match.")
    else:
        print("ping-pong logs count is match")


def main():
    parser = argparse.ArgumentParser(description='RPMSG related test')
    parser.add_argument('--type',
                        help='To filter out PKCS11 for the suite',
                        choices=["detect", "pingpong"])
    args = parser.parse_args()

    if args.type == "detect":
        check_rpmsg_device()
    elif args.type == "pingpong":
        pingpong_test(detect_arm_processor_type())


if __name__ == "__main__":
    main()
