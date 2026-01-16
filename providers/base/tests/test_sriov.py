#!/usr/bin/env python3
"""
Unit Tests for sriov.py
Copyright (C) 2025 Canonical Ltd.

Author
    Michael Reed <michael.reed@canonical.com.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>

"""

import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch, mock_open
import sriov


class TestSriovFunctions(TestCase):
    @patch("sriov.get_release_to_test", return_value="24.04")
    @patch("sriov.logging.info")
    def test_check_ubuntu_version_valid(self, mock_logging, mock_get_release):
        sriov.check_ubuntu_version()
        mock_logging.assert_called_with(
            "The system is 24.04 or greater, proceed"
        )

    @patch("sriov.get_release_to_test", return_value="22.04")
    def test_check_ubuntu_version_invalid(self, mock_get_release):
        with self.assertRaises(ValueError) as context:
            sriov.check_ubuntu_version()

        self.assertEqual(
            str(context.exception),
            "Ubuntu 24.04 or greater is required, but found 22.04.",
        )

    @patch(
        "sriov.get_release_to_test", side_effect=Exception("Mocked exception")
    )
    def test_check_ubuntu_version_exception(self, mock_get_release):
        with self.assertRaises(Exception) as context:
            sriov.check_ubuntu_version()

        self.assertEqual(str(context.exception), "Mocked exception")

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="0x8086")
    @patch("sriov.logging.info")
    def test_check_interface_vendor_intel(
        self, mock_logging, mock_open, mock_exists
    ):
        sriov.check_interface_vendor("eth0")
        mock_logging.assert_called_with(
            "The interface %s is a(n) %s NIC", "eth0", "Intel"
        )

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="0x15b3")
    @patch("sriov.logging.info")
    def test_check_interface_vendor_mellanox(
        self, mock_logging, mock_open, mock_exists
    ):
        sriov.check_interface_vendor("eth0")
        mock_logging.assert_called_with(
            "The interface %s is a(n) %s NIC", "eth0", "Mellanox"
        )

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="0x14e4")
    @patch("sriov.logging.info")
    def test_check_interface_vendor_broadcom(
        self, mock_logging, mock_open, mock_exists
    ):
        sriov.check_interface_vendor("eth0")
        mock_logging.assert_called_with(
            "The interface %s is a(n) %s NIC", "eth0", "Broadcom"
        )

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="0x0000")
    def test_check_interface_vendor_unknown(self, mock_open, mock_exists):
        with self.assertRaises(ValueError) as context:
            sriov.check_interface_vendor("eth0")
        self.assertEqual(
            str(context.exception), "eth0 has an unknown vendor ID 0x0000"
        )

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", side_effect=Exception("File read error"))
    def test_check_interface_vendor_exception(self, mock_open, mock_exists):
        with self.assertRaises(Exception) as context:
            sriov.check_interface_vendor("eth0")
        self.assertEqual(str(context.exception), "File read error")

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    @patch("sriov.logging.info")
    def test_is_sriov_capable(self, mock_logging, mock_open, mock_exists):
        sriov.is_sriov_capable("eth0")
        mock_logging.assert_any_call(
            "SR-IOV enabled with 1 VFs on interface eth0."
        )

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", side_effect=IOError("Permission denied"))
    @patch("sys.exit")
    def test_sriov_ioerror(self, mock_exit, mock_open, mock_exists):
        """Test when opening the file raises IOError."""
        sriov.is_sriov_capable("eth0")
        mock_exit.assert_called_once_with(1)

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", side_effect=FileNotFoundError("File not found"))
    @patch("sys.exit")
    def test_sriov_filenotfound(self, mock_exit, mock_open, mock_exists):
        """Test when the sriov file is missing, raising FileNotFoundError."""
        sriov.is_sriov_capable("eth0")
        mock_exit.assert_called_once_with(1)

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", side_effect=Exception("Unknown error"))
    @patch("sys.exit")
    def test_sriov_general_exception(self, mock_exit, mock_open, mock_exists):
        """Test when a general exception occurs in is_sriov_capable."""
        sriov.is_sriov_capable("eth0")
        mock_exit.assert_called_once_with(1)

    @patch("sriov.cleanup_sriov")
    @patch("sriov.check_ubuntu_version")
    @patch("sriov.check_interface_vendor")
    @patch("sriov.is_sriov_capable")
    @patch("sriov.LXD")
    @patch("sriov.logging.info")
    def test_test_lxd_sriov(
        self,
        mock_logging,
        mock_lxd,
        mock_sriov_capable,
        mock_check_vendor,
        mock_check_version,
        mock_cleanup_sriov,
    ):
        mock_instance = MagicMock()
        mock_lxd.return_value.__enter__.return_value = mock_instance
        args = MagicMock()
        args.interface = "eth0"
        args.template = "template"
        args.rootfs = "rootfs"

        sriov.test_lxd_sriov(args)

        mock_check_vendor.assert_called_once_with("eth0")
        mock_sriov_capable.assert_called_once_with("eth0")
        mock_instance.run.assert_any_call(
            "lxc network create lab_sriov --type=sriov parent=eth0"
        )
        mock_instance.wait_until_running.assert_called_once_with()
        mock_instance.run.assert_any_call(
            'bash -c "lspci | grep Virtual"', on_guest=True
        )
        mock_instance.run.assert_any_call("lxc network delete lab_sriov")
        mock_cleanup_sriov.assert_called_once_with("eth0")

    @patch("sriov.cleanup_sriov")
    @patch("sriov.check_ubuntu_version")
    @patch("sriov.check_interface_vendor")
    @patch("sriov.is_sriov_capable")
    @patch("sriov.LXDVM")
    @patch("sriov.logging.info")
    def test_test_lxd_vm_sriov(
        self,
        mock_logging,
        mock_lxdvm,
        mock_sriov_capable,
        mock_check_vendor,
        mock_check_version,
        mock_cleanup_sriov,
    ):
        mock_instance = MagicMock()
        mock_lxdvm.return_value.__enter__.return_value = mock_instance
        args = MagicMock()
        args.interface = "eth0"
        args.template = "template"
        args.image = "image"

        sriov.test_lxd_vm_sriov(args)

        mock_check_vendor.assert_called_once_with("eth0")
        mock_sriov_capable.assert_called_once_with("eth0")
        mock_instance.run.assert_any_call(
            "lxc network create lab_sriov --type=sriov parent=eth0"
        )

        mock_instance.wait_until_running.assert_called_once_with()
        mock_instance.run.assert_any_call(
            'bash -c "lspci | grep Virtual"', on_guest=True
        )
        mock_instance.run.assert_any_call("lxc network delete lab_sriov")
        mock_cleanup_sriov.assert_called_once_with("eth0")

    @patch("sys.argv", ["sriov.py", "lxd", "--interface", "eth0"])
    @patch("sriov.test_lxd_sriov")
    @patch("sriov.logging.basicConfig")
    def test_main(self, mock_logging_config, mock_test_lxd_sriov):
        with patch("sys.exit"):
            sriov.main()

    @patch("sys.argv", ["sriov.py", "lxdvm", "--interface", "eth0"])
    @patch("sriov.test_lxd_vm_sriov")
    @patch("sriov.logging.basicConfig")
    def test_main_lxdvm(self, mock_logging_config, mock_test_lxd_vm_sriov):
        with patch("sys.exit"):
            sriov.main()

    @patch("os.path.exists", return_value=False)
    def test_check_interface_vendor_file_not_exists(self, mock_exists):
        with self.assertRaises(FileNotFoundError) as context:
            sriov.check_interface_vendor("eth0")
        self.assertEqual(
            str(context.exception),
            "Vendor ID path /sys/class/net/eth0/device/vendor not found",
        )

    @patch("os.path.exists", return_value=False)
    @patch("sys.exit")
    def test_is_sriov_capable_file_not_exists(self, mock_exit, mock_exists):
        with self.assertLogs(level="INFO") as log:
            sriov.is_sriov_capable("eth0")
        mock_exit.assert_called_once_with(1)
        self.assertIn(
            "Failed to enable SR-IOV on eth0: SR-IOV not supported "
            "or interface eth0 does not exist.",
            log.output[1],
        )

    def test_get_release_to_test_distro(self):
        with patch("distro.id", return_value="ubuntu"):
            with patch("distro.version", return_value="24.04"):
                result = sriov.get_release_to_test()
                self.assertEqual(result, "24.04")

    def test_get_release_to_test_ubuntu_core(self):
        with patch("distro.id", return_value="ubuntu-core"):
            with patch("distro.version", return_value="24"):
                result = sriov.get_release_to_test()
                self.assertEqual(result, "24.04")

    def test_get_release_to_test_import_error(self):
        with patch("builtins.__import__") as mock_import:
            # Mock lsb_release module
            mock_lsb_release = MagicMock()
            mock_lsb_release.get_distro_information.return_value = {
                "RELEASE": "24.04"
            }

            def side_effect(name, *args):
                if name == "distro":
                    raise ImportError("No module named 'distro'")
                elif name == "lsb_release":
                    return mock_lsb_release
                return __import__(name, *args)

            mock_import.side_effect = side_effect

            result = sriov.get_release_to_test()
            self.assertEqual(result, "24.04")
            mock_lsb_release.get_distro_information.assert_called_once_with()

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    @patch("sriov.logging.info")
    def test_cleanup_sriov_success(self, mock_logging, mock_open, mock_exists):
        """Test successful cleanup of SRIOV interface."""
        sriov.cleanup_sriov("eth0")

        mock_exists.assert_called_once_with(
            "/sys/class/net/eth0/device/sriov_numvfs"
        )
        mock_logging.assert_any_call("checking if sriov_numvfs exists")
        mock_logging.assert_any_call("Setting numvfs to zero")
        mock_open.assert_called_once_with(
            "/sys/class/net/eth0/device/sriov_numvfs", "w", encoding="utf-8"
        )
        mock_open().write.assert_called_once_with("0")

    @patch("os.path.exists", return_value=False)
    @patch("sriov.logging.info")
    @patch("sys.exit")
    def test_cleanup_sriov_file_not_exists(
        self, mock_exit, mock_logging, mock_exists
    ):
        """Test cleanup when SRIOV file does not exist."""
        sriov.cleanup_sriov("eth0")

        mock_exists.assert_called_once_with(
            "/sys/class/net/eth0/device/sriov_numvfs"
        )
        mock_logging.assert_any_call("checking if sriov_numvfs exists")
        mock_logging.assert_any_call(
            "Failed to disable SR-IOV on eth0: SR-IOV interface eth0 does not exist."
        )
        mock_exit.assert_called_once_with(1)

    @patch("os.path.exists", return_value=True)
    @patch(
        "builtins.open",
        side_effect=FileNotFoundError("File not found during write"),
    )
    @patch("sriov.logging.info")
    @patch("sys.exit")
    def test_cleanup_sriov_file_write_filenotfound(
        self, mock_exit, mock_logging, mock_open, mock_exists
    ):
        """Test cleanup when file write raises FileNotFoundError."""
        sriov.cleanup_sriov("eth0")

        mock_exists.assert_called_once_with(
            "/sys/class/net/eth0/device/sriov_numvfs"
        )
        mock_logging.assert_any_call("checking if sriov_numvfs exists")
        mock_logging.assert_any_call("Setting numvfs to zero")
        mock_logging.assert_any_call(
            "Failed to disable SR-IOV on eth0: File not found during write"
        )
        mock_exit.assert_called_once_with(1)

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", side_effect=IOError("Permission denied"))
    @patch("sriov.logging.info")
    @patch("sys.exit")
    def test_cleanup_sriov_ioerror(
        self, mock_exit, mock_logging, mock_open, mock_exists
    ):
        """Test cleanup when file write raises IOError."""
        sriov.cleanup_sriov("eth0")

        mock_exists.assert_called_once_with(
            "/sys/class/net/eth0/device/sriov_numvfs"
        )
        mock_logging.assert_any_call("checking if sriov_numvfs exists")
        mock_logging.assert_any_call("Setting numvfs to zero")
        mock_logging.assert_any_call("An error occurred: Permission denied")
        mock_exit.assert_called_once_with(1)

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", side_effect=Exception("Unexpected error"))
    @patch("sriov.logging.info")
    @patch("sys.exit")
    def test_cleanup_sriov_general_exception(
        self, mock_exit, mock_logging, mock_open, mock_exists
    ):
        """Test cleanup when file operations raise general Exception."""
        sriov.cleanup_sriov("eth0")

        mock_exists.assert_called_once_with(
            "/sys/class/net/eth0/device/sriov_numvfs"
        )
        mock_logging.assert_any_call("checking if sriov_numvfs exists")
        mock_logging.assert_any_call("Setting numvfs to zero")
        mock_logging.assert_any_call("An error occurred: Unexpected error")
        mock_exit.assert_called_once_with(1)

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    @patch("sriov.logging.info")
    def test_cleanup_sriov_different_interface(
        self, mock_logging, mock_open, mock_exists
    ):
        """Test cleanup with different interface name."""
        sriov.cleanup_sriov("enp0s3")

        mock_exists.assert_called_once_with(
            "/sys/class/net/enp0s3/device/sriov_numvfs"
        )
        mock_logging.assert_any_call("checking if sriov_numvfs exists")
        mock_logging.assert_any_call("Setting numvfs to zero")
        mock_open.assert_called_once_with(
            "/sys/class/net/enp0s3/device/sriov_numvfs", "w", encoding="utf-8"
        )
        mock_open().write.assert_called_once_with("0")


if __name__ == "__main__":
    unittest.main()
