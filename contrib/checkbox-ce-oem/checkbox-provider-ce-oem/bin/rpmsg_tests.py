#!/usr/bin/env python3
import argparse
import os
import sys
import time
import re
import subprocess
import logging
import threading
import glob
from pathlib import Path
import serial_test


SOC_ROOT = "/sys/devices/soc0"
REMOTEPROC_PATH = "/sys/class/remoteproc"


class RpmsgSysFsHandler:

    properties = ["firmware_path", "firmware_file", "rpmsg_state"]

    def __init__(self, remoteproc_dir):
        root_path = os.path.join(REMOTEPROC_PATH, remoteproc_dir)
        self.sysfs_fw_path = "/sys/module/firmware_class/parameters/path"
        self.sysfs_firmware_file = os.path.join(root_path, "firmware")
        self.sysfs_state_path = os.path.join(root_path, "state")
        self.original_firmware_path = None
        self.original_firmware = None
        self.original_state = None
        self.started_by_script = False

        if not os.path.isdir(root_path):
            logging.error(
                "Error: Remoteproc directory not found at '%s'", root_path
            )
            raise SystemExit(1)

    def _read_node(self, path):
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except IOError as e:
            logging.error("Error reading from %s: %s", path, e)
            return None

    def _write_node(self, path, value):
        """Helper to write to a sysfs node."""
        try:
            with open(path, "w") as f:
                f.write(value)
            logging.debug("Wrote '%s' to %s", value, path)
            return True
        except IOError as e:
            logging.error("Error writing to '%s': %s", path, e)
            raise

    @property
    def firmware_path(self):
        return self._read_node(self.sysfs_fw_path)

    @firmware_path.setter
    def firmware_path(self, value: str):
        logging.info("Update firmware path: %s", value)
        self._write_node(self.sysfs_fw_path, value)

    @property
    def firmware_file(self):
        return self._read_node(self.sysfs_firmware_file)

    @firmware_file.setter
    def firmware_file(self, value: str):
        logging.info("Loading new firmware: %s", value)
        self._write_node(self.sysfs_firmware_file, value)

    @property
    def rpmsg_state(self):
        """
        Reports the state of the remote processor, which will be one of:

        - "offline"
        - "suspended"
        - "running"
        - "crashed"
        - "invalid"

        "offline" means the remote processor is powered off.
        "suspended" means that the remote processor is suspended and
        must be woken to receive messages.
        "running" is the normal state of an available remote processor
        "crashed" indicates that a problem/crash has been detected on
        the remote processor.
        "invalid" is returned if the remote processor is in an
        unknown state.

        Returns:
            str: remote processor state
        """
        return self._read_node(self.sysfs_state_path)

    @rpmsg_state.setter
    def rpmsg_state(self, value: str):
        """
        Writing this file controls the state of the remote processor.

        The following states can be written:
        - "start"
        - "stop"

        Writing "start" will attempt to start the processor running the
        firmware indicated by, or written to,
        /sys/class/remoteproc/.../firmware. The remote processor should
        transition to "running" state.

        Writing "stop" will attempt to halt the remote processor and
        return it to the "offline" state.

        Returns:
            None
        """
        if value not in ["start", "stop"]:
            raise ValueError("Unsupported value for remote processor state")
        self._write_node(self.sysfs_state_path, value)

    def setup(self):
        """Reads and stores the initial firmware configuration and state"""
        self.original_firmware_path = self.firmware_path
        if self.original_firmware_path is not None:
            logging.info(
                "Original firmware path was: %s", self.original_firmware_path
            )
        else:
            logging.warning("Could not read original firmwar path.")

        self.original_firmware = self.firmware_file
        if self.original_firmware is not None:
            logging.info("Original firmware was: %s", self.original_firmware)
        else:
            logging.warning("Could not read original firmware.")

        self.original_state = self.rpmsg_state
        if self.original_state:
            logging.info("Original state was: %s", self.original_state)
        else:
            logging.warning("Could not read original state.")

    def teardown(self):
        """Restores the initial firmware configuration."""
        if self.original_firmware is not None:
            if self.rpmsg_state == "running":
                self.stop()
                time.sleep(1)  # Give it a moment to stop

            logging.info(
                "Restoring original firmware: %s", self.original_firmware
            )
            self.firmware_file = self.original_firmware
        else:
            logging.info("No original firmware to restore.")

        if self.original_firmware_path is not None:
            logging.info(
                "Restoring original firmware path: %s",
                self.original_firmware_path,
            )
            self.firmware_path = self.original_firmware_path
        else:
            logging.info("No original firmware path to restore.")

        # Only restart if it was not started by this script
        #   and was running before
        if not self.started_by_script and self.original_state == "running":
            self.start()
        logging.info("Cleanup complete.")

    def start(self):
        if self.rpmsg_state == "running":
            logging.info("Remoteproc is already running.")
            return True
        self.started_by_script = True
        self.rpmsg_state = "start"
        return True

    def stop(self):
        if self.rpmsg_state == "offline":
            logging.info("Remoteproc is already offline.")
            return True
        self.rpmsg_state = "stop"
        return True


class RpmsgTest:
    def __init__(
        self, rpmsg_node, load_firmware, firmware_path, firmware_file
    ):
        self._test_func = None
        self.kernel_module = None
        self.probe_cmd = None

        self.rpmsg_node = rpmsg_node
        self.handler = RpmsgSysFsHandler(self.rpmsg_node)
        self.firmware_name = firmware_file
        self.firmware_path = firmware_path
        self.should_load_firmware = load_firmware
        self.log_reader = None

        self.expected_events = []

    def unload_module(self):
        # Unload module is needed
        try:
            logging.info("# Unload kernel module if needed")
            cmd = "lsmod | grep {} && modprobe -r {}".format(
                self.kernel_module, self.kernel_module
            )
            logging.debug("$ %s", cmd)
            subprocess.run(cmd, shell=True)
        except subprocess.CalledProcessError:
            pass

    def probe_module(self):
        logging.info("probe rpmsg-tty kernel module")
        try:
            subprocess.run(self.probe_cmd, shell=True)
        except subprocess.CalledProcessError:
            pass

    def _init_logger(self) -> None:
        self.log_reader = subprocess.Popen(
            ["journalctl", "-f"], stdout=subprocess.PIPE
        )

    def lookup_reload_logs(self, entry: str) -> bool:
        keep_looking = True
        for key, pattern in self._search_patterns.items():
            if re.search(pattern, entry):
                self.expected_events.append((key, entry))
                if key == "ready":
                    keep_looking = False
                    break

        return keep_looking

    def verify_load_firmware_logs(
        self, match_records: list, search_stages: list
    ):
        logging.info("Validate RPMSG related log from journal logs")
        logging.debug(match_records)
        actuall_stage = []
        for record in match_records:
            if record[1]:
                actuall_stage.append(record[0])
            logging.info("%s stage: %s", record[0], record[1])

        return set(actuall_stage) == set(search_stages)

    def _monitor_journal_logs(self):
        start_time = time.time()
        logging.info("# start time: %s", start_time)

        while True:
            raw = self.log_reader.stdout.readline().decode()
            logging.info(raw)
            if raw and self.lookup_reload_logs(raw) is False:
                return
            cur_time = time.time()
            if (cur_time - start_time) > 60:
                return

    def monitor_reload_process(self):
        proc_pattern = "remoteproc remoteproc[0-9]+"
        self._search_patterns = {
            "start": r"{}: powering up .*".format(proc_pattern),
            "boot_image": (
                r"{}: Booting fw image (?P<image>\w*.elf), \w*"
            ).format(proc_pattern),
            # Please keep latest record in ready stage
            # This function will return if latest record been captured.
            "ready": (r"{}: remote processor .* is now up").format(
                proc_pattern
            ),
        }
        self._monitor_journal_logs()
        self.log_reader.kill()
        self.log_reader = None

        if self.verify_load_firmware_logs(
            self.expected_events, self._search_patterns.keys()
        ):
            logging.info("# Reload M-Core firmware successful")
        else:
            raise SystemExit("# Reload M-Core firmware failed")

    def run_test(self):
        logging.info("========== Starting RPMSG Test ==========")
        try:
            if self.should_load_firmware:
                self.handler.setup()
                logging.info("--- Managing Firmware ---")
                self.handler.stop()
                time.sleep(1)  # Allow time for the device to stop
                if self.firmware_path:
                    self.handler.firmware_path = self.firmware_path
                self.handler.firmware_file = self.firmware_name
                self._init_logger()
                thread = threading.Thread(target=self.monitor_reload_process)
                thread.start()
                self.handler.start()
                thread.join()
                self.handler.start()

            self._test_func()

        except Exception as e:
            logging.error("An error occurred during the test: %s", e)
        finally:
            self.unload_module()
            # Teardown is crucial to restore the system state
            self.handler.teardown()
            logging.info("========== RPMSG Test Finished ==========")


class RpmsgPingPongTest(RpmsgTest):
    def __init__(
        self,
        rpmsg_node,
        kernel_module,
        probe_cmd,
        pingpong_event_pattern,
        pingpong_end_pattern,
        expected_count,
        load_firmware=False,
        firmware_path=None,
        firmware_file=None,
    ):
        super().__init__(
            rpmsg_node, load_firmware, firmware_path, firmware_file
        )
        self._test_func = self.pingpong_test
        self.kernel_module = kernel_module
        self.probe_cmd = probe_cmd
        self.pingpong_event_pattern = pingpong_event_pattern
        self.pingpong_end_pattern = pingpong_end_pattern
        self.expected_count = expected_count

    def lookup_pingpong_logs(self, entry):
        keep_looking = True

        if re.search(self.pingpong_end_pattern, entry):
            keep_looking = False
        else:
            result = re.search(self.pingpong_event_pattern, entry)
            if result and result.groups()[0] in self.rpmsg_channels:
                self.pingpong_events.append(entry)

        return keep_looking

    def monitor_journal_pingpong_logs(self):

        start_time = time.time()
        logging.info("# start time: %s", start_time)

        self.pingpong_events = []
        while True:
            raw = self.log_reader.stdout.readline().decode()
            logging.info(raw)
            if raw and self.lookup_pingpong_logs(raw) is False:
                return
            cur_time = time.time()
            if (cur_time - start_time) > 60:
                return

    def get_rpmsg_channel(self):
        """
        Get all of the RPMSG destination channel

        Raises:
            SystemExit: if rpmsg_channels is empty

        Returns:
            rpmsg_channels (list): a list of RPMSG destination channel
        """
        logging.info("## Checking RPMSG channel ...")
        rpmsg_root = "/sys/bus/rpmsg/devices"
        rpmsg_channels = []
        rpmsg_devices = os.listdir(rpmsg_root)
        if not rpmsg_devices:
            raise SystemExit("RPMSG device is not available")
        else:
            logging.info("RPMSG device is available")

        for file_obj in rpmsg_devices:
            tmp_file = os.path.join(rpmsg_root, file_obj, "dst")
            if os.path.isfile(tmp_file):
                with open(tmp_file, "r") as fp:
                    rpmsg_channels.append(fp.read().strip("\n"))

        if rpmsg_channels:
            logging.info("Available RPMSG channels is %s", rpmsg_channels)
        else:
            raise SystemExit("RPMSG channel is not created")

        return rpmsg_channels

    def pingpong_test(self):
        """
        Probe ping-pong kernel module for RPMSG ping-pong test

        Raises:
            SystemExit: if ping pong event count is not expected
        """

        logging.info("# Start ping pong test")
        self.unload_module()
        # sleep few seconds for rpmsg device initialization
        time.sleep(3)
        self.rpmsg_channels = self.get_rpmsg_channel()
        try:
            if self.log_reader is None:
                self._init_logger()

            thread = threading.Thread(
                target=self.monitor_journal_pingpong_logs
            )
            thread.start()
            self.probe_module()
            thread.join()

            self.log_reader.kill()
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


class RpmsgStringEchoTest(RpmsgTest):
    def __init__(
        self,
        rpmsg_node,
        kernel_module,
        probe_cmd,
        check_pattern,
        data_size=1024,
        load_firmware=False,
        firmware_path=None,
        firmware_file=None,
    ):
        super().__init__(
            rpmsg_node, load_firmware, firmware_path, firmware_file
        )
        self._test_func = self.serial_tty_test
        self.kernel_module = kernel_module
        self.probe_cmd = probe_cmd
        self.check_pattern = check_pattern
        self.data_size = data_size

    def rpmsg_tty_test_supported(self, cpu_type):
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

    def check_rpmsg_tty_devices(self, path_obj):
        """
        Detect the RPMSG TTY devices, probe module might be executed if needed

        Args:
            path_obj (Path): a Path object
            pattern (str): the pattern of RPMSG devices
            probe_command (str): command of probe RPMSG TTY module

        Returns:
            list(Path()): a list of Path object
        """
        rpmsg_devices = sorted(path_obj.glob(self.check_pattern))
        if not rpmsg_devices:
            logging.info("probe rpmsg-tty kernel module")
            self.unload_module()
            time.sleep(2)
            self.probe_module()
            rpmsg_devices = sorted(path_obj.glob(self.check_pattern))

        return rpmsg_devices

    def serial_tty_test(self):
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
        path_obj = Path("/dev")
        rpmsg_devs = self.check_rpmsg_tty_devices(path_obj)
        if rpmsg_devs:
            serial_test.client_mode(
                str(rpmsg_devs[0]),
                "rpmsg-tty",
                [],
                115200,
                8,
                "N",
                1,
                3,
                self.data_size,
            )
        else:
            raise SystemExit("No RPMSG TTY devices found.")


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


def pingpong_test(
    rpmsg_node,
    cpu_type,
    load_firmware=False,
    firmware_path=None,
    firmware_file=None,
):
    """
    RPMSG ping-pong test

    Raises:
        SystemExit: if ping pong event count is not expected
    """

    if cpu_type == "imx":
        kernel_module = "imx_rpmsg_pingpong"
        probe_cmd = "modprobe imx_rpmsg_pingpong"
        pingpong_event_pattern = r"get .* \(src: (\w*)\)"
        pingpong_end_pattern = r"rpmsg.*: goodbye!"
        expected_count = 51
    elif cpu_type == "ti":
        kernel_module = "rpmsg_client_sample"
        probe_cmd = "modprobe rpmsg_client_sample count=100"
        pingpong_event_pattern = r".*ti.ipc4.ping-pong.*\(src: (\w*)\)"
        pingpong_end_pattern = r"rpmsg.*: goodbye!"
        expected_count = 100
    else:
        raise SystemExit("Unexpected CPU type.")

    test_obj = RpmsgPingPongTest(
        rpmsg_node,
        kernel_module,
        probe_cmd,
        pingpong_event_pattern,
        pingpong_end_pattern,
        expected_count,
        load_firmware=load_firmware,
        firmware_path=firmware_path,
        firmware_file=firmware_file,
    )
    test_obj.run_test()


def string_echo_test(
    rpmsg_node,
    cpu_type,
    load_firmware=False,
    firmware_path=None,
    firmware_file=None,
):
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
        kernel_module = "imx_rpmsg_tty"
        probe_cmd = "modprobe imx_rpmsg_tty"
        check_pattern = r"ttyRPMSG[0-9]*"
        data_size = 1024
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

    test_obj = RpmsgStringEchoTest(
        rpmsg_node,
        kernel_module,
        probe_cmd,
        check_pattern,
        data_size,
        load_firmware=load_firmware,
        firmware_path=firmware_path,
        firmware_file=firmware_file,
    )
    test_obj.run_test()


def run(cmd):
    return subprocess.check_output(cmd, shell=True, text=True).strip()


def check_device_tree():
    mailboxes = []
    vdevbuffer = []
    vdevring = []
    rsc_table = []

    # check mailbox define and interrupt value
    for root, dirs, files in os.walk("/proc/device-tree/"):
        for d in dirs:
            if d.startswith("mailbox"):
                mailboxes.append(os.path.join(root, d))
    if not mailboxes:
        raise SystemExit("FAIL: no mailbox is defined in device-tree")
    logging.info("PASSED: mailbox defined is found")

    for node in mailboxes:
        dts = run("dtc -qqq -f -I fs -O dts {}".format(node))
        interrupt = re.search(r"\binterrupts\s*=\s*<([^>]+)>;", dts)
        if not interrupt:
            raise SystemExit("FAIL: no interrupts is defined for mailbox")
        logging.info("PASSED: interrupt defined is found for mailbox")

    # check virtio device ring buffer and buffer define.
    for root, dirs, files in os.walk("/proc/device-tree/"):
        for d in dirs:
            if "vdev" in d and "buffer" in d:
                vdevbuffer.append(d)
            elif "vdev" in d and "vring" in d:
                vdevring.append(d)
            elif "rsc-table" in d:
                rsc_table.append(d)

    if not vdevbuffer:
        raise SystemExit("FAIL: vdevbuffer is not defined")
    logging.info("PASSED: vdevbuffer define:")
    logging.debug(vdevbuffer)

    if not vdevring:
        raise SystemExit("WARNING: vdev vrings are not defined")
    logging.info("PASSED: vdev vring is are defined:")
    logging.debug(vdevring)

    if not rsc_table:
        raise SystemExit("WARNING: resource table is not defined")
    logging.info("PASSED: resource table is defined:")
    logging.debug(rsc_table)


def remoteproc_node_detection_test(remoteproc_node):
    """
    Validate the remoteproc node is available

    Raises:
        SystemExit: exit if no remoteproc node is available
    """
    logging.info("## Checking remoteproc node is available ...")

    remoteproc_devices = os.listdir(REMOTEPROC_PATH)
    logging.info(remoteproc_devices)
    if not remoteproc_devices:
        raise SystemExit("REMOTEPROC node is not available")
    elif remoteproc_node and remoteproc_node not in remoteproc_devices:
        raise SystemExit("{} is not available".format(remoteproc_node))

    logging.info("PASSED: remoteproc node is available")


def has_bound_device(driver_path):
    """
    A bound platform device usually appears as a symlink whose
    name looks like a hex address or device identifier.
    """

    try:
        for entry in os.listdir(driver_path):
            # platform device names are often hex-like or numeric
            if re.match(r"^[0-9a-fA-F]", entry):
                return
    except OSError:
        raise SystemExit("FAIL: No mailbox driver be probed.")


def check_mailbox(mbox_driver):
    logging.info("Target mailbox driver: {}".format(mbox_driver))
    drivers_path = "/sys/bus/platform/drivers"

    if mbox_driver in os.listdir(drivers_path):
        driver_path = os.path.join(drivers_path, mbox_driver)

        has_bound_device(driver_path)

    else:
        raise SystemExit("FAIL: No mailbox driver is found.")
    logging.info("PASSED: Mailbox driver found")


def check_virtio_device(node):
    logging.info("Target device: {}".format(node))
    virtio_devices = [
        Path(p).name for p in glob.glob("/sys/bus/virtio/devices/virtio*")
    ]
    logging.info(virtio_devices)
    if node not in virtio_devices:
        raise SystemExit(
            "FAIL: no matched virtio devices created by remoteproc."
        )
    logging.info("PASSED: virtio devices present: {}".format(node))


def check_rpmsg_transport(node, e_driver):
    logging.info("Target driver %s", e_driver)
    driver = os.path.join("/sys/bus/virtio/devices", node, "driver")
    if os.path.islink(driver):
        drv = os.path.realpath(driver)
        if e_driver in drv:
            logging.info("PASSED: rpmsg transport bound to %s", drv)
            return
        else:
            raise SystemExit(
                "FAIL: We expect driver {}, but {} found".format(
                    e_driver, os.path.basename(drv)
                )
            )
    raise SystemExit("FAIL: transport driver not bound")


def check_virtio(virtio_device, virtio_driver):
    check_virtio_device(virtio_device)
    check_rpmsg_transport(virtio_device, virtio_driver)


def get_rpmsg_channel():
    """
    Get all of the RPMSG destination channel

    Raises:
        SystemExit: if rpmsg_channels is empty

    Returns:
        rpmsg_channels (list): a list of RPMSG destination channel
    """
    logging.info("## Checking RPMSG channel ...")
    rpmsg_root = "/sys/bus/rpmsg/devices"
    rpmsg_channels = []
    rpmsg_devices = os.listdir(rpmsg_root)
    if not rpmsg_devices:
        raise SystemExit("FAIL: RPMSG device is not available")
    else:
        logging.info("PASSED: RPMSG device is available")

    for file_obj in rpmsg_devices:
        tmp_file = Path(rpmsg_root, file_obj, "dst")
        if tmp_file.is_file():
            rpmsg_channels.append(tmp_file.read_text().strip("\n"))

    if rpmsg_channels:
        logging.info("PASSED: Available RPMSG channels is %s", rpmsg_channels)
    else:
        raise SystemExit("FAIL: RPMSG channel is not created")

    return rpmsg_channels


def register_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "RPMSG validation tool for ping-pong and string-echo tests."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--remoteproc-node",
        default="remoteproc0",
        help="The RPMSG node to use (default: remoteproc0)",
    )

    parser.add_argument(
        "--virtio-device",
        default="virtio0",
        help="The virtio device to use(default: virtio0).",
    )

    parser.add_argument(
        "--virtio-driver",
        default="virtio_rpmsg_bus",
        help="The virtio for rpmsg driver to use(default: virtio_rpmsg_bus).",
    )

    parser.add_argument(
        "--mbox-driver",
        default="imx_mu",
        help="The mailbox driver to use(default: imx_mu).",
    )

    subparsers = parser.add_subparsers(
        dest="test_command", required=True, help="The test to run."
    )

    parser_dtree = subparsers.add_parser(
        "dtree-verify", help="Check if the device tree is well defined."
    )
    parser_dtree.set_defaults(func=check_device_tree)

    parser_detection = subparsers.add_parser(
        "node-detection", help="Check if the remoteproc node exists."
    )
    parser_detection.set_defaults(func=remoteproc_node_detection_test)

    parser_mbox = subparsers.add_parser(
        "mailbox-detection",
        help="Check if the mailbox device node exists "
        "and driver has been probed",
    )

    parser_mbox.set_defaults(func=check_mailbox)

    parser_vio = subparsers.add_parser(
        "virtio-detection", help="Check if the virtio device node exists."
    )
    parser_vio.set_defaults(func=check_virtio)

    parser_channel = subparsers.add_parser(
        "channel-detection",
        help="Check if the transport driver has been probed.",
    )
    parser_channel.set_defaults(func=get_rpmsg_channel)

    parser_pingpong = subparsers.add_parser(
        "pingpong", help="Run RPMSG ping-pong test."
    )
    parser_pingpong.add_argument(
        "--load-firmware",
        action="store_true",
        default=False,
        help="Enable this flag to manage firmware loading.",
    )
    parser_pingpong.add_argument(
        "--firmware-path",
        default="/lib/firmware",
        help="Path to the directory containing firmware files.",
    )
    parser_pingpong.add_argument(
        "--firmware-file",
        default="",
        help=(
            "Specific firmware file to load "
            "(required if --load-firmware is set)."
        ),
    )
    parser_pingpong.set_defaults(func=pingpong_test)

    parser_echo = subparsers.add_parser(
        "string-echo", help="Run the string echo serial test."
    )
    parser_echo.add_argument(
        "--load-firmware",
        action="store_true",
        default=False,
        help="Enable this flag to manage firmware loading.",
    )
    parser_echo.add_argument(
        "--firmware-path",
        default="/lib/firmware",
        help="Path to the directory containing firmware files.",
    )
    parser_echo.add_argument(
        "--firmware-file",
        default="",
        help=(
            "Specific firmware file to load "
            "(required if --load-firmware is set)."
        ),
    )
    parser_echo.set_defaults(func=string_echo_test)

    return parser.parse_args()


def main():
    args = register_arguments()

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

    func_kwargs = {}
    if args.test_command in ["node-detection"]:
        func_kwargs["remoteproc_node"] = args.remoteproc_node
        args.func(**func_kwargs)

    elif args.test_command in ["pingpong", "string-echo"]:

        if args.load_firmware and not args.firmware_file:
            logging.error(
                "firmware-file is required when 'load-firmware' is specified."
            )
            exit(1)

        func_kwargs["remoteproc_node"] = args.remoteproc_node
        cpu_type = detect_arm_processor_type()
        func_kwargs["cpu_type"] = cpu_type
        func_kwargs["load_firmware"] = args.load_firmware
        func_kwargs["firmware_path"] = args.firmware_path
        func_kwargs["firmware_file"] = args.firmware_file
        args.func(**func_kwargs)

    elif args.test_command in ["mailbox-detection"]:
        func_kwargs["mbox_driver"] = args.mbox_driver
        args.func(**func_kwargs)

    elif args.test_command in ["virtio-detection"]:
        func_kwargs["virtio_device"] = args.virtio_device
        func_kwargs["virtio_driver"] = args.virtio_driver
        args.func(**func_kwargs)

    else:
        args.func()


if __name__ == "__main__":
    main()
