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

    def test_simple(self):
        # Mock the glob.glob function to return a fan path
        with patch("glob.glob") as mock_glob:
            mock_glob.return_value = ["/sys/class/hwmon/hwmon1/fan1_input"]
            with patch("os.path.realpath") as mock_path:
                mock_path.return_value = "foo"
                fan_monitor = FanMonitor()
                # Mock the open function to return a mocked file objects
                with patch("builtins.open") as mock_open:
                    mock_open.return_value.__enter__().read.return_value = (
                        "1000"
                    )
                    rpm = fan_monitor.get_rpm()
                    self.assertEqual(rpm, {"hwmon1/fan1_input": 1000})

    def test_multiple(self):
        # Mock the glob.glob function to return a list of fan paths
        with patch("glob.glob") as mock_glob:
            mock_glob.return_value = [
                "/sys/class/hwmon/hwmon1/fan1_input",
                "/sys/class/hwmon/hwmon2/fan2_input",
            ]
            with patch("os.path.realpath") as mock_path:
                mock_path.return_value = "foo"
                fan_monitor = FanMonitor()
                with patch("builtins.open") as mock_open:
                    mock_open.return_value.__enter__().read.return_value = (
                        "1000"
                    )
                    rpm = fan_monitor.get_rpm()
                    self.assertEqual(
                        rpm,
                        {"hwmon1/fan1_input": 1000, "hwmon2/fan2_input": 1000},
                    )

    def test_discard_gpu_fan(self):
        # Testing if GPU fan will be discard or not, so pci code & path should be mocked
        with patch("glob.glob") as mock_glob:
            mock_glob.return_value = ["/sys/class/hwmon/hwmon1/fan1_input"]
            # Mock the open function to return a mocked file objects
            with patch("os.path.realpath") as mock_path:
                mock_path.return_value = (
                    "/sys/devices/pci0000:00/0000:00:01.0/0000:01:00.0"
                )
                with patch("builtins.open") as mock_open:
                    mock_open.return_value.__enter__().read.return_value = (
                        "0x030000"
                    )
                    # This test case includes the possibility that there is no CPU fan
                    # If considering the absence of a CPU fan as a failure, then modification is needed here
                    # (Because there is no CPU fan to test with)
                    with self.assertRaises(SystemExit) as cm:
                        with redirect_stdout(StringIO()) as stdout:
                            FanMonitor()

                    the_exception = cm.exception
                    self.assertEqual(the_exception.code, 0)

    def test_discard_gpu_fan_keep_cpu_fan(self):
        with patch("glob.glob") as mock_glob:
            mock_glob.return_value = [
                "/sys/class/hwmon/hwmon1/fan1_input",  # GPU
                "/sys/class/hwmon/hwmon2/fan2_input",  # CPU
            ]
            with patch("os.path.realpath") as mock_path:
                # Mock the return value of the first fan path (GPU fan)
                mock_path.side_effect = [
                    # Each section is a PCI address (Domain:Bus:Device.Function)
                    # In this case, the GPU has a 4-layer structure
                    "/sys/devices/pci0000:00/0000:00:01.0/0000:01:00.0/0000:02:00.0/0000:03:00.0",
                    "foo",
                ]
                with patch("builtins.open") as mock_open:
                    # Mock the return values for the two fans
                    mock_open.return_value.__enter__().read.return_value = (
                        "0x030000"
                    )
                    fan_monitor = FanMonitor()
                    with patch("builtins.open") as mock_open:
                        mock_open.return_value.__enter__().read.return_value = (
                            "1000"
                        )
                        rpm = fan_monitor.get_rpm()
                        self.assertEqual(rpm, {"hwmon2/fan2_input": 1000})
