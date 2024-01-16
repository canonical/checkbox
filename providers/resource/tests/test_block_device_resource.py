import unittest
import textwrap
import block_device_resource
from subprocess import CalledProcessError
from unittest.mock import patch, mock_open, MagicMock


class TestDeviceState(unittest.TestCase):
    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("os.readlink")
    def test_device_state_removable(
        self, mock_readlink, mock_listdir, mock_exists
    ):
        mock_readlink.return_value = "/sys/bus/usb/devices/usb1"
        mock_exists.return_value = True
        mock_listdir.return_value = ["usb1"]
        result = block_device_resource.device_state("sda")
        self.assertEqual(result, "removable")

    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("os.readlink")
    def test_device_state_internal(
        self, mock_readlink, mock_listdir, mock_exists
    ):
        mock_readlink.return_value = "/sys/bus/sata/devices/sata1"
        mock_exists.return_value = False
        result = block_device_resource.device_state("sdb")
        self.assertEqual(result, "internal")


class TestUsbSupport(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="3.00")
    @patch("os.readlink")
    def test_usb_support_supported(self, mock_readlink, mock_file):
        mock_readlink.return_value = "/dev/usb12ab/1-1.2/1-1.2:1.0"
        result = block_device_resource.usb_support("sda", 2.00)
        self.assertEqual(result, "supported")

    @patch("builtins.open", new_callable=mock_open, read_data="1.00")
    @patch("os.readlink")
    def test_usb_support_unsupported(self, mock_readlink, mock_file):
        mock_readlink.return_value = "/dev/usb12ab/1-1.2/1-1.2:1.0"
        result = block_device_resource.usb_support("sda", 3.00)
        self.assertEqual(result, "unsupported")


class TestDeviceRotation(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="1")
    @patch("os.path.exists")
    def test_device_rotation_spinning(self, mock_path_exists, mock_file):
        mock_path_exists.return_value = True
        result = block_device_resource.device_rotation("sda")
        self.assertEqual(result, "yes")

    @patch("builtins.open", new_callable=mock_open, read_data="0")
    @patch("os.path.exists")
    def test_device_rotation_non_spinning(self, mock_path_exists, mock_file):
        mock_path_exists.return_value = True
        result = block_device_resource.device_rotation("sdb")
        self.assertEqual(result, "no")


class TestSmartSupportDiskInfo(unittest.TestCase):
    def test_smart_supporting_diskinfo_supported(self):
        diskinfo = ["SMART support is: Available", "other info"]
        result = block_device_resource.smart_supporting_diskinfo(diskinfo)
        self.assertTrue(result)

    def test_smart_supporting_diskinfo_unsupported(self):
        diskinfo = ["Some other line", "more info"]
        result = block_device_resource.smart_supporting_diskinfo(diskinfo)
        self.assertFalse(result)

    @patch("block_device_resource.check_output")
    def test_smart_support_enabled(self, mock_check_output):
        mock_check_output.return_value = textwrap.dedent(
            """
            Some intro information on the drive
            === START OF SMART DATA SECTION ===
            SMART overall-health self-assessment test result: PASSED
            """
        )

        result = block_device_resource.smart_support("sda")
        self.assertEqual(result, "True")

    @patch("block_device_resource.check_output")
    def test_smart_support_disabled(self, mock_check_output):
        mock_check_output.return_value = (
            "some output indicating no SMART support"
        )

        result = block_device_resource.smart_support("sdb")
        self.assertEqual(result, "False")

    @patch("block_device_resource.check_output")
    def test_smart_support_enabled_raid(self, mock_check_output):
        mock_check_output.side_effect = [
            textwrap.dedent(
                """
                Some intro information of the drive in raid
                Raid configuration: some -d 3ware,N
                """
            ),
            # here we are checking inside the raid checking function
            textwrap.dedent(
                """
                Some intro information of the drive in raid
                """
            ),
            # Note: at least one disk in the raid doesn't support SMART,
            #       we report true here as this will make the subsequent
            #       test fail as this is likely to be a mistake from the OEM
            textwrap.dedent(
                """
                Some intro information of the drive in raid
                === START OF SMART DATA SECTION ===
                SMART overall-health self-assessment test result: PASSED
                """
            ),
            CalledProcessError("cmd", 1),
        ]

        result = block_device_resource.smart_support("sdb")
        self.assertEqual(result, "True")

    @patch("block_device_resource.check_output")
    def test_smart_support_disabled_raid(self, mock_check_output):
        mock_check_output.side_effect = [
            textwrap.dedent(
                """
                Some intro information of the drive in raid
                Raid configuration: some -d 3ware,N
                """
            ),
            # here we are checking inside the raid checking function
            textwrap.dedent(
                """
                Some intro information of the drive in raid
                """
            ),
            textwrap.dedent(
                """
                Some intro information of the drive in raid
                """
            ),
            CalledProcessError("cmd", 1),
        ]

        result = block_device_resource.smart_support("sdb")
        self.assertEqual(result, "False")


class TestMainFunction(unittest.TestCase):
    @patch("block_device_resource.Path.glob")
    @patch("block_device_resource.device_state")
    @patch("block_device_resource.usb_support")
    @patch("block_device_resource.device_rotation")
    @patch("block_device_resource.smart_support")
    def test_block_device_resource_main(
        self,
        mock_smart_support,
        mock_device_rotation,
        mock_usb_support,
        mock_device_state,
        mock_path_glob,
    ):
        device = MagicMock()
        device.name = "device"
        device.parent.name = "sda"
        # Mocking Path.glob to simulate disk names
        mock_path_glob.return_value = [device]

        # Mocking other functions to return specific values
        mock_device_state.return_value = "internal"
        mock_usb_support.side_effect = (
            lambda name, version: "supported"
            if version == 3.00
            else "unsupported"
        )
        mock_device_rotation.return_value = "yes"
        mock_smart_support.return_value = "True"

        # Capturing the output of print statements
        with patch("block_device_resource.print") as mocked_print:
            block_device_resource.main()

            # Verifying the output
            expected_output = textwrap.dedent(
                """
                name: sda
                state: internal
                usb2: unsupported
                usb3: supported
                rotation: yes
                smart: True
                """
            ).lstrip()

            mocked_print.assert_called_with(expected_output)
