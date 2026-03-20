import io
import json
from unittest import TestCase
from unittest.mock import patch, mock_open

from checkbox_ng.support import device_info


class TestDeviceInfoCLI(TestCase):
    def test_get_kernel_cmdline(self):
        read_data = "BOOT_IMAGE=/boot/vmlinuz-6.17.0-1012-oem quiet splash\n"
        with patch("builtins.open", mock_open(read_data=read_data)) as _:
            returned = device_info.get_kernel_cmdline()
            expected = "BOOT_IMAGE=/boot/vmlinuz-6.17.0-1012-oem quiet splash"
            self.assertEqual(returned, expected)

    @patch("checkbox_ng.support.device_info.subprocess.check_output")
    @patch("checkbox_ng.support.device_info.parse_udevadm_output")
    def test_get_devices(self, mock_parse_udevadm, mock_co):
        device_info.get_devices()
        self.assertTrue(mock_co.called)
        self.assertTrue(mock_parse_udevadm.called)

    @patch("checkbox_ng.support.device_info.subprocess.check_output")
    def test_get_debian_packages(self, mock_co):
        mock_co.return_value = "7zip\t23.01+dfsg-11\tamd64\naccountsservice\t23.13.9-2ubuntu6\tamd64\n"
        pkg = device_info.get_debian_packages()
        self.assertEqual(len(pkg), 2)
        self.assertEqual(pkg[0]["name"], "7zip")
        self.assertEqual(pkg[0]["version"], "23.01+dfsg-11")
        self.assertEqual(pkg[0]["architecture"], "amd64")

    @patch("glob.glob")
    def test_get_bios_info_success(self, mock_glob):
        """Test successful retrieval of multiple BIOS files."""
        # Setup mocks
        mock_glob.return_items = [
            "/sys/class/dmi/id/bios_vendor",
            "/sys/class/dmi/id/bios_version",
        ]
        mock_glob.return_value = mock_glob.return_items

        # Use a mapping for mock_open to return different data for different files
        file_contents = {
            "/sys/class/dmi/id/bios_vendor": "Dell Inc.",
            "/sys/class/dmi/id/bios_version": "1.5.0",
        }

        def side_effect_open(filename, mode):
            content = file_contents.get(filename, "")
            return mock_open(read_data=content).return_value

        with patch("builtins.open", side_effect=side_effect_open):
            result = device_info.get_bios_info()

            self.assertEqual(result["bios_vendor"], "Dell Inc.")
            self.assertEqual(result["bios_version"], "1.5.0")
            self.assertEqual(len(result), 2)

    @patch("glob.glob")
    def test_get_bios_info_empty(self, mock_glob):
        """Test behavior when no bios_* files are found."""
        mock_glob.return_value = []

        result = device_info.get_bios_info()

        self.assertEqual(result, {})

    @patch("glob.glob")
    @patch("os.path.basename")
    def test_get_bios_info_permission_denied(self, mock_basename, mock_glob):
        """Test behavior when a file exists but cannot be read."""
        mock_glob.return_value = ["/sys/class/dmi/id/bios_version"]
        mock_basename.return_value = "bios_version"

        # Force a PermissionError when trying to open the file
        with patch("builtins.open", side_effect=PermissionError):
            result = device_info.get_bios_info()
            self.assertEqual(result, {})

    @patch("checkbox_ng.support.device_info.get_debian_packages")
    @patch("checkbox_ng.support.device_info.get_devices")
    @patch("checkbox_ng.support.device_info.get_release_info")
    @patch("checkbox_ng.support.device_info.get_meminfo")
    @patch("checkbox_ng.support.device_info.get_snap_packages")
    @patch("checkbox_ng.support.device_info.get_uname")
    @patch("checkbox_ng.support.device_info.get_kernel_cmdline")
    def test_kernel_cmdline_subcommand_uses_only_kernel_getter(
        self,
        mock_kernel_cmdline,
        mock_uname,
        mock_snap_packages,
        mock_meminfo,
        mock_release_info,
        mock_devices,
        mock_debian_packages,
    ):
        mock_kernel_cmdline.return_value = "splash quiet"
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            device_info.main(["kernel_cmdline"])

        self.assertEqual(
            json.loads(mock_stdout.getvalue()),
            "splash quiet",
        )
        mock_kernel_cmdline.assert_called_once_with()
        mock_uname.assert_not_called()
        mock_meminfo.assert_not_called()
        mock_release_info.assert_not_called()
        mock_devices.assert_not_called()
        mock_snap_packages.assert_not_called()
        mock_debian_packages.assert_not_called()
