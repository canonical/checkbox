#!/usr/bin/env python3

import argparse
import datetime
import os
import sys
import re
import subprocess
import select
import logging
from systemd import journal
from pathlib import Path
from serial_test import serial_init, client_mode


def init_logger():
    """
    Set the logger to log DEBUG and INFO to stdout, and
    WARNING, ERROR, CRITICAL to stderr.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logger_format = "%(asctime)s %(levelname)-8s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stdout_handler.setLevel(logging.DEBUG)
    stderr_handler.setLevel(logging.WARNING)

    # Add a filter to the stdout handler to limit log records to
    # INFO level and below
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(stdout_handler)

    return root_logger


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
    logging.info("## Checking RPMSG device is available ...")

    rpmsg_devices = os.listdir(RPMSG_ROOT)
    if not rpmsg_devices:
        raise SystemExit("RPMSG device is not available")
    else:
        logging.info("RPMSG device is available")

    return rpmsg_devices


def get_rpmsg_channel():
    """
    Get all of the RPMSG destination channel

    Raises:
        SystemExit: if rpmsg_channels is empty

    Returns:
        rpmsg_channels (list): a list of RPMSG destination channel
    """
    logging.info("## Checking RPMSG channel ...")

    rpmsg_channels = []
    rpmsg_devices = check_rpmsg_device()
    for file_obj in rpmsg_devices:
        tmp_file = os.path.join(RPMSG_ROOT, file_obj, "dst")
        if os.path.isfile(tmp_file):
            with open(tmp_file, "r") as fp:
                rpmsg_channels.append(fp.read().strip("\n"))

    if rpmsg_channels:
        logging.info("Available RPMSG channels is %s", rpmsg_channels)
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

    logging.info("SoC family is %s", soc_family)
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

    logging.info("SoC machine is %s", soc_machine)
    return soc_machine


def detect_arm_processor_type():
    """
    Check the ARM processor manufacturer

    Returns:
        arm_cpu_type (str): ARM CPU type. E.g. ti, imx
    """
    family = get_soc_family()
    machine = get_soc_machine()
    logging.info("SoC family is %s, machine is %s", family, machine)

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

    logging.info("## Probe pingpong kernel module")
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
                kernel_module, kernel_module
            ),
            shell=True,
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
    logging.info("# start time: %s", start_time)
    logging.info("# probe pingpong module with '%s'", probe_cmd)
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
            logging.info(entry["MESSAGE"])
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

    logging.info("## Check Ping pong test is finish")
    if len(pingpong_events) != expected_count:
        logging.info(
            "ping-pong count is not match. expected %s, actual: %s",
            expected_count,
            len(pingpong_events),
        )
        raise SystemExit("The ping-pong message is not match.")
    else:
        logging.info("ping-pong logs count is match")


def rpmsg_tty_test_supported(cpu_type):
    """Validate the RPMSG TTY test is supported,
    the probe driver command and RPMSG-TTY device pattern will return

    Args:
        cpu_type (str): the SoC type

    Raises:
        SystemExit: If CPU is not expected

    Returns:
        check_pattern (str): the pattern of RPMSG-TTY device
        probe_cmd (str): the command to probe RPMSG-TTY driver
    """
    if cpu_type == "imx":
        probe_cmd = "modprobe imx_rpmsg_tty"
        check_pattern = r"ttyRPMSG[0-9]*"
    elif cpu_type == "ti":
        # To DO: verify it while we have a system
        # Following configuration is for TI platform
        # But we don't have platform to ensure it is working
        #
        # probe_cmd = "modprobe rpmsg_pru"
        # check_pattern = r"rpmsg_pru[0-9]*"
        raise SystemExit("Unsupported method for TI.")
    else:
        raise SystemExit("Unexpected CPU type.")

    return check_pattern, probe_cmd


def check_rpmsg_tty_devices(path_obj, pattern, probe_command):
    """
    Detect the RPMSG TTY devices, probe module might be executed if needed

    Args:
        path_obj (Path): a Path object
        pattern (str): the pattern of RPMSG devices
        probe_command (str): command of probe RPMSG TTY module

    Returns:
        list(Path()): a list of Path object
    """
    rpmsg_devices = sorted(path_obj.glob(pattern))
    if not rpmsg_devices:
        logging.info("probe rpmsg-tty kernel module")
        try:
            subprocess.run(probe_command, shell=True)
        except subprocess.CalledProcessError:
            pass
        rpmsg_devices = sorted(path_obj.glob(pattern))

    return rpmsg_devices


def serial_tty_test(cpu_type, data_size):
    """
    Probe rpmsg-tty kernel module for RPMSG TTY test

    Raises:
        SystemExit: in following condition
            - CPU type is not supported or
            - RPMSG TTY device is not exists or
            - no data received from serial device
            - received data not match
    """
    logging.info("# Start string-echo test for RPMSG TTY device")

    check_pattern, probe_cmd = rpmsg_tty_test_supported(cpu_type)
    path_obj = Path("/dev")
    rpmsg_devs = check_rpmsg_tty_devices(path_obj, check_pattern, probe_cmd)
    if rpmsg_devs:
        client_mode(serial_init(str(rpmsg_devs[0])), data_size)
    else:
        raise SystemExit("No RPMSG TTY devices found.")


def main():
    parser = argparse.ArgumentParser(description="RPMSG related test")
    parser.add_argument(
        "--type",
        help="RPMSG tests",
        required=True,
        choices=["detect", "pingpong", "serial-tty"],
    )
    args = parser.parse_args()
    init_logger()

    if args.type == "detect":
        check_rpmsg_device()
    elif args.type == "pingpong":
        pingpong_test(detect_arm_processor_type())
    elif args.type == "serial-tty":
        serial_tty_test(detect_arm_processor_type(), 1024)


if __name__ == "__main__":
    main()
