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

from unittest import TestCase
from unittest.mock import MagicMock, patch, mock_open
import sriov


class TestSriovFunctions(TestCase):
    @patch("sriov.distro.version", return_value="24.04")
    @patch("sriov.logging.info")
    def test_check_ubuntu_version_valid(self, mock_logging, mock_version):
        sriov.check_ubuntu_version()
        mock_logging.assert_called_with("The system is 24.04 or greater, proceed")

    @patch("sriov.distro.version", return_value="22.04")
    @patch("sriov.logging.info")
    @patch("sriov.sys.exit")
    def test_check_ubuntu_version_invalid(self, mock_exit, mock_logging, mock_version):
        sriov.check_ubuntu_version()
        mock_logging.assert_called_with("24.04 or greater is required, this is 22.04")
        mock_exit.assert_called_once_with(1)

    @patch("distro.version", side_effect=Exception("Mocked exception"))
    @patch("sys.exit")
    @patch("logging.info")
    def test_check_ubuntu_version_exception(self, mock_logging, mock_exit, mock_distro_version):
        sriov.check_ubuntu_version()

        # Verify that the exception was logged
        mock_logging.assert_any_call("An error occurred: Mocked exception")

        # Verify that sys.exit(1) was called
        mock_exit.assert_called_once_with(1)

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='0x8086')
    @patch("sriov.logging.info")
    def test_check_interface_vendor_intel(self, mock_logging, mock_open, mock_exists):
        sriov.check_interface_vendor("eth0")
        mock_logging.assert_called_with("The interface eth0 is a(n) Intel NIC")

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='0x15b3')
    @patch("sriov.logging.info")
    def test_check_interface_vendor_mellanox(self, mock_logging, mock_open, mock_exists):
        sriov.check_interface_vendor("eth0")
        mock_logging.assert_called_with("The interface eth0 is a(n) Mellanox NIC")

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='0x14e4')
    @patch("sriov.logging.info")
    @patch("sriov.sys.exit")
    def test_check_interface_vendor_broadcom(self, mock_exit, mock_logging, mock_open, mock_exists):
        sriov.check_interface_vendor("eth0")
        mock_logging.assert_called_with("Broadcom SRIOV testing is not supported at this time")
        mock_exit.assert_called_once_with(1)        

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='0x0000')
    @patch("sriov.logging.info")
    @patch("sriov.sys.exit")
    def test_check_interface_vendor_unknown(self, mock_exit, mock_logging, mock_open, mock_exists):
        sriov.check_interface_vendor("eth0")
        mock_logging.assert_called_with("eth0 has an unknown vendor  ID 0x0000")
        mock_exit.assert_called_once_with(1)

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", side_effect=Exception("File read error"))
    @patch("sys.exit")  # Mock sys.exit to prevent actual exit
    def test_check_interface_vendor_exception(self, mock_exit, mock_open, mock_exists):
        with self.assertLogs(level="INFO") as log:
            sriov.check_interface_vendor("eth0")

        mock_exit.assert_called_once_with(1)
        self.assertIn("An error occurred: File read error", log.output[0])

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    @patch("sriov.logging.info")
    def test_is_sriov_capable(self, mock_logging, mock_open, mock_exists):
        sriov.is_sriov_capable("eth0")
        mock_logging.assert_any_call("SR-IOV enabled with 1 VFs on interface eth0.")

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

    @patch("sriov.check_ubuntu_version")
    @patch("sriov.check_interface_vendor")
    @patch("sriov.is_sriov_capable")
    @patch("sriov.LXD")
    @patch("sriov.logging.info")
    def test_test_lxd_sriov(self, mock_logging, mock_lxd, mock_sriov_capable, mock_check_vendor, mock_check_version):
        mock_instance = MagicMock()
        mock_lxd.return_value.__enter__.return_value = mock_instance
        args = MagicMock()
        args.interface = "eth0"
        args.template = "template"
        args.rootfs = "rootfs"

        sriov.test_lxd_sriov(args)

        mock_check_version.assert_called_once()
        mock_check_vendor.assert_called_once_with("eth0")
        mock_sriov_capable.assert_called_once_with("eth0")
        mock_instance.run.assert_any_call("lxc network create lab_sriov --type=sriov parent=eth0")
        mock_instance.launch.assert_called_once()
        mock_instance.wait_until_running.assert_called_once()
        mock_instance.run.assert_any_call("bash -c \"lspci | grep Virtual\"", on_guest=True)
        mock_instance.run.assert_any_call("lxc network delete lab_sriov")

    @patch("sriov.check_ubuntu_version")
    @patch("sriov.check_interface_vendor")
    @patch("sriov.is_sriov_capable")
    @patch("sriov.LXDVM")
    @patch("sriov.logging.info")
    def test_test_lxd_vm_sriov(self, mock_logging, mock_lxdvm, mock_sriov_capable, mock_check_vendor, mock_check_version):
        mock_instance = MagicMock()
        mock_lxdvm.return_value.__enter__.return_value = mock_instance
        args = MagicMock()
        args.interface = "eth0"
        args.template = "template"
        args.image = "image"

        sriov.test_lxd_vm_sriov(args)

        mock_check_version.assert_called_once()
        mock_check_vendor.assert_called_once_with("eth0")
        mock_sriov_capable.assert_called_once_with("eth0")
        mock_instance.run.assert_any_call("lxc network create lab_sriov --type=sriov parent=eth0")
        mock_instance.launch.assert_called_once()
        mock_instance.wait_until_running.assert_called_once()
        mock_instance.run.assert_any_call("bash -c \"lspci | grep Virtual\"", on_guest=True)
        mock_instance.run.assert_any_call("lxc network delete lab_sriov")

    @patch("sys.argv", ["sriov.py", "lxd", "--interface", "eth0"])
    @patch("sriov.test_lxd_sriov")
    @patch("sriov.logging.basicConfig")
    def test_main(self, mock_logging_config, mock_test_lxd_sriov):
        with patch("sys.exit") as mock_exit:
            sriov.main()
            mock_test_lxd_sriov.assert_called_once()


if __name__ == "__main__":
    unittest.main()
