import os
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from unittest.mock import patch, mock_open, call

import rpmsg_tests


tmpdir = TemporaryDirectory()


class RpmsgSysFsHandlerTests(unittest.TestCase):

    @patch("rpmsg_tests.RPMSG_PATH", tmpdir.name)
    def setUp(self):
        self.rpmsg_node = "remoteproc0"

        dir_path = Path(tmpdir.name)
        remoteproc_dir = dir_path.joinpath(self.rpmsg_node)
        remoteproc_dir.mkdir(exist_ok=True)
        self.firmware_file = remoteproc_dir.joinpath("firmware")
        self.firmware_file.write_text("test_firmware")
        self.state_file = remoteproc_dir.joinpath("state")
        self.state_file.write_text("running")
        self.firmware_path_file = remoteproc_dir.joinpath("path")
        self.firmware_path_file.write_text("test_path")

        self.handler = rpmsg_tests.RpmsgSysFsHandler(self.rpmsg_node)
        self.handler.sysfs_fw_path = self.firmware_path_file

    def test_rpmsg_sysfs_handler_initialization(self):
        self.assertEqual(
            self.handler.sysfs_fw_path,
            self.firmware_path_file,
        )
        self.assertEqual(
            self.handler.sysfs_firmware_file,
            os.path.join(tmpdir.name, self.rpmsg_node, "firmware"),
        )
        self.assertEqual(
            self.handler.sysfs_state_path,
            os.path.join(tmpdir.name, self.rpmsg_node, "state"),
        )
        self.assertIsNone(self.handler.original_firmware_path)
        self.assertIsNone(self.handler.original_firmware)
        self.assertIsNone(self.handler.original_state)
        self.assertFalse(self.handler.started_by_script)

    def test_rpmsg_sysfs_handler_initialization_no_dir(self):

        with patch("rpmsg_tests.RPMSG_PATH", tmpdir.name):
            with self.assertRaises(SystemExit) as cm:
                rpmsg_tests.RpmsgSysFsHandler("nonexistent")
                self.assertEqual(cm.exception.code, 1)

    def test_read_node(self):

        value = self.handler._read_node(self.handler.sysfs_firmware_file)
        self.assertEqual(value, "test_firmware")

    def test_read_node_ioerror(self):
        with patch(
            "builtins.open", side_effect=IOError("No such file or directory")
        ):
            value = self.handler._read_node("fake_path")
            self.assertIsNone(value)

    def test_write_node(self):

        value = self.handler._write_node(
            self.handler.sysfs_firmware_file, "fake_path"
        )
        self.assertTrue(value)

    def test_write_node_ioerror(self):
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            with self.assertRaises(IOError):
                self.handler._write_node(
                    self.handler.sysfs_firmware_file, "fake_path"
                )

    def test_firmware_path_property(self):
        self.assertEqual(self.handler.firmware_path, "test_path")

    def test_firmware_file_property(self):
        self.assertEqual(self.handler.firmware_file, "test_firmware")

    def test_rpmsg_state_property(self):
        self.assertEqual(self.handler.rpmsg_state, "running")

    def test_rpmsg_state_setter_validation(self):
        with self.assertRaises(ValueError):
            self.handler.rpmsg_state = "invalid"
            self.assertEqual(self.handler.rpmsg_state, "running")

    def test_setup_teardown(self):

        self.state_file.write_text("offline")

        self.handler.setup()
        self.assertEqual(self.handler.original_firmware_path, "test_path")
        self.assertEqual(self.handler.original_firmware, "test_firmware")
        self.assertEqual(self.handler.original_state, "offline")

        self.handler.teardown()
        self.assertEqual(self.handler.firmware_path, "test_path")
        self.assertEqual(self.handler.firmware_file, "test_firmware")
        self.assertEqual(self.handler.rpmsg_state, "offline")

    def test_setup_teardown_no_original_values(self):
        with (
            patch(
                "builtins.open",
                side_effect=IOError("No such file or directory"),
            ),
        ):
            self.handler.setup()

            self.assertIsNone(self.handler.original_firmware_path)
            self.assertIsNone(self.handler.original_firmware)
            self.assertIsNone(self.handler.original_state)

            self.handler.teardown()

    def test_start_stop(self):
        self.state_file.write_text("offline")
        self.handler.start()
        self.assertEqual(self.handler.rpmsg_state, "start")
        self.assertTrue(self.handler.started_by_script)

        self.handler.stop()
        self.assertEqual(self.handler.rpmsg_state, "stop")

    def test_start_already_running(self):
        self.state_file.write_text("running")
        value = self.handler.start()
        self.assertTrue(value)

    def test_stop_already_offline(self):
        self.state_file.write_text("offline")
        value = self.handler.stop()
        self.assertTrue(value)

    def test_teardown_state_not_started_by_script(self):
        self.firmware_file.write_text("new_firmware")
        self.firmware_path_file.write_text("new_path")
        self.state_file.write_text("running")

        self.handler.setup()
        self.assertFalse(self.handler.started_by_script)

        self.handler.teardown()
        self.handler.firmware_file = "original_firmware"
        self.handler.firmware_path = "test_path"
        self.handler.rpmsg_state = "start"
