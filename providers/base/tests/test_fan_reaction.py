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

import glob
import os
import unittest
from unittest import mock
from unittest.mock import patch
import sys
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

    def fake_get_pci_addr(fakedir, addr):
        pci_class_path = fakedir + '/sys/bus/pci/devices/%s/class' % addr
        return pci_class_path

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
            amdgpu_pci_class = os.path.join(amdgpu_pci, 'class')
            with open(amdgpu_pci_class, 'w') as f:
                f.write('0x030000')
            glob_mock.return_value = [amdgpu_fan_input_file]
            realpath_mock.return_value = \
                    "/sys/devices/pci0000:00/0000:00:01.0/0000:01:00.0/" + \
                    "0000:02:00.0/0000:03:00.0"
            with self.assertRaises(SystemExit) as cm:
                fan_mon = FanMonitor()

            the_exception = cm.exception
            self.assertEqual(the_exception.code, 0)
