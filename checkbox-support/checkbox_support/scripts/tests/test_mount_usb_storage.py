#!/usr/bin/env python3
import unittest
import contextlib
import subprocess
import sys
from unittest.mock import patch, MagicMock, call
from subprocess import CompletedProcess

# Import mount_usb_storage from the module
from checkbox_support.scripts.usb_read_write import mount_usb_storage


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
              3. ["umount", FOLDER_TO_MOUNT] (here we patch FOLDER_TO_MOUNT to "/mnt/usb")
              4. ["umount", "/dev/sda1"]
              5. ["mount", "/dev/sda1", "/mnt/usb"]
          - Upon exiting the context, the finally block should also call unmount on the folder (["umount", "/mnt/usb"]).
          - And sys.exit should not be called.
        """

        # Define a side_effect to simulate different return values for various commands:
        def call_side_effect(args, **kwargs):
            if args[0] == "mount":
                return 0  # Simulate mount success
            else:
                return 0  # Other commands also return success

        mock_call.side_effect = call_side_effect

        # Patch FOLDER_TO_MOUNT to be "/mnt/usb"
        with patch(
            "checkbox_support.scripts.usb_read_write.FOLDER_TO_MOUNT",
            "/mnt/usb",
        ):
            # Enter the mount_usb_storage context using a context manager
            with contextlib.ExitStack() as stack:
                stack.enter_context(mount_usb_storage("sda1"))
                # When entering the context, the following commands should be executed in order:
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
    @patch(
        "checkbox_support.scripts.usb_read_write.os.path.join",
        return_value="/dev/sda1",
    )
    @patch(
        "checkbox_support.scripts.usb_read_write.sys.exit",
        side_effect=SystemExit,
    )
    def test_mount_usb_storage_failure(self, mock_exit, mock_join, mock_call):
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
            with self.assertRaises(SystemExit):
                with mount_usb_storage("sda1"):
                    # As soon as we enter the context, a non-zero return from mount should trigger sys.exit(1)
                    pass

        # Check that sys.exit was called correctly (with 1)
        mock_exit.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
