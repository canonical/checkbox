import unittest
import sys
import argparse
from pathlib import Path
from io import StringIO
from contextlib import redirect_stdout
from unittest.mock import patch, MagicMock, Mock

sys.modules["systemd"] = MagicMock()

import rpmsg_load_firmware


class RpmsgLoardFirmwareTests(unittest.TestCase):
    """
    Unit tests for RPMSG load firmware test scripts
    """

    def setUp(self) -> None:
        test_dev = "remoteproc0"
        self._rpmsg_load_fw_test = rpmsg_load_firmware.RpmsgLoadFirmwareTest(
            test_dev
        )
        self._default_search_pattern = {
            "start": r"remoteproc remoteproc[0-9]+: powering up imx-rproc",
            "boot_image": (
                r"remoteproc remoteproc[0-9]+: "
                r"Booting fw image (?P<image>\w*.elf), \w*"
            ),
            "ready": (
                r"remoteproc remoteproc[0-9]+: "
                r"remote processor imx-rproc is now up"
            ),
        }

    def test_validate_rpmsg_object(self):

        self.assertEqual(
            self._rpmsg_load_fw_test._firmware_path,
            Path("/sys/module/firmware_class/parameters/path"),
        )
        self.assertEqual(
            self._rpmsg_load_fw_test._firmware_file,
            Path("/sys/class/remoteproc/remoteproc0/firmware"),
        )
        self.assertEqual(
            self._rpmsg_load_fw_test._rpmsg_state,
            Path("/sys/class/remoteproc/remoteproc0/state"),
        )
        self.assertDictEqual(
            self._rpmsg_load_fw_test._search_patterns,
            {},
        )
        self.assertListEqual(self._rpmsg_load_fw_test.expected_events, [])

    @patch("pathlib.Path.read_text")
    def test_get_firmware_path(self, mock_read):

        expected_result = "test-response"
        mock_read.return_value = expected_result
        self.assertEqual(
            self._rpmsg_load_fw_test.firmware_path, expected_result
        )

    @patch("pathlib.Path.write_text")
    def test_set_firmware_path(self, mock_write):
        expected_result = "test-response"
        self._rpmsg_load_fw_test.firmware_path = expected_result
        mock_write.assert_called_once_with(expected_result)

    @patch("pathlib.Path.read_text")
    def test_get_firmware_file(self, mock_read):

        expected_result = "test-response"
        mock_read.return_value = expected_result
        self.assertEqual(
            self._rpmsg_load_fw_test.firmware_file, expected_result
        )

    @patch("pathlib.Path.write_text")
    def test_set_firmware_file(self, mock_write):
        expected_result = "test-response"
        self._rpmsg_load_fw_test.firmware_file = expected_result
        mock_write.assert_called_once_with(expected_result)

    @patch("pathlib.Path.read_text")
    def test_get_rpmsg_state(self, mock_read):

        expected_result = "test-response"
        mock_read.return_value = expected_result
        self.assertEqual(self._rpmsg_load_fw_test.rpmsg_state, expected_result)

    @patch("pathlib.Path.write_text")
    def test_set_rpmsg_state(self, mock_write):
        expected_result = "test-response"
        self._rpmsg_load_fw_test.rpmsg_state = expected_result
        mock_write.assert_called_once_with(expected_result)

    def test_get_search_pattern(self):
        self.assertDictEqual(
            self._rpmsg_load_fw_test.search_pattern,
            {},
        )

    def test_set_search_pattern(self):
        expected_result = {
            "start": "fake",
            "boot_image": "fake",
            "ready": "fake",
        }

        self._rpmsg_load_fw_test.search_pattern = expected_result
        self.assertDictEqual(
            self._rpmsg_load_fw_test.search_pattern,
            expected_result,
        )

    def test_init_logger(self):
        pass

    def test_lookup_reload_logs_not_last_one(self):
        self._rpmsg_load_fw_test.search_pattern = self._default_search_pattern
        entry = {
            "MESSAGE": (
                "Apr 25 07:12:53 ubuntu kernel: remoteproc "
                "remoteproc0: powering up imx-rproc"
            )
        }
        self.assertTrue(self._rpmsg_load_fw_test.lookup_reload_logs(entry))
        self.assertEqual(
            self._rpmsg_load_fw_test.expected_events,
            [("start", entry["MESSAGE"])],
        )

    def test_lookup_reload_logs_last_one(self):
        self._rpmsg_load_fw_test.search_pattern = self._default_search_pattern
        entry = {
            "MESSAGE": (
                "Apr 25 07:12:53 ubuntu kernel: remoteproc "
                "remoteproc0: remote processor imx-rproc is now up"
            )
        }
        self.assertFalse(self._rpmsg_load_fw_test.lookup_reload_logs(entry))
        self.assertEqual(
            self._rpmsg_load_fw_test.expected_events,
            [("ready", entry["MESSAGE"])],
        )

    def test_verify_load_firmware_logs_successful(self):
        match_records = [("stage1", "message1"), ("stage2", "message2")]
        search_stages = ["stage1", "stage2"]

        self.assertTrue(
            rpmsg_load_firmware.verify_load_firmware_logs(
                match_records, search_stages
            )
        )

    def test_verify_load_firmware_logs_not_match(self):
        match_records = [("stage1", "message1")]
        search_stages = ["stage1", "stage2"]

        self.assertFalse(
            rpmsg_load_firmware.verify_load_firmware_logs(
                match_records, search_stages
            )
        )


class RpmsgMainFunctionTest(unittest.TestCase):
    def test_reload_test_parser(self):
        sys.argv = [
            "rpmsg_load_firmware.py",
            "test-reload",
            "--device",
            "remoteproc0",
            "--path",
            "/home",
            "--file",
            "test-fw.elf",
        ]
        args = rpmsg_load_firmware.register_arguments()

        self.assertEqual(
            args.test_func, rpmsg_load_firmware.load_firmware_test
        )
        self.assertEqual(args.device, "remoteproc0")
        self.assertEqual(args.path, "/home")
        self.assertEqual(args.file, "test-fw.elf")

    def test_resource_parser(self):
        sys.argv = [
            "rpmsg_load_firmware.py",
            "resource-reload",
            "--mapping",
            "remoteproc0:test-fw.elf",
            "--path",
            "/home",
        ]
        args = rpmsg_load_firmware.register_arguments()

        self.assertEqual(
            args.test_func, rpmsg_load_firmware.dump_firmware_test_mapping
        )
        self.assertEqual(args.path, "/home")
        self.assertEqual(args.mapping, "remoteproc0:test-fw.elf")

    def test_dump_firmware_test_mapping_successful(self):
        mock_args = Mock(
            return_value=argparse.Namespace(
                mapping="remoteproc0:test-fw.elf remoteproc1:test-fw.elf",
                path="/home/ubuntu",
            )
        )
        with redirect_stdout(StringIO()) as stdout:
            rpmsg_load_firmware.dump_firmware_test_mapping(mock_args())
        self.assertEqual(
            stdout.getvalue().strip("\n"),
            (
                "device: remoteproc0\nfirmware: test-fw.elf\n"
                "path: /home/ubuntu\n\n"
                "device: remoteproc1\nfirmware: test-fw.elf\n"
                "path: /home/ubuntu"
            ),
        )

    def test_dump_firmware_test_mapping_format_invalid(self):
        mock_args = Mock(
            return_value=argparse.Namespace(
                mapping="remoteproest-fw.elf",
                path="/home/ubuntu",
            )
        )
        args = mock_args()
        with redirect_stdout(StringIO()) as stdout:
            rpmsg_load_firmware.dump_firmware_test_mapping(args)
        self.assertEqual(
            stdout.getvalue().strip("\n"),
            ("device: {}\nfirmware: {}\npath: {}").format(
                args.mapping, args.mapping, args.path
            ),
        )
