#!/usr/bin/env python3
# Copyright 2020 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
from unittest.mock import patch, mock_open
import tempfile

from fan_reaction_test import FanMonitor


class FanMonitorTests(unittest.TestCase):

    """Tests for several type of sysfs hwmon fan files."""

    @mock.patch('glob.glob')
    @mock.patch.object(os.path, 'relpath', autospec=True)
    def test_simple(self, relpath_mock, glob_mock):
        with tempfile.TemporaryDirectory() as fake_sysfs:
            fan_input_file = os.path.join(fake_sysfs, 'fan1_input')
            with open(fan_input_file, 'w') as f:
                f.write('150')
            glob_mock.return_value = [fan_input_file]
            relpath_mock.side_effect = ['hwmon4/fan1_input']
            fan_mon = FanMonitor()
            self.assertEqual(fan_mon.get_rpm(), {'hwmon4/fan1_input': 150})

    @mock.patch('glob.glob')
    @mock.patch.object(os.path, 'relpath', autospec=True)
    def test_multiple(self, relpath_mock, glob_mock):
        with tempfile.TemporaryDirectory() as fake_sysfs:
            fan_input_file1 = os.path.join(fake_sysfs, 'fan1_input')
            with open(fan_input_file1, 'w') as f1:
                f1.write('150')
            fan_input_file2 = os.path.join(fake_sysfs, 'fan2_input')
            with open(fan_input_file2, 'w') as f2:
                f2.write('1318')
            glob_mock.return_value = [fan_input_file1, fan_input_file2]
            relpath_mock.side_effect = [
                'hwmon4/fan1_input', 'hwmon6/fan2_input']
            fan_mon = FanMonitor()
            self.assertEqual(
                fan_mon.get_rpm(),
                {'hwmon4/fan1_input': 150, 'hwmon6/fan2_input': 1318})

    @mock.patch('glob.glob')
    @mock.patch('os.path.realpath')
    def test_discard_gpu_fan(self, realpath_mock, glob_mock):
        with tempfile.TemporaryDirectory() as fake_sysfs:
            amdgpu_hwmon = os.path.join(fake_sysfs, 'amdgpu-1002-7340')
            amdgpu_pci = os.path.join(amdgpu_hwmon, 'device')
            os.makedirs(amdgpu_pci)
            amdgpu_fan_input_file = os.path.join(amdgpu_hwmon, 'fan1_input')
            with open(amdgpu_fan_input_file, 'w') as f:
                f.write('65536')
            glob_mock.return_value = [amdgpu_fan_input_file]
            realpath_mock.return_value = \
                ("/sys/devices/pci0000:00/0000:00:01.0/0000:01:00.0/"
                 "0000:02:00.0/0000:03:00.0")
            # The following call is patching open(pci_class_path, 'r')
            with patch("builtins.open", mock_open(read_data='0x030000')) as f:
                with self.assertRaises(SystemExit) as cm:
                    FanMonitor()
                the_exception = cm.exception
                self.assertEqual(the_exception.code, 0)

    @mock.patch('glob.glob')
    @mock.patch('os.path.realpath')
    @mock.patch.object(os.path, 'relpath', autospec=True)
    def test_discard_gpu_fan_keep_cpu_fan(
        self, relpath_mock, realpath_mock, glob_mock
    ):
        with tempfile.TemporaryDirectory() as fake_sysfs:
            amdgpu_hwmon = os.path.join(fake_sysfs, 'amdgpu-1002-7340')
            amdgpu_pci = os.path.join(amdgpu_hwmon, 'device')
            os.makedirs(amdgpu_pci)
            amdgpu_fan_input_file = os.path.join(amdgpu_hwmon, 'fan1_input')
            with open(amdgpu_fan_input_file, 'w') as f:
                f.write('65536')
            fan_input_file2 = os.path.join(fake_sysfs, 'fan2_input')
            with open(fan_input_file2, 'w') as f2:
                f2.write('412')
            glob_mock.return_value = [amdgpu_fan_input_file, fan_input_file2]
            realpath_mock.side_effect = [
                    "/sys/devices/pci0000:00/0000:00:01.0/0000:01:00.0/"
                    "0000:02:00.0/0000:03:00.0", "foo"]
            relpath_mock.side_effect = ['hwmon6/fan2_input']
            # The following call is patching open(pci_class_path, 'r')
            with patch("builtins.open", mock_open(read_data='0x030000')) as f:
                fan_mon = FanMonitor()
                self.assertEqual(len(fan_mon.hwmons), 1)
                self.assertTrue(fan_mon.hwmons[0].endswith('fan2_input'))
            self.assertEqual(
                fan_mon.get_rpm(), {'hwmon6/fan2_input': 412})
