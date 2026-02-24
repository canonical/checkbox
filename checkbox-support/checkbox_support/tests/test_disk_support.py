#!/usr/bin/env python3
# encoding: UTF-8
# Copyright (c) 2026 Canonical Ltd.
#
# Authors:
#     Rod Smith <rod.smith@canonical.com> using CoPilot
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import unittest
from unittest.mock import patch, MagicMock
from subprocess import CalledProcessError

from checkbox_support import disk_support

GiB = 1024 * 1024 * 1024


class TestDiskSupport(unittest.TestCase):
    @patch("checkbox_support.disk_support.check_output")
    def test_get_partition_data_with_type(self, mock_check_output):
        # blockdev returns size, blkid returns TYPE=...
        def _side_effect(args, *a, **kw):
            # args is a list produced by shlex.split, first element is the
            # command
            if args[0] == "blockdev":
                return b"%d" % (5 * GiB)
            if args[0] == "blkid":
                # simulate blkid -o export output; code looks for tokens
                # containing "TYPE"
                return b"TYPE=ext4"
            raise AssertionError("Unexpected command: %r" % (args,))

        mock_check_output.side_effect = _side_effect
        result = disk_support.get_partition_data("sda1")
        self.assertEqual(result["name"], "sda1")
        self.assertEqual(result["size"], 5 * GiB)
        self.assertEqual(result["fs_type"], "ext4")

    @patch("checkbox_support.disk_support.check_output")
    def test_get_partition_data_no_blkid(self, mock_check_output):
        # blkid raises CalledProcessError -> fs_type should be empty
        def _side_effect(args, *a, **kw):
            if args[0] == "blockdev":
                return b"1024"
            if args[0] == "blkid":
                raise CalledProcessError(2, "blkid")
            raise AssertionError("Unexpected command: %r" % (args,))

        mock_check_output.side_effect = _side_effect
        result = disk_support.get_partition_data("sda2")
        self.assertEqual(result["name"], "sda2")
        self.assertEqual(result["size"], 1024)
        self.assertEqual(result["fs_type"], "")

    @patch("checkbox_support.disk_support.check_output")
    def test_find_mount_point_mounted_and_unmounted(self, mock_check_output):
        # Mounted case
        mock_check_output.return_value = (
            b"Filesystem      1K-blocks Used Available Use% Mounted on\n"
            b"/dev/sda1 10000 5000 5000 50% /mnt/data\n"
        )
        mp = disk_support.find_mount_point("sda1")
        self.assertEqual(mp, "/mnt/data")

        # Unmounted case: df will return "/dev" as final token
        mock_check_output.return_value = (
            b"Filesystem      1K-blocks Used Available Use% Mounted on\n"
            b"/dev 0 0 0 0% /dev\n"
        )
        mp = disk_support.find_mount_point("sda9")
        self.assertIsNone(mp)

    @patch("checkbox_support.disk_support.stat.S_ISBLK")
    @patch("checkbox_support.disk_support.os.stat")
    def test_is_block_device_true_false_and_missing(
        self, mock_stat, mock_s_isblk
    ):
        # Prepare an instance without running __init__ to avoid touching sysfs
        disk = object.__new__(disk_support.Disk)
        disk.device = "/dev/sda"

        # When os.stat returns a mode and S_ISBLK returns True
        mock_stat.return_value = MagicMock(st_mode=123)
        mock_s_isblk.return_value = True
        self.assertTrue(disk.is_block_device())

        # When S_ISBLK returns False
        mock_s_isblk.return_value = False
        self.assertFalse(disk.is_block_device())

        # FileNotFoundError should return False
        mock_stat.side_effect = FileNotFoundError()
        self.assertFalse(disk.is_block_device())

    def test_get_mount_point_accessor(self):
        disk = object.__new__(disk_support.Disk)
        disk.mount_point = "/mnt/foo"
        self.assertEqual(disk.get_mount_point(), "/mnt/foo")

    def test_find_largest_partition_selection(self):
        # Create Disk instance without running __init__ and set all_parts
        disk = object.__new__(disk_support.Disk)
        disk.MIN_SZ = 10 * GiB
        # The method will initialize largest_part and unsupported_fs internally
        disk.all_parts = [
            # small supported (below MIN_SZ)
            {
                "name": "sda1",
                "size": 5 * GiB,
                "part_type": "partition",
                "fs_type": "ext4",
            },
            # large unsupported (should become unsupported_fs)
            {
                "name": "sda2",
                "size": 20 * GiB,
                "part_type": "partition",
                "fs_type": "ntfs",
            },
            # supported > MIN_SZ (candidate)
            {
                "name": "sda3",
                "size": 15 * GiB,
                "part_type": "partition",
                "fs_type": "ext4",
            },
            # LV with largest supported filesystem
            {
                "name": "dm-0",
                "size": 30 * GiB,
                "part_type": "lv",
                "fs_type": "ext4",
            },
        ]

        largest = disk.find_largest_partition()
        # The partition (not LV) with largest supported filesystem should be
        # selected
        self.assertEqual(largest["name"], "sda3")
        self.assertIsNotNone(disk.unsupported_fs)
        self.assertEqual(disk.unsupported_fs["name"], "sda2")

    @patch("checkbox_support.disk_support.os.makedirs")
    @patch("checkbox_support.disk_support.uuid.uuid1")
    def test_mount_filesystem_simulate(self, mock_uuid, mock_makedirs):
        # Prepare a Disk instance and stub find_largest_partition and
        # find_mount_point
        disk = object.__new__(disk_support.Disk)
        disk.device = "/dev/sda"
        disk.test_dir = "/tmp"
        disk.mount_point = ""

        target_part = {
            "name": "sda3",
            "size": 20 * GiB,
            "part_type": "partition",
            "fs_type": "ext4",
        }

        # Patch instance methods / module functions
        disk.find_largest_partition = MagicMock(return_value=target_part)
        with patch(
            "checkbox_support.disk_support.find_mount_point",
            return_value="/mnt/sda3",
        ):
            mock_uuid.return_value = "fixed-uuid"
            ok = disk.mount_filesystem(simulate=False)
            self.assertTrue(ok)
            # test_dir should be under the mount point and include the
            # stress-ng- prefix
            self.assertTrue(disk.test_dir.startswith("/mnt/sda3/stress-ng-"))


if __name__ == "__main__":
    unittest.main()
