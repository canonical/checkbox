import unittest
from unittest.mock import patch, MagicMock


from storage_test import mountpoint, run_bonnie, main


class TestMountpoint(unittest.TestCase):
    @patch("psutil.disk_partitions")
    def test_mountpoint_nominal(self, mock_disk_partitions):

        sdiskpart = MagicMock()
        sdiskpart.device = "/dev/sda1"
        sdiskpart.mountpoint = "/"
        mock_disk_partitions.return_value = [sdiskpart]
        self.assertEqual(mountpoint("/dev/sda1"), "/")

    @patch("psutil.disk_partitions")
    def test_mountpoint_nominal_multiple(self, mock_disk_partitions):

        mock_disk_partitions.return_value = [
            MagicMock(device="/dev/sda1", mountpoint="/"),
            MagicMock(device="/dev/sda2", mountpoint="/boot"),
        ]
        self.assertEqual(mountpoint("/dev/sda2"), "/boot")

    @patch("psutil.disk_partitions")
    def test_mountpoint_empty(self, mock_disk_partitions):
        mock_disk_partitions.return_value = []
        self.assertEqual(mountpoint("/dev/sda1"), None)

    @patch("storage_test.memory", return_value=8000)
    @patch("storage_test.free_space", return_value=16000)
    @patch("storage_test.sp.check_call")
    def test_run_bonnie(self, mock_check_call, mock_free_space, mock_memory):
        run_bonnie("/test_dir")
        mock_check_call.assert_called_once_with(
            "bonnie++ -d /test_dir -u root -r 8000", shell=True
        )

    @patch("storage_test.devmapper_name", return_value=None)
    @patch("storage_test.disk_test")
    def test_main_disk_test(self, mock_disk_test, mock_devmapper_name):
        with patch("sys.argv", ["storage_test.py", "sda"]):
            main()
            mock_disk_test.assert_called_once_with("sda")

    @patch("storage_test.devmapper_name", return_value="mapper_name")
    @patch("storage_test.devmapper_test")
    def test_main_devmapper_test(
        self, mock_devmapper_test, mock_devmapper_name
    ):
        with patch("sys.argv", ["storage_test.py", "sda"]):
            main()
            mock_devmapper_test.assert_called_once_with("sda")

    @patch("builtins.print")
    @patch("sys.exit")
    def test_main_ignore_mtdblock(self, mock_exit, mock_print):
        with patch("sys.argv", ["storage_test.py", "mtdblock0"]):
            main()
            mock_print.assert_called_with("Ignoring mtdblock device")
            mock_exit.assert_not_called()
