#!/usr/bin/env python3
# Copyright 2015-2020 Canonical Ltd.
# Written by:
#   Shawn Wang <shawn.wang@canonical.com>
#   Jonathan Cave <jonathan.cave@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import unittest
from unittest import mock
from unittest.mock import patch
import sys

import recovery_info


class FunctionTests(unittest.TestCase):

    """Tests for several functions."""

    @mock.patch('subprocess.check_output')
    def test_get_recovery_package(self, mock_subprocess_check_output):
        """Smoke test for get_recovery_package()."""
        mock_subprocess_check_output.return_value = """\
dell-recovery:
  Installed: 1.11
  Candidate: 1.11
  Version table:
     1.11
        500 https://archive/cesg-mirror/ test/public amd64 Packages
"""
        self.assertEqual(recovery_info.get_recovery_package(),
                         "dell-recovery_1.11")

    @mock.patch('subprocess.check_output')
    def test_get_recovery_partition(self, mock_subprocess_check_output):
        """Smoke test for get_recovery_partition()."""
        mock_subprocess_check_output.return_value = (
            b'TYPE FSTYPE NAME LABEL\n'
            b'disk linux_raid_member sda fx:2x250GB\n'
            b'raid1 bcache md127 \n'
            b'disk ext4 bcache0 Ultra\n'
            b'disk linux_raid_member sdb fx:2x250GB\n'
            b'raid1 bcache md127 \n'
            b'disk ext4 bcache0 Ultra\n'
            b'disk  sdc \n'
            b'part btrfs sdc1 vol1\n'
            b'disk  sdd \n'
            b'part ntfs sdd1 Windows\x208.1\n'
            b'part  sdd2 \n'
            b'part ext4 sdd5 Utopic\n'
            b'part swap sdd6 \n'
            b'disk bcache sde \n'
            b'disk ext4 bcache0 Ultra\n'
            b'disk  sdf \n'
            b'part ntfs sda3 RECOVERY\n')
        self.assertEqual(recovery_info.get_recovery_partition(),
                         ("DELL", "/dev/sda3"))

    def test_lsblk_unescape(self):
        """Smoke tests for lsblk_unescape()."""
        self.assertEqual(recovery_info.lsblk_unescape(
            'Windows\\x208.1'), 'Windows 8.1')
        self.assertEqual(recovery_info.lsblk_unescape(
            'Windows XP'), 'Windows XP')


class MountedPartitionTests(unittest.TestCase):

    """Unittest of MountedPartition."""

    @mock.patch('subprocess.check_output')
    def test_with_of_MountedPartition(self, mock_subprocess_check_output):
        """Test mount point."""
        test_dir = ""
        with recovery_info.MountedPartition("/dev/test") as tmp:
            test_dir = tmp
            self.assertTrue(os.path.exists(test_dir))
            mock_subprocess_check_output.assert_has_calls(
                [mock.call(['mount', '/dev/test', test_dir],
                           universal_newlines=True)])
        self.assertFalse(os.path.exists(test_dir))
        mock_subprocess_check_output.assert_has_calls(
            [mock.call(['umount', test_dir],
                       universal_newlines=True)])


class RecoveryInfoTests(unittest.TestCase):

    """Tests for RecoveryInfo."""

    @mock.patch('recovery_info.get_recovery_package')
    @mock.patch('recovery_info.get_recovery_partition')
    def test_smoke(self, mock_get_recovery_partition,
                   mock_get_recovery_package):
        """Smoke tests for running recovery_info."""
        mock_get_recovery_partition.return_value = ("DELL", "/dev/sda3")
        mock_get_recovery_package.return_value = "dell-recovery_1.11"

        testargs = ["recovery_info.py"]
        with patch.object(sys, 'argv', testargs):
            self.assertIsNone(recovery_info.RecoveryInfo().main())

        testargs = ["recovery_info.py", "checktype", "HP"]
        with patch.object(sys, 'argv', testargs):
            with self.assertRaises(SystemExit):
                recovery_info.RecoveryInfo().main()

        testargs = ["recovery_info.py", "checktype", "DELL"]
        with patch.object(sys, 'argv', testargs):
            self.assertIsNone(recovery_info.RecoveryInfo().main())
