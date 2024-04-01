import unittest
import sys
from unittest.mock import patch, MagicMock
sys.modules["systemd"] = MagicMock()
sys.modules["serial_test"] = MagicMock()
sys.modules["serial_test"].client_mode = MagicMock(
                                    side_effect=SystemExit(0))
import rpmsg_tests


class RpmsgTests(unittest.TestCase):
    """
    Unit tests for RPMSG test scripts
    """

    def test_rpmsg_device_exist(self):
        """
        Checking RPMSG device is available
        """
        rpmsg_devices = None
        expected_node = "virtio0.rpmsg-openamp-demo-channel.-1.30"
        with patch("os.listdir") as mock_listdir:
            mock_listdir.return_value = [expected_node]
            rpmsg_devices = rpmsg_tests.check_rpmsg_device()

        self.assertEqual([expected_node], rpmsg_devices)

    def test_rpmsg_device_not_exist(self):
        """
        Checking RPMSG device is not available
        """
        with patch("os.listdir") as mock_listdir:
            mock_listdir.return_value = []

            with self.assertRaises(SystemExit):
                rpmsg_tests.check_rpmsg_device()

    def test_arm_processor_am62(self):
        """
        Checking if the CPU processor manufacture is TI
        """
        cpu_family = ""
        with patch("rpmsg_tests.get_soc_machine") as mock_machine:
            mock_machine.return_value = "Texas Instruments AM625 SK"
            with patch("rpmsg_tests.get_soc_family") as mock_family:
                mock_family.return_value = "AM62X"
                cpu_family = rpmsg_tests.detect_arm_processor_type()

        self.assertEqual("ti", cpu_family)

    def test_arm_processor_imx(self):
        """
        Checking if the CPU processor manufacture is i.MX
        """
        cpu_family = ""
        with patch("rpmsg_tests.get_soc_machine") as mock_machine:
            mock_machine.return_value = "Honeywell i.MX8MM X8Med35 PDK"
            with patch("rpmsg_tests.get_soc_family") as mock_family:
                mock_family.return_value = "Freescale i.MX"
                cpu_family = rpmsg_tests.detect_arm_processor_type()

        self.assertEqual("imx", cpu_family)

    def test_arm_processor_unexpected(self):
        """
        /sys/devices/soc0/family and machine files not exists
        """
        cpu_family = ""
        with patch("rpmsg_tests.get_soc_machine") as mock_machine:
            mock_machine.return_value = ""
            with patch("rpmsg_tests.get_soc_family") as mock_family:
                mock_family.return_value = ""
                cpu_family = rpmsg_tests.detect_arm_processor_type()

        self.assertEqual("unknown", cpu_family)

    def test_rpmsg_test_supported_with_imx(self):
        """
        RPMSG TTY test is supported for i.MX
        """
        pattern, cmd = rpmsg_tests.rpmsg_tty_test_supported("imx")
        self.assertEqual(pattern, r"ttyRPMSG[0-9]*")
        self.assertEqual(cmd, "modprobe imx_rpmsg_tty")

    def test_rpmsg_test_supported_with_ti(self):
        """
        RPMSG TTY test is not supported for TI
        """
        with self.assertRaisesRegex(
                SystemExit, "Unsupported method for TI."):
            rpmsg_tests.rpmsg_tty_test_supported("ti")

    def test_rpmsg_test_supported_with_other(self):
        """
        RPMSG TTY test is not supported for Other SoC
        """
        with self.assertRaisesRegex(
                SystemExit, "Unexpected CPU type."):
            rpmsg_tests.rpmsg_tty_test_supported("mtk")

    @patch("rpmsg_tests.check_rpmsg_tty_devices")
    def test_no_rpmsg_devices(self, mock_check_rpmsg_tty_devices):
        """
        No RPMSG TTY devices found and raise SystemExit
        """
        mock_check_rpmsg_tty_devices.return_value = []
        with self.assertRaisesRegex(
                SystemExit, "No RPMSG TTY devices found."):
            rpmsg_tests.serial_tty_test("imx", 64)

    @patch("rpmsg_tests.check_rpmsg_tty_devices")
    def test_rpmsg_test_passed(self,
                               mock_check_rpmsg_tty_devices):
        """
        String-ECHO test passed through RPMSG TTY device
        """
        mock_check_rpmsg_tty_devices.return_value = ["/dev/ttyRPMSG30"]

        with self.assertRaises(SystemExit):
            rpmsg_tests.serial_tty_test("imx", 64)
