#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024-2025 Canonical Ltd.
# Authors:
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
#   Jeffery Yen <songpao2262gmail.com>
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
import subprocess
import contextlib
from unittest.mock import patch, MagicMock, call

from checkbox_support.scripts.usb_read_write import (
    mount_usb_storage,
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


class TestMountUsbStorage(unittest.TestCase):
    @patch("checkbox_support.scripts.usb_read_write.subprocess.call")
    @patch(
        "checkbox_support.scripts.usb_read_write.os.path.join",
        return_value="/dev/sda1",
    )
    @patch("checkbox_support.scripts.usb_read_write.sys.exit")
    def test_mount_usb_storage_success(self, mock_exit, mock_join, mock_call):
        """
        Test the success scenario:
          - Simulate that all subprocess.call calls return 0 (success),
            with the mount command returning 0 to indicate a successful mount.
          - Verify that the following commands are called in order:
              1. ["sync"]
              2. ["udevadm", "settle", "--timeout=10"]
              3. ["umount", FOLDER_TO_MOUNT] (here we patch FOLDER_TO_MOUNT to
                 "/mnt/usb")
              4. ["umount", "/dev/sda1"]
              5. ["mount", "/dev/sda1", "/mnt/usb"]
          - Upon exiting the context, the finally block should also call
            unmount on the folder (["umount", "/mnt/usb"]).
          - And sys.exit should not be called.
        """

        # Simulate that all the calls are passing
        mock_call.return_value = 0

        # Patch FOLDER_TO_MOUNT to be "/mnt/usb"
        with patch(
            "checkbox_support.scripts.usb_read_write.FOLDER_TO_MOUNT",
            "/mnt/usb",
        ):
            # Enter the mount_usb_storage context using a context manager
            with contextlib.ExitStack() as stack:
                stack.enter_context(mount_usb_storage("sda1"))
                # When entering the context, the following commands should be
                # executed in order:
                expected_calls_entry = [
                    call(["sync"]),
                    call(["udevadm", "settle", "--timeout=10"]),
                    call(["umount", "/mnt/usb"], stderr=subprocess.PIPE),
                    call(["umount", "/dev/sda1"], stderr=subprocess.PIPE),
                    call(["mount", "/dev/sda1", "/mnt/usb"]),
                ]
                for expected in expected_calls_entry:
                    self.assertIn(expected, mock_call.call_args_list)
            # When exiting the context, the finally block should execute:
            expected_final_call = call(["umount", "/mnt/usb"])
            self.assertIn(expected_final_call, mock_call.call_args_list)
        # Ensure that sys.exit was not called
        mock_exit.assert_not_called()

    @patch("checkbox_support.scripts.usb_read_write.subprocess.call")
    @patch("logging.error")
    def test_mount_usb_storage_failure(self, mock_log, mock_call):
        """
        Test the failure scenario:
          - Simulate that the mount command returns 1 (failure).
          - The program should call sys.exit(1) and raise a SystemExit.
        """

        def call_side_effect(args, **kwargs):
            if args[0] == "mount":
                return 1  # Simulate mount failure
            else:
                return 0

        mock_call.side_effect = call_side_effect

        with patch(
            "checkbox_support.scripts.usb_read_write.FOLDER_TO_MOUNT",
            "/mnt/usb",
        ):
            with self.assertRaises(SystemExit) as context:
                with mount_usb_storage("sda1"):
                    # As soon as we enter the context, a non-zero return from
                    # mount should trigger sys.exit(1)
                    pass

        self.assertEqual(context.exception.code, 1)

        # Verify that the program logs the error message
        mock_log.assert_called_once_with("mount /dev/sda1 on /mnt/usb failed.")


if __name__ == "__main__":
    unittest.main()
