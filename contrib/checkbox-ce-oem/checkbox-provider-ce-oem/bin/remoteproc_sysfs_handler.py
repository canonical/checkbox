#!/usr/bin/env python3
import os
import time
import logging

REMOTEPROC_PATH = "/sys/class/remoteproc"


class RemoteProcSysFsHandler:

    properties = ["firmware_path", "firmware_file", "rpmsg_state"]

    def __init__(self, remoteproc_dir):
        root_path = os.path.join(REMOTEPROC_PATH, remoteproc_dir)
        self.sysfs_fw_path = "/sys/module/firmware_class/parameters/path"
        self.sysfs_firmware_file = os.path.join(root_path, "firmware")
        self.sysfs_state_path = os.path.join(root_path, "state")
        self.sysfs_name_path = os.path.join(root_path, "name")
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
    def name(self):
        return self._read_node(self.sysfs_name_path)

    @property
    def state(self):
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

    @state.setter
    def state(self, value: str):
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

        self.original_state = self.state
        if self.original_state:
            logging.info("Original state was: %s", self.original_state)
        else:
            logging.warning("Could not read original state.")

    def teardown(self):
        """Restores the initial firmware configuration."""
        if self.original_firmware is not None:
            if self.state == "running":
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
        if self.state == "running":
            logging.info("Remoteproc is already running.")
            return True
        self.started_by_script = True
        self.state = "start"
        return True

    def stop(self):
        if self.state == "offline":
            logging.info("Remoteproc is already offline.")
            return True
        self.state = "stop"
        return True
