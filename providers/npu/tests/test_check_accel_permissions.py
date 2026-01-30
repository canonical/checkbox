#!/usr/bin/env python3
import unittest
import io
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import check_accel_permissions


class TestFindNpuDevicePath(unittest.TestCase):
    @patch("check_accel_permissions.Path")
    def test_device_found(self, mock_path_class):
        # Mock that "/sys/class/accel" exists
        mock_base_path = MagicMock()
        mock_base_path.is_dir.return_value = True

        # Add accel0 into the folder
        mock_accel0 = MagicMock()
        mock_accel0.name = "accel0"
        mock_base_path.iterdir.return_value = [mock_accel0]

        # Mock for device_dir / "device" / "driver"
        mock_driver_path = MagicMock()
        mock_driver_path.readlink.return_value = Path(
            "../../bus/pci/drivers/intel_vpu"
        )
        mock_accel0.__truediv__.return_value.__truediv__.return_value = (
            mock_driver_path
        )

        # Mock for Path("/dev/accel") / device_dir.name
        mock_dev_base = MagicMock()
        mock_dev_device = MagicMock()
        mock_dev_device.exists.return_value = True
        mock_dev_base.__truediv__.return_value = mock_dev_device

        # Configure mock_path_class to return the correct mock for each path
        def path_side_effect(path_str):
            if path_str == "/sys/class/accel":
                return mock_base_path
            if path_str == "/dev/accel":
                return mock_dev_base
            return MagicMock()

        mock_path_class.side_effect = path_side_effect

        result = check_accel_permissions.find_npu_device_path()
        self.assertEqual(result, mock_dev_device)

    @patch("check_accel_permissions.Path")
    def test_no_sys_class_accel(self, mock_path_class):
        """Test when the base /sys/class/accel directory doesn't exist."""
        mock_base_path = MagicMock()
        mock_base_path.is_dir.return_value = False

        def path_side_effect(path_str):
            if path_str == "/sys/class/accel":
                return mock_base_path
            return MagicMock()

        mock_path_class.side_effect = path_side_effect

        with self.assertRaises(SystemExit):
            check_accel_permissions.find_npu_device_path()

    @patch("check_accel_permissions.Path")
    def test_wrong_driver(self, mock_path_class):
        """Test when a device exists but it's not the 'intel_vpu' driver."""
        mock_base_path = MagicMock()
        mock_base_path.is_dir.return_value = True

        mock_accel0 = MagicMock()
        mock_accel0.name = "accel0"
        mock_base_path.iterdir.return_value = [mock_accel0]

        # Mock for device_dir / "device" / "driver"
        mock_driver_path = MagicMock()
        mock_driver_path.readlink.return_value = Path(
            "../../bus/pci/drivers/other_driver"
        )
        mock_accel0.__truediv__.return_value.__truediv__.return_value = (
            mock_driver_path
        )

        def path_side_effect(path_str):
            if path_str == "/sys/class/accel":
                return mock_base_path
            return MagicMock()

        mock_path_class.side_effect = path_side_effect

        with self.assertRaises(SystemExit):
            check_accel_permissions.find_npu_device_path()

    @patch("check_accel_permissions.Path")  # Patches Path *within* the script
    def test_driver_found_but_dev_missing(self, mock_path_class):
        """Test when the sysfs entry exists, but the /dev/accel node does not."""
        mock_base_path = MagicMock()
        mock_base_path.is_dir.return_value = True

        mock_accel0 = MagicMock()
        mock_accel0.name = "accel0"
        mock_base_path.iterdir.return_value = [mock_accel0]

        # Mock for device_dir / "device" / "driver"
        mock_driver_path = MagicMock()
        mock_driver_path.readlink.return_value = Path(
            "../../bus/pci/drivers/intel_vpu"
        )
        mock_accel0.__truediv__.return_value.__truediv__.return_value = (
            mock_driver_path
        )

        mock_dev_base = MagicMock()
        mock_dev_device = MagicMock()
        # Here, the device doesn't exist
        mock_dev_device.exists.return_value = False
        mock_dev_base.__truediv__.return_value = mock_dev_device

        def path_side_effect(path_str):
            if path_str == "/sys/class/accel":
                return mock_base_path
            if path_str == "/dev/accel":
                return mock_dev_base
            return MagicMock()

        mock_path_class.side_effect = path_side_effect

        with self.assertRaises(SystemExit):
            check_accel_permissions.find_npu_device_path()

    @patch("check_accel_permissions.Path")
    def test_multiple_devices_first_missing_dev_second_ok(
        self, mock_path_class
    ):
        """Test finding the 2nd device if the 1st /dev node is missing."""
        mock_base_path = MagicMock()
        mock_base_path.is_dir.return_value = True

        mock_accel0 = MagicMock()
        mock_accel0.name = "accel0"
        mock_accel1 = MagicMock()
        mock_accel1.name = "accel1"
        mock_base_path.iterdir.return_value = [mock_accel0, mock_accel1]

        mock_driver_path0 = MagicMock()
        mock_driver_path0.readlink.return_value = Path(
            "../../bus/pci/drivers/intel_vpu"
        )
        mock_accel0.__truediv__.return_value.__truediv__.return_value = (
            mock_driver_path0
        )
        mock_driver_path1 = MagicMock()
        mock_driver_path1.readlink.return_value = Path(
            "../../bus/pci/drivers/intel_vpu"
        )
        mock_accel1.__truediv__.return_value.__truediv__.return_value = (
            mock_driver_path1
        )

        # Mock for Path("/dev/accel") / device_dir.name
        mock_dev_base = MagicMock()
        mock_dev_device0 = MagicMock()
        mock_dev_device0.exists.return_value = False
        mock_dev_device1 = MagicMock()
        mock_dev_device1.exists.return_value = True

        def dev_truediv_side_effect(name):
            if name == "accel0":
                return mock_dev_device0
            if name == "accel1":
                return mock_dev_device1
            return MagicMock()

        mock_dev_base.__truediv__.side_effect = dev_truediv_side_effect

        def path_side_effect(path_str):
            if path_str == "/sys/class/accel":
                return mock_base_path
            if path_str == "/dev/accel":
                return mock_dev_base
            return MagicMock()

        mock_path_class.side_effect = path_side_effect

        result = check_accel_permissions.find_npu_device_path()

        # Check that the correct device path is returned (the SECOND one)
        self.assertEqual(result, mock_dev_device1)

        # Verify it checked exists() for BOTH /dev nodes
        mock_dev_device0.exists.assert_called_with()
        mock_dev_device1.exists.assert_called_with()


class TestMainFunction(unittest.TestCase):
    @patch("os.access", return_value=True)
    @patch(
        "check_accel_permissions.find_npu_device_path",
        return_value=Path("/dev/accel0"),
    )
    def test_main_success(self, mock_find_device, mock_access):
        """Test the main success path: device found, permissions OK."""
        check_accel_permissions.main()

        # Check os.access was called for both Read and Write
        mock_access.assert_any_call(Path("/dev/accel0"), os.R_OK | os.W_OK)

    @patch("os.access", return_value=False)
    @patch(
        "check_accel_permissions.find_npu_device_path",
        return_value=Path("/dev/accel0"),
    )
    def test_main_no_rw_permission(self, mock_find_device, mock_access):
        """Test the main failure path: device found, but no RW permission."""
        with self.assertRaises(SystemExit):
            check_accel_permissions.main()


if __name__ == "__main__":
    unittest.main()
