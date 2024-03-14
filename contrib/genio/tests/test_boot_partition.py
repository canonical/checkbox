import unittest
from unittest.mock import patch, MagicMock
import boot_partition as bp


class TestBootPartition(unittest.TestCase):

    def setUp(self):
        self.pbd = bp.TestPartedBootDevice()

    @patch("boot_partition.subprocess.run")
    def test_runcmd(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="output", stderr="error", returncode=0
        )
        result = bp.runcmd("echo Hello")

        mock_run.assert_called_once()
        self.assertEqual(result.stdout, "output")
        self.assertEqual(result.stderr, "error")
        self.assertEqual(result.returncode, 0)

    @patch("pathlib.Path.is_block_device")
    def test_check_is_block_device(self, mock_is_block_device):
        self.pbd.path = "/dev/sdc"

        mock_is_block_device.return_value = True
        self.pbd.check_is_block_device()

        mock_is_block_device.return_value = False
        with self.assertRaises(SystemExit):
            self.pbd.check_is_block_device()

    @patch("boot_partition.TestPartedBootDevice.check_sector_size")
    @patch("boot_partition.TestPartedBootDevice.check_partitions")
    def test_check_disk(self, mock_cp, mock_css):
        self.pbd.check_disk()
        self.pbd.check_sector_size.assert_called_once()
        self.pbd.check_partitions.assert_called_once()

    @patch("boot_partition.runcmd")
    def test_get_disk_information(self, mock_runcmd):
        json_data = (
            '{"disk": {"logical-sector-size": 4096, "physical-sector-size": '
            '4096, "partitions": [ {"number": 1, "name": "bootloaders"} ] } }'
        )

        mock_runcmd.return_value.stdout = json_data

        self.pbd.path = "/dev/sdc"
        self.pbd.get_disk_information()
        self.assertEqual(
            self.pbd.expected_result,
            self.pbd.expected_result_UFS,
            "Failed to get expected result for UFS",
        )

        self.pbd.path = "/dev/mmcblk0"
        self.pbd.get_disk_information()
        self.assertEqual(
            self.pbd.expected_result,
            self.pbd.expected_result_EMMC,
            "Failed to get expected result for EMMC",
        )

        self.pbd.path = "/dev/unknown"
        with self.assertRaises(SystemExit):
            self.pbd.get_disk_information()

    def test_check_sector_size(self):
        self.pbd.expected_result = {
            "logical-sector-size": 4096,
            "physical-sector-size": 4096,
        }

        # Correct sector size
        self.pbd.actual_result = {
            "logical-sector-size": 4096,
            "physical-sector-size": 4096,
        }
        self.pbd.check_sector_size()

        # Different logical-sector-size
        self.pbd.actual_result = {
            "logical-sector-size": 8192,
            "physical-sector-size": 4096,
        }
        with self.assertRaises(SystemExit):
            self.pbd.check_sector_size()

        # Different logical-sector-size not found
        self.pbd.actual_result = {"physical-sector-size": 4096}
        with self.assertRaises(SystemExit):
            self.pbd.check_sector_size()

        # Different physical-sector-size
        self.pbd.actual_result = {
            "logical-sector-size": 4096,
            "physical-sector-size": 8192,
        }
        with self.assertRaises(SystemExit):
            self.pbd.check_sector_size()

        # Different physical-sector-size not found
        self.pbd.actual_result = {"logical-sector-size": 4096}
        with self.assertRaises(SystemExit):
            self.pbd.check_sector_size()

    def test_check_partitions(self):
        self.pbd.expected_result = {
            "partitions": [{"number": 1, "name": "bootloaders"}]
        }

        # Correct partitions
        self.pbd.actual_result = {
            "partitions": [{"number": 1, "name": "bootloaders"}]
        }
        self.pbd.check_partitions()

        # Different lenght of partitions
        self.pbd.actual_result = {
            "partitions": [
                {"number": 1, "name": "bootloaders"},
                {"number": 9, "name": "writable"},
            ]
        }
        with self.assertRaises(SystemExit):
            self.pbd.check_partitions()

        # Different partition number
        self.pbd.actual_result = {
            "partitions": [{"number": 2, "name": "bootloaders"}]
        }
        with self.assertRaises(SystemExit):
            self.pbd.check_partitions()

        # Different partition name
        self.pbd.actual_result = {
            "partitions": [{"number": 1, "name": "bad_name"}]
        }
        with self.assertRaises(SystemExit):
            self.pbd.check_partitions()

        # Different partitions not found
        self.pbd.actual_result = {}
        with self.assertRaises(SystemExit):
            self.pbd.check_partitions()

    @patch("boot_partition.runcmd")
    def test_check_device(self, mock_runcmd):
        mock_runcmd.return_value.stdout = "sdc"
        self.pbd.check_device(True)

        mock_runcmd.return_value.stdout = "mmcblk0"
        self.pbd.check_device(True)

        mock_runcmd.return_value.stdout = "unknown"
        self.pbd.check_device(False)

        mock_runcmd.return_value.stdout = "unknown"
        with self.assertRaises(SystemExit):
            self.pbd.check_device(True)

    @patch("boot_partition.TestPartedBootDevice.check_device")
    @patch("boot_partition.TestPartedBootDevice.check_is_block_device")
    @patch("boot_partition.TestPartedBootDevice.get_disk_information")
    @patch("boot_partition.TestPartedBootDevice.check_disk")
    def test_main_with_path(
        self, mock_check_disk, mock_get_disk, mock_is_block, mock_check_dev
    ):
        args = ["script_name", "--path", "/dev/sda"]
        with patch("sys.argv", args):
            self.pbd.main()
        mock_check_dev.assert_not_called()
        mock_is_block.assert_called_once()
        mock_get_disk.assert_called_once()
        mock_check_disk.assert_called_once()

    @patch("boot_partition.TestPartedBootDevice.check_device")
    @patch("boot_partition.TestPartedBootDevice.check_is_block_device")
    def test_main_check_device(self, mock_is_block, mock_check_dev):
        # Test with --check_device_name flag
        args = ["script_name", "--check_device_name"]
        with patch("sys.argv", args):
            self.pbd.main()
        mock_check_dev.assert_called_once()
        mock_is_block.assert_not_called()

    @patch("boot_partition.TestPartedBootDevice.check_device")
    def test_main_check_device_with_exit(self, mock_is_block):
        # Test with --check_device_name flag
        mock_is_block.return_value = None
        args = ["script_name", "--check_device_name", "--exit_when_check_fail"]
        with patch("sys.argv", args):
            self.pbd.main()

        mock_is_block.side_effect = SystemExit
        with self.assertRaises(SystemExit):
            with patch("sys.argv", args):
                self.pbd.main()