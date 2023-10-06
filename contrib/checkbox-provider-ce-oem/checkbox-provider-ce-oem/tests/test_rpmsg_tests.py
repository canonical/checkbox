import unittest
import rpmsg_tests
from unittest.mock import patch

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
        /sys/devices/soc0/family and machine fils not exists
        """
        cpu_family = ""
        with patch("rpmsg_tests.get_soc_machine") as mock_machine:
            mock_machine.return_value = ""
            with patch("rpmsg_tests.get_soc_family") as mock_family:
                mock_family.return_value = ""
                cpu_family = rpmsg_tests.detect_arm_processor_type()

        self.assertEqual("unknown", cpu_family)
