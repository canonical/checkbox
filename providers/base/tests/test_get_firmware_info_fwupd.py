import os
import unittest
from unittest.mock import patch
from get_firmware_info_fwupd import get_firmware_info_fwupd


class TestGetFirmwareInfo(unittest.TestCase):

    @patch("subprocess.run")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_firmware_data_by_fwupd_snap(
            self, mock_snapd, mock_subporcess):

        mock_snapd.return_value = True
        get_firmware_info_fwupd()
        mock_snapd.assert_called_with("fwupd")
        mock_subporcess.assert_called_with(
            ['fwupd.fwupdmgr', 'get-devices', '--json'])

    @patch.dict(os.environ, {"SNAP": "checkbox-snap"})
    @patch("json.loads")
    @patch("subprocess.run")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_firmware_data_by_fwupd1914_deb_on_checkbox_snap(
            self, mock_snapd, mock_subporcess, mock_json):

        mock_snapd.return_value = False
        mock_json.return_value = {
            "Versions": [
                {
                    "Type": "runtime",
                    "AppstreamId": "org.freedesktop.fwupd",
                    "Version": "1.9.14"
                }
            ]
        }
        get_firmware_info_fwupd()
        mock_snapd.assert_called_with("fwupd")
        mock_subporcess.assert_called_with(
            ['fwupdmgr', 'get-devices', '--json'])
        self.assertEqual(
            os.environ.get("SNAP"), "checkbox-snap")

    @patch.dict(os.environ, {"SNAP": "checkbox-snap"})
    @patch("json.loads")
    @patch("subprocess.run")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_firmware_data_by_fwupd_deb_on_checkbox_snap(
            self, mock_snapd, mock_subporcess, mock_json):

        mock_snapd.return_value = False
        mock_json.return_value = {
            "Versions": [
                {
                    "Type": "runtime",
                    "AppstreamId": "org.freedesktop.fwupd",
                    "Version": "1.7.9"
                }
            ]
        }
        get_firmware_info_fwupd()
        mock_snapd.assert_called_with("fwupd")
        mock_subporcess.assert_called_with(
            ['fwupdmgr', 'get-devices', '--json'])
        self.assertIsNone(os.environ.get("SNAP"))
