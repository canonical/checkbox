#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Authors:
#   Fernando Bravo <daniel.manrique@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

import unittest
from unittest.mock import patch, MagicMock
import subprocess


from checkbox_support.scripts.usb_read_write import (
    write_test_unit,
)


class TestUsbReadWrite(unittest.TestCase):

    @patch("os.path")
    @patch("subprocess.Popen")
    @patch("subprocess.check_output")
    @patch("subprocess.run")
    def test_write_test_unit(
        self, mock_run, mock_check_output, mock_popen, mock_os
    ):
        mock_os.join.return_value = "output_file"

        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"2048+1 records in\n2048+1 records out\n1049076 bytes (1.0 MB) "
            b"copied, 0.00473357 s, 222 MB/s\n",
            None,
        )
        mock_popen.return_value = mock_process

        random_file = MagicMock()
        random_file.tfile.name = "random_file"
        write_test_unit(random_file)

        mock_popen.assert_called_once_with(
            [
                "dd",
                "if=random_file",
                "of=output_file",
                "bs=1M",
                "oflag=sync",
            ],
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            env={"LC_NUMERIC": "C"},
        )
        mock_popen.return_value.communicate.assert_called_with()

    @patch("os.path")
    @patch("subprocess.Popen")
    @patch("subprocess.check_output")
    @patch("subprocess.run")
    def test_write_test_unit_wrong_units(
        self, mock_run, mock_check_output, mock_popen, mock_os
    ):
        mock_os.join.return_value = "output_file"

        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"2048+1 records in\n2048+1 records out\n1049076 bytes (1.0 MB) "
            b"copied, 0.00473357 s, 222 ***/s\n",
            None,
        )
        mock_popen.return_value = mock_process

        random_file = MagicMock()
        random_file.tfile.name = "random_file"
        with self.assertRaises(SystemExit):
            write_test_unit(random_file)

    @patch("os.path")
    @patch("subprocess.Popen")
    @patch("subprocess.check_output")
    @patch("subprocess.run")
    def test_write_test_unit_io_error(
        self, mock_run, mock_check_output, mock_popen, mock_os
    ):
        mock_os.join.return_value = "output_file"

        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b"2048+1 records in\n2048+1 records out\n1049076 bytes (1.0 MB) "
            b"copied, 0.00473357 s, 222 MBs\n",
            None,
        )
        mock_popen.return_value = mock_process

        dmesg = MagicMock()
        dmesg.stdout.decode.return_value = "I/O error"
        mock_run.return_value = dmesg

        random_file = MagicMock()
        random_file.tfile.name = "random_file"
        with self.assertRaises(SystemExit):
            write_test_unit(random_file)
