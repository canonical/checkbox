import json
import unittest
from pathlib import Path, PosixPath
from unittest.mock import MagicMock, patch

from storage_test import (
    devmapper_name,
    devmapper_test,
    disk_test,
    find_largest_partition,
    main,
    mount,
    mountpoint,
    run_bonnie,
    unmount,
)


class TestMountpoint(unittest.TestCase):
    @patch("psutil.disk_partitions")
    def test_mountpoint_nominal(self, mock_disk_partitions):

        sdiskpart = MagicMock()
        sdiskpart.device = "/dev/sda1"
        sdiskpart.mountpoint = "/"
        mock_disk_partitions.return_value = [sdiskpart]
        self.assertEqual(mountpoint(Path("/dev/sda1")), Path("/"))

    @patch("psutil.disk_partitions")
    def test_mountpoint_nominal_multiple(self, mock_disk_partitions):

        mock_disk_partitions.return_value = [
            MagicMock(device="/dev/sda1", mountpoint="/"),
            MagicMock(device="/dev/sda2", mountpoint="/boot"),
        ]
        self.assertEqual(mountpoint(Path("/dev/sda2")), Path("/boot"))

    @patch("psutil.disk_partitions")
    def test_mountpoint_empty(self, mock_disk_partitions):
        mock_disk_partitions.return_value = []
        self.assertIsNone(mountpoint(Path("/dev/sda1")))


class TestFindLargestPartition(unittest.TestCase):
    def _lsblk_json(self, blockdevices):
        return json.dumps({"blockdevices": blockdevices})

    @patch("storage_test.sp.check_output")
    def test_find_largest_partition_nominal(self, mock_check_output):
        mock_check_output.return_value = self._lsblk_json(
            [
                {
                    "name": "sda1",
                    "size": 1000,
                    "type": "part",
                    "fstype": "ext4",
                },
                {
                    "name": "sda2",
                    "size": 2000,
                    "type": "part",
                    "fstype": "ext4",
                },
            ]
        )
        self.assertEqual(
            find_largest_partition(Path("/dev/sda")), Path("/dev/sda2")
        )

    @patch("storage_test.sp.check_output")
    def test_find_largest_partition_skips_luks_and_disk(
        self, mock_check_output
    ):
        mock_check_output.return_value = self._lsblk_json(
            [
                {
                    "name": "sda",
                    "size": 5000,
                    "type": "disk",
                    "fstype": None,
                },
                {
                    "name": "sda1",
                    "size": 4000,
                    "type": "part",
                    "fstype": "crypto_LUKS",
                },
                {
                    "name": "sda2",
                    "size": 1000,
                    "type": "part",
                    "fstype": "ext4",
                },
            ]
        )
        self.assertEqual(
            find_largest_partition(Path("/dev/sda")), Path("/dev/sda2")
        )

    @patch("storage_test.sp.check_output")
    def test_find_largest_partition_no_candidates(self, mock_check_output):
        mock_check_output.return_value = self._lsblk_json(
            [
                {
                    "name": "sda",
                    "size": 5000,
                    "type": "disk",
                    "fstype": None,
                },
            ]
        )
        with self.assertRaises(SystemExit):
            find_largest_partition(Path("/dev/sda"))

    @patch("storage_test.sp.check_output")
    def test_find_largest_partition_unexpected_type(self, mock_check_output):
        mock_check_output.return_value = json.dumps([])
        with self.assertRaises(TypeError):
            find_largest_partition(Path("/dev/sda"))


class TestDevmapperName(unittest.TestCase):
    @patch("storage_test.Path.read_text", return_value="mapper_name\n")
    @patch("storage_test.Path.is_dir", return_value=True)
    def test_devmapper_name_found(self, mock_is_dir, mock_read_text):
        self.assertEqual(devmapper_name("dm-0"), "mapper_name")

    @patch("storage_test.Path.is_dir", return_value=False)
    def test_devmapper_name_not_found(self, mock_is_dir):
        self.assertIsNone(devmapper_name("sda"))


class TestMountUnmount(unittest.TestCase):
    @patch("storage_test.sp.check_call")
    def test_mount(self, mock_check_call):
        mount(Path("/dev/sda1"), Path("/mnt/point"))
        mock_check_call.assert_called_once_with(
            ["mount", Path("/dev/sda1"), Path("/mnt/point")]
        )

    @patch("storage_test.sp.check_call")
    def test_unmount(self, mock_check_call):
        unmount(Path("/mnt/point"))
        mock_check_call.assert_called_once_with(["umount", Path("/mnt/point")])


class TestRunBonnie(unittest.TestCase):
    @patch("storage_test.memory", return_value=8000)
    @patch("storage_test.free_space", return_value=16000)
    @patch("storage_test.sp.check_call")
    def test_run_bonnie(self, mock_check_call, mock_free_space, mock_memory):
        run_bonnie(Path("/test_dir"))
        mock_check_call.assert_called_once_with(
            [
                "bonnie++",
                "-d",
                PosixPath("/test_dir"),
                "-u",
                "root",
                "-r",
                "8000",
            ]
        )

    @patch("storage_test.memory", return_value=8000)
    @patch("storage_test.free_space", return_value=1000)
    @patch("storage_test.sp.check_call")
    def test_run_bonnie_low_free_space(
        self, mock_check_call, mock_free_space, mock_memory
    ):
        run_bonnie(Path("/test_dir"))
        mock_check_call.assert_called_once_with(
            [
                "bonnie++",
                "-d",
                PosixPath("/test_dir"),
                "-u",
                "root",
                "-r",
                "250.0",
            ]
        )


class TestDevmapperTest(unittest.TestCase):
    @patch("storage_test.run_bonnie")
    @patch("storage_test.mountpoint", return_value=Path("/mnt/point"))
    def test_devmapper_test_already_mounted(
        self, mock_mountpoint, mock_run_bonnie
    ):
        devmapper_test("dm-0")
        mock_run_bonnie.assert_called_once_with(Path("/mnt/point"))

    @patch("storage_test.unmount")
    @patch("storage_test.mount")
    @patch("storage_test.run_bonnie")
    @patch("storage_test.tempfile.mkdtemp", return_value="/tmp/mockdir")
    @patch("storage_test.os.rmdir")
    @patch("storage_test.devmapper_name", return_value=None)
    @patch("storage_test.mountpoint", return_value=None)
    def test_devmapper_test_not_mounted(
        self,
        mock_mountpoint,
        mock_devmapper_name,
        mock_rmdir,
        mock_mkdtemp,
        mock_run_bonnie,
        mock_mount,
        mock_unmount,
    ):
        devmapper_test("dm-0")
        mock_mount.assert_called_once_with(
            Path("/dev/dm-0"), Path("/tmp/mockdir")
        )
        mock_run_bonnie.assert_called_once_with(Path("/tmp/mockdir"))
        mock_unmount.assert_called_once_with(Path("/tmp/mockdir"))


class TestDiskTest(unittest.TestCase):
    @patch("storage_test.run_bonnie")
    @patch(
        "storage_test.find_largest_partition",
        return_value=Path("/dev/sda1"),
    )
    @patch("storage_test.mountpoint", return_value=Path("/mnt/point"))
    def test_disk_test_already_mounted(
        self, mock_mountpoint, mock_find_largest_partition, mock_run_bonnie
    ):
        disk_test("sda")
        mock_run_bonnie.assert_called_once_with(Path("/mnt/point"))

    @patch("storage_test.unmount")
    @patch("storage_test.mount")
    @patch("storage_test.run_bonnie")
    @patch("storage_test.tempfile.mkdtemp", return_value="/tmp/mockdir")
    @patch("storage_test.os.rmdir")
    @patch(
        "storage_test.find_largest_partition",
        return_value=Path("/dev/sda1"),
    )
    @patch("storage_test.mountpoint", return_value=None)
    def test_disk_test_not_mounted(
        self,
        mock_mountpoint,
        mock_find_largest_partition,
        mock_rmdir,
        mock_mkdtemp,
        mock_run_bonnie,
        mock_mount,
        mock_unmount,
    ):
        disk_test("sda")
        mock_mount.assert_called_once_with(
            Path("/dev/sda1"), Path("/tmp/mockdir")
        )
        mock_run_bonnie.assert_called_once_with(Path("/tmp/mockdir"))
        mock_unmount.assert_called_once_with(Path("/tmp/mockdir"))


class TestMain(unittest.TestCase):
    @patch("storage_test.os.getuid", return_value=0)
    @patch("storage_test.devmapper_name", return_value=None)
    @patch("storage_test.disk_test")
    def test_main_disk_test(
        self, mock_disk_test, mock_devmapper_name, mock_getuid
    ):
        with patch("sys.argv", ["storage_test.py", "sda"]):
            main()
            mock_disk_test.assert_called_once_with("sda")

    @patch("storage_test.os.getuid", return_value=0)
    @patch("storage_test.devmapper_name", return_value="mapper_name")
    @patch("storage_test.devmapper_test")
    def test_main_devmapper_test(
        self, mock_devmapper_test, mock_devmapper_name, mock_getuid
    ):
        with patch("sys.argv", ["storage_test.py", "sda"]):
            main()
            mock_devmapper_test.assert_called_once_with("sda")

    @patch("storage_test.os.getuid", return_value=0)
    @patch("builtins.print")
    def test_main_ignore_mtdblock(self, mock_print, mock_getuid):
        with patch("sys.argv", ["storage_test.py", "mtdblock0"]):
            main()
            mock_print.assert_called_with("Ignoring mtdblock device")

    @patch("storage_test.os.getuid", return_value=1000)
    def test_main_requires_root(self, mock_getuid):
        with patch("sys.argv", ["storage_test.py", "sda"]):
            with self.assertRaises(SystemExit):
                main()


if __name__ == "__main__":
    unittest.main()
