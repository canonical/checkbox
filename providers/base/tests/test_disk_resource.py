import unittest
import textwrap
from subprocess import CalledProcessError
from unittest.mock import patch, MagicMock

import disk_resource


class TestDiskResource(unittest.TestCase):
    def test_print_as_resource(self):
        with patch("builtins.print") as mocked_print:
            block_device = {
                "kname": "sda",
                "path": "/dev/sda",
                "model": "FastSSD",
                "size": "512110190592",
                "rota": False,
            }
            disk_resource.print_as_resource(block_device)
            mocked_print.assert_any_call("name:", "sda")
            mocked_print.assert_any_call("path:", "/dev/sda")
            mocked_print.assert_any_call("model:", "FastSSD")
            mocked_print.assert_any_call("size:", "512110190592")
            mocked_print.assert_any_call("rotational:", False)

    def test_get_relevant_block_devices_is_mmc(self):
        block_devices = [
            {"type": "disk", "kname": "mmcblk0", "mountpoint": "/boot"}
        ]
        result = list(disk_resource.get_relevant_block_devices(block_devices))
        self.assertEqual(len(result), 0)

    def test_get_relevant_block_devices_loopback(self):
        block_devices = [
            {"type": "loop", "kname": "loop0", "mountpoint": None}
        ]
        result = list(disk_resource.get_relevant_block_devices(block_devices))
        self.assertEqual(len(result), 0)

    def test_get_relevant_block_devices_snapd(self):
        block_devices = [
            {
                "type": "disk",
                "kname": "sda",
                "mountpoint": "var/lib/snapd/save",
            }
        ]
        result = list(disk_resource.get_relevant_block_devices(block_devices))
        self.assertEqual(len(result), 0)

    def test_get_relevant_block_devices_ok(self):
        block_devices = [{"type": "disk", "kname": "sda", "mountpoint": "/"}]
        result = list(disk_resource.get_relevant_block_devices(block_devices))
        self.assertEqual(len(result), 1)

    @patch("disk_resource.check_output")
    def test_get_blockdevices_info_ok(self, mock_check_output):
        mock_check_output.return_value = textwrap.dedent(
            """
            {
                "blockdevices": [
                    {
                        "kname": "sda",
                        "path": "/dev/sda",
                        "type": "disk",
                        "size": "256G",
                        "model": "FastSSD",
                        "rota": false
                    }
                ]
            }
            """
        )
        result = disk_resource.get_blockdevices_info()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["model"], "FastSSD")

    @patch("disk_resource.check_output")
    def test_get_blockdevices_info_fail(self, mock_check_output):
        mock_check_output.side_effect = CalledProcessError(1, "Command failed")
        with self.assertRaises(SystemExit):
            disk_resource.get_blockdevices_info()


class TestMain(unittest.TestCase):
    @patch("disk_resource.check_output")
    @patch("disk_resource.print_as_resource")
    def test_main(self, mock_print_as_resource, mock_check_output):
        mock_check_output.return_value = textwrap.dedent(
            """
            {
                "blockdevices": [
                    {
                        "kname": "sda",
                        "path": "/dev/sda",
                        "type": "disk",
                        "size": "256G",
                        "model": "FastSSD",
                        "rota": "0",
                        "mountpoint" : "/"
                    },
                    {
                        "kname": "loop1",
                        "path": "/dev/loop1",
                        "type": "loop",
                        "size": 58363904,
                        "model": null,
                        "rota": false,
                        "mountpoint": "/var/lib/snapd/snap/core16/2812"
                    }

                ]
            }
            """
        )

        disk_resource.main()

        self.assertEqual(mock_print_as_resource.call_count, 1)
