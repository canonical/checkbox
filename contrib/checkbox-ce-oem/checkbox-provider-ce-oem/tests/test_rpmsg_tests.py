import unittest
import sys
import argparse
from unittest.mock import patch, MagicMock, Mock

sys.modules["systemd"] = MagicMock()

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
        with self.assertRaisesRegex(SystemExit, "Unsupported method for TI."):
            rpmsg_tests.rpmsg_tty_test_supported("ti")

    def test_rpmsg_test_supported_with_other(self):
        """
        RPMSG TTY test is not supported for Other SoC
        """
        with self.assertRaisesRegex(SystemExit, "Unexpected CPU type."):
            rpmsg_tests.rpmsg_tty_test_supported("mtk")


class TestRpmsgPingPong(unittest.TestCase):

    @patch("rpmsg_tests.RpmsgPingPongTest.__init__")
    @patch("rpmsg_tests.RpmsgPingPongTest.pingpong_test")
    def test_pingpong_entry_imx(self, mock_pingpong, mock_init):

        mock_init.return_value = None
        rpmsg_tests.pingpong_test("imx")
        mock_init.assert_called_with(
            "imx_rpmsg_pingpong",
            "modprobe imx_rpmsg_pingpong",
            r"get .* \(src: (\w*)\)",
            r"rpmsg.*: goodbye!",
            51,
        )
        mock_pingpong.assert_called_with()

    @patch("rpmsg_tests.RpmsgPingPongTest.__init__")
    @patch("rpmsg_tests.RpmsgPingPongTest.pingpong_test")
    def test_pingpong_entry_ti(self, mock_pingpong, mock_init):

        mock_init.return_value = None
        rpmsg_tests.pingpong_test("ti")
        mock_init.assert_called_with(
            "rpmsg_client_sample",
            "modprobe rpmsg_client_sample count=100",
            r".*ti.ipc4.ping-pong.*\(src: (\w*)\)",
            r"rpmsg.*: goodbye!",
            100,
        )
        mock_pingpong.assert_called_with()

    @patch("rpmsg_tests.RpmsgPingPongTest.__init__")
    @patch("rpmsg_tests.RpmsgPingPongTest.pingpong_test")
    def test_pingpong_entry_failed(self, mock_pingpong, mock_init):

        mock_init.return_value = None
        with self.assertRaises(SystemExit):
            rpmsg_tests.pingpong_test("unknown")
        mock_init.assert_not_called()
        mock_pingpong.assert_not_called()


class TestRpmsgSerialTty(unittest.TestCase):

    @patch("serial_test.client_mode")
    @patch("serial_test.Serial")
    @patch("rpmsg_tests.check_rpmsg_tty_devices")
    def test_no_rpmsg_devices(
        self, mock_check_rpmsg_tty_devices, mock_serial, mock_client_mode
    ):
        """
        No RPMSG TTY devices found and raise SystemExit
        """
        mock_serial.return_value = []
        mock_check_rpmsg_tty_devices.return_value = []
        with self.assertRaisesRegex(SystemExit, "No RPMSG TTY devices found."):
            rpmsg_tests.serial_tty_test("imx", 64)
            mock_serial.assert_not_called()
            mock_client_mode.assert_not_called()

    @patch("serial_test.client_mode")
    @patch("serial_test.Serial")
    @patch("rpmsg_tests.check_rpmsg_tty_devices")
    def test_rpmsg_tty_test_passed(
        self, mock_check_rpmsg_tty_devices, mock_serial, mock_client_mode
    ):
        """
        String-ECHO test passed through RPMSG TTY device
        """
        serial_dev = "serial-dev"
        tty_device = "/dev/ttyRPMSG30"
        mock_check_rpmsg_tty_devices.return_value = [tty_device]
        mock_serial.return_value = serial_dev

        rpmsg_tests.serial_tty_test("imx", 64)
        mock_serial.assert_called_with(
            tty_device, "rpmsg-tty", [], 115200, 8, "N", 1, 3, 1024
        )
        mock_client_mode.assert_called_with(serial_dev, 64)

    @patch("rpmsg_tests.serial_tty_test")
    @patch("rpmsg_tests.pingpong_test")
    @patch("rpmsg_tests.check_rpmsg_device")
    def test_launch_check_rpmsg_device(
        self, mock_check_rpmsg, mock_pingpong, mock_stty
    ):

        mock_args = Mock(return_value=argparse.Namespace(type="detect"))
        rpmsg_tests.main(mock_args())
        mock_check_rpmsg.assert_called_with()
        mock_pingpong.assert_not_called()
        mock_stty.assert_not_called()

    @patch("rpmsg_tests.serial_tty_test")
    @patch("rpmsg_tests.check_rpmsg_device")
    @patch("rpmsg_tests.detect_arm_processor_type")
    @patch("rpmsg_tests.pingpong_test")
    def test_launch_pingpong_test(
        self, mock_pingpong, mock_detect_arch, mock_check_rpmsg, mock_stty
    ):

        mock_args = Mock(return_value=argparse.Namespace(type="pingpong"))
        mock_detect_arch.return_value = "imx"
        rpmsg_tests.main(mock_args())
        mock_pingpong.assert_called_with("imx")
        mock_detect_arch.assert_called_with()
        mock_check_rpmsg.assert_not_called()
        mock_stty.assert_not_called()

    @patch("rpmsg_tests.check_rpmsg_device")
    @patch("rpmsg_tests.pingpong_test")
    @patch("rpmsg_tests.detect_arm_processor_type")
    @patch("rpmsg_tests.serial_tty_test")
    def test_launch_serial_tty_test(
        self, mock_stty, mock_detect_arch, mock_pingpong, mock_check_rpmsg
    ):

        mock_args = Mock(return_value=argparse.Namespace(type="serial-tty"))
        mock_detect_arch.return_value = "imx"
        rpmsg_tests.main(mock_args())
        mock_stty.assert_called_with("imx", 1024)
        mock_detect_arch.assert_called_with()
        mock_pingpong.assert_not_called()
        mock_check_rpmsg.assert_not_called()

    def test_argument_parser(self):
        sys.argv = ["rpmsg_tests.py", "--type", "detect"]
        args = rpmsg_tests.register_arguments()

        self.assertEqual(args.type, "detect")
