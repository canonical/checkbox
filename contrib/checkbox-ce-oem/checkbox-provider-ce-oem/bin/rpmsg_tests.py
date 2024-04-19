#!/usr/bin/env python3

import argparse
import os
import sys
import time
import re
import subprocess
import shlex
import select
import logging
import threading
from systemd import journal
from pathlib import Path
import serial_test


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


class RpmsgPingPongTest:

    def __init__(
        self,
        kernel_module,
        probe_cmd,
        pingpong_event_pattern,
        pingpong_end_pattern,
        expected_count,
    ):
        self.kernel_module = kernel_module
        self.probe_cmd = probe_cmd
        self.pingpong_event_pattern = pingpong_event_pattern
        self.pingpong_end_pattern = pingpong_end_pattern
        self.expected_count = expected_count
        self._init_logger()

    def _init_logger(self):
        self.log_reader = journal.Reader()
        self.log_reader.this_boot()
        self.log_reader.seek_tail()
        self.log_reader.get_previous()

        self._poller = select.poll()
        self._poller.register(self.log_reader, self.log_reader.get_events())

    def lookup_pingpong_logs(self):
        keep_looking = True
        for entry in self.log_reader:
            logging.info(entry["MESSAGE"])
            if entry["MESSAGE"] == "":
                continue

            if re.search(self.pingpong_end_pattern, entry["MESSAGE"]):
                keep_looking = False
                break
            else:
                result = re.search(
                    self.pingpong_event_pattern, entry["MESSAGE"]
                )
                if result and result.groups()[0] in self.rpmsg_channels:
                    self.pingpong_events.append(entry["MESSAGE"])

        return keep_looking

    def monitor_journal_pingpong_logs(self):

        start_time = time.time()
        logging.info("# start time: %s", start_time)

        self.pingpong_events = []

        while self._poller.poll(1000):
            if self.log_reader.process() == journal.APPEND:
                if self.lookup_pingpong_logs() is False:
                    return self.pingpong_events

            cur_time = time.time()
            if (cur_time - start_time) > 60:
                return self.pingpong_events

    def pingpong_test(self):
        """
        Probe ping-pong kernel module for RPMSG ping-pong test

        Raises:
            SystemExit: if ping pong event count is not expected
        """

        logging.info("# Start ping pong test")
        # Unload module is needed
        try:
            logging.info("# Unload pingpong kernel module if needed")
            subprocess.run(
                "lsmod | grep {} && modprobe -r {}".format(
                    self.kernel_module, self.kernel_module
                ),
                shell=True,
            )
        except subprocess.CalledProcessError:
            pass

        self.rpmsg_channels = get_rpmsg_channel()

        try:
            thread = threading.Thread(
                target=self.monitor_journal_pingpong_logs
            )
            thread.start()
            logging.info("# probe pingpong module with '%s'", self.probe_cmd)

            subprocess.Popen(shlex.split(self.probe_cmd))
            thread.join()

            self._poller.unregister(self.log_reader)
            self.log_reader.close()
        except subprocess.CalledProcessError:
            pass

        logging.info("# check Ping pong records")
        if len(self.pingpong_events) != self.expected_count:
            logging.info(
                "ping-pong count is not match. expected %s, actual: %s",
                self.expected_count,
                len(self.pingpong_events),
            )
            raise SystemExit("The ping-pong message is not match.")
        else:
            logging.info("ping-pong logs count is match")


def pingpong_test(cpu_type):
    """
    RPMSG ping-pong test

    Raises:
        SystemExit: if ping pong event count is not expected
    """

    if cpu_type == "imx":
        test_obj = RpmsgPingPongTest(
            "imx_rpmsg_pingpong",
            "modprobe imx_rpmsg_pingpong",
            r"get .* \(src: (\w*)\)",
            r"rpmsg.*: goodbye!",
            51,
        )
    elif cpu_type == "ti":
        test_obj = RpmsgPingPongTest(
            "rpmsg_client_sample",
            "modprobe rpmsg_client_sample count=100",
            r".*ti.ipc4.ping-pong.*\(src: (\w*)\)",
            r"rpmsg.*: goodbye!",
            100,
        )
    else:
        raise SystemExit("Unexpected CPU type.")

    test_obj.pingpong_test()


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
        serial_dev = serial_test.Serial(
            str(rpmsg_devs[0]), "rpmsg-tty", [], 115200, 8, "N", 1, 3, 1024
        )
        serial_test.client_mode(serial_dev, data_size)
    else:
        raise SystemExit("No RPMSG TTY devices found.")


def register_arguments():
    parser = argparse.ArgumentParser(description="RPMSG related test")
    parser.add_argument(
        "--type",
        help="RPMSG tests",
        required=True,
        choices=["detect", "pingpong", "serial-tty"],
    )
    return parser.parse_args()


def main(args):
    if args.type == "detect":
        check_rpmsg_device()
    elif args.type == "pingpong":
        pingpong_test(detect_arm_processor_type())
    elif args.type == "serial-tty":
        serial_tty_test(detect_arm_processor_type(), 1024)


if __name__ == "__main__":

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

    main(register_arguments())
