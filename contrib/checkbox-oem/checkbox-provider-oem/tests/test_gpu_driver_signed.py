import unittest
from unittest.mock import patch, mock_open
import subprocess
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))

from gpu_driver_signed import (
    get_gpu_addresses,
    has_gpu_driver,
    has_nvidia_signature,
    has_nvidia_package_support,
    get_nvidia_version_modinfo,
)


class TestGpuDriverSigned(unittest.TestCase):

    @patch("subprocess.check_output")
    def test_get_gpu_addresses(self, mock_subprocess):
        """Test getting GPU PCI addresses from lspci."""
        mock_subprocess.side_effect = [
            "00:02.0 VGA compatible controller [0300]: Intel Corporation Device [8086:a7a0] (rev 04)\n",
            "01:00.0 3D controller [0302]: NVIDIA Corporation Device [10de:25e2] (rev a1)\n",
            "",  # No 0380 class devices
        ]

        gpus = get_gpu_addresses()
        self.assertEqual(gpus, ["00:02.0", "01:00.0"])

    @patch("os.readlink")
    @patch("os.path.isdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_has_gpu_driver_with_driver(
        self, mock_file, mock_isdir, mock_readlink
    ):
        """Test GPU with driver bound (nvidia case)."""
        mock_file.return_value.read.side_effect = ["0x10de", "0x25e2"]
        mock_isdir.return_value = True
        mock_readlink.return_value = "/sys/bus/pci/drivers/nvidia"

        result = has_gpu_driver("01:00.0")
        self.assertTrue(result)

    @patch("subprocess.run")
    @patch("os.path.isdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_has_gpu_driver_without_driver(
        self, mock_file, mock_isdir, mock_run
    ):
        """Test GPU without driver bound."""
        mock_file.return_value.read.side_effect = ["0x10de", "0x25e2"]
        mock_isdir.return_value = False

        result = has_gpu_driver("01:00.0")
        self.assertFalse(result)
        # Verify lspci was called for debugging
        mock_run.assert_called_once_with(
            ["lspci", "-nnvk", "-s", "0000:01:00.0"]
        )

    def test_has_nvidia_signature_signed(self):
        """Test NVIDIA driver with Canonical signature."""
        modinfo_output = """filename:       /lib/modules/6.8.0-49-generic/kernel/drivers/video/nvidia.ko
version:        535.274.02
signer:         Canonical Ltd. Kernel Module Signing
sig_key:        XX:XX:XX:XX
sig_hashalgo:   sha512"""

        result = has_nvidia_signature(modinfo_output, "535.274.02")
        self.assertTrue(result)

    @patch("subprocess.check_output")
    def test_has_nvidia_signature_not_signed(self, mock_subprocess):
        """Test NVIDIA driver without Canonical signature."""
        mock_subprocess.return_value = "6.8.0-49-generic"

        modinfo_output = """filename:       /lib/modules/6.8.0-49-generic/kernel/drivers/video/nvidia.ko
version:        535.274.02
signer:         Some Other Signer
sig_key:        XX:XX:XX:XX
sig_hashalgo:   sha512"""

        result = has_nvidia_signature(modinfo_output, "535.274.02")
        self.assertFalse(result)

    @patch("subprocess.check_output")
    def test_has_nvidia_package_support_lts(self, mock_subprocess):
        """Test NVIDIA driver with LTS support."""
        mock_subprocess.return_value = """Package: nvidia-driver-535
Version: 535.274.02-0ubuntu0.24.04.1
Support: LTSB
Description: NVIDIA driver"""

        result = has_nvidia_package_support("535.274.02")
        self.assertTrue(result)

    @patch("subprocess.check_output")
    def test_has_nvidia_package_support_production(self, mock_subprocess):
        """Test NVIDIA driver with production support."""
        mock_subprocess.return_value = """Package: nvidia-driver-535
Version: 535.274.02-0ubuntu0.24.04.1
Support: PB
Description: NVIDIA driver"""

        result = has_nvidia_package_support("535.274.02")
        self.assertTrue(result)

    @patch("subprocess.check_output")
    def test_get_nvidia_version_present(self, mock_subprocess):
        """Test getting NVIDIA version when driver is present."""
        mock_subprocess.return_value = """filename:       /lib/modules/6.8.0-49-generic/kernel/drivers/video/nvidia.ko
version:        535.274.02
signer:         Canonical Ltd. Kernel Module Signing
sig_key:        XX:XX:XX:XX
sig_hashalgo:   sha512"""

        version, modinfo_output = get_nvidia_version_modinfo()
        self.assertEqual(version, "535.274.02")
        self.assertIn("version:        535.274.02", modinfo_output)

    @patch("subprocess.check_output")
    def test_get_nvidia_version_not_present(self, mock_subprocess):
        """Test getting NVIDIA version when driver is not present."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            1, "modinfo"
        )

        version, modinfo_output = get_nvidia_version_modinfo()
        self.assertIsNone(version)
        self.assertIsNone(modinfo_output)


if __name__ == "__main__":
    unittest.main()
