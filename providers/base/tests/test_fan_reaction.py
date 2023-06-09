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
import tempfile
from io import StringIO
from unittest.mock import Mock, patch
from contextlib import redirect_stdout
from unittest.mock import patch, mock_open

from fan_reaction_test import FanMonitor


class FanMonitorTests(unittest.TestCase):

    """Tests for several type of sysfs hwmon fan files."""
    """
    def test_simple(self):
        # Mock the glob.glob function to return a fan path
        with patch('glob.glob') as mock_glob:
            mock_glob.return_value = ['/sys/class/hwmon/hwmon1/fan1_input']
            fan_monitor = FanMonitor()
            # Mock the open function to return a mocked file objects
            with patch('builtins.open') as mock_open:
                mock_open.return_value.__enter__().read.return_value = '1000'
                rpm = fan_monitor.get_rpm()
                self.assertEqual(rpm, {'hwmon1/fan1_input': 1000})

    def test_multiple(self):
        # Mock the glob.glob function to return a list of fan paths
        with patch('glob.glob') as mock_glob:
            mock_glob.return_value = [
                '/sys/class/hwmon/hwmon1/fan1_input',
                '/sys/class/hwmon/hwmon2/fan2_input'
            ]
            fan_monitor = FanMonitor()
            # Mock the open function to return a mocked file objects
            with patch('builtins.open') as mock_open:
                mock_open.return_value.__enter__().read.return_value = '1000'
                rpm = fan_monitor.get_rpm()
                self.assertEqual(rpm, {
                    'hwmon1/fan1_input': 1000,
                    'hwmon2/fan2_input': 1000
                })

    def test_discard_gpu_fan(self):
        # Mock the glob.glob function to return a fan path
        with patch('glob.glob') as mock_glob:
            mock_glob.return_value = ['/sys/class/hwmon/hwmon1/fan1_input']
            fan_monitor = FanMonitor()
            # Mock the open function to return a mocked file objects
            with patch('builtins.open') as mock_open:
                mock_open.return_value.__enter__().read.return_value = '1000'
                rpm = fan_monitor.get_rpm()
                self.assertEqual(rpm, {'hwmon1/fan1_input': 1000})
    # fan_input_file = /tmp/tmpzd_44yuk/fan1_input
    # fan_input_file = /tmp/tmpagzm5dbm/amdgpu-1002-7340/fan1_input

    """
    # """
    @patch('glob.glob')
    @patch('os.path.realpath')
    def test_discard_gpu_fan(self, realpath_mock, glob_mock):
        with tempfile.TemporaryDirectory() as fake_sysfs:
            amdgpu_hwmon = os.path.join(fake_sysfs, 'amdgpu-1002-7340')
            amdgpu_pci = os.path.join(amdgpu_hwmon, 'device')
            os.makedirs(amdgpu_pci)
            amdgpu_fan_input_file = os.path.join(amdgpu_hwmon, 'fan1_input')
            print()
            print(amdgpu_fan_input_file)
            print()
            with open(amdgpu_fan_input_file, 'w') as f:
                f.write('65536')
            glob_mock.return_value = [amdgpu_fan_input_file]
            realpath_mock.return_value = \
                ("/sys/devices/pci0000:00/0000:00:01.0/0000:01:00.0/"
                 "0000:02:00.0/0000:03:00.0")
            # The following call is patching open(pci_class_path, 'r')
            with patch("builtins.open", mock_open(read_data='0x030000')) as f:
                with self.assertRaises(SystemExit) as cm:
                    with redirect_stdout(StringIO()):
                        FanMonitor()
                the_exception = cm.exception
                self.assertEqual(the_exception.code, 0)
    """
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

    """
if __name__ == '__main__':
    unittest.main()
