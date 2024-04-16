import os
import json
import unittest
import subprocess
from unittest.mock import patch
import get_firmware_info_fwupd


class TestGetFirmwareInfo(unittest.TestCase):

    @patch("json.loads")
    @patch("subprocess.run")
    def test_get_deb_fwupd_version_success(self, mock_subporcess, mock_json):

        dict_resp = {
            "Versions": [
                {
                    "Type": "runtime",
                    "AppstreamId": "org.freedesktop.fwupd",
                    "Version": "1.9.14",
                },
                {
                    "Type": "compile",
                    "AppstreamId": "org.freedesktop.fwupd",
                    "Version": "1.7.9",
                },
            ]
        }
        json_resp = json.dumps(dict_resp)
        mock_subporcess.return_value = subprocess.CompletedProcess(
            returncode=0,
            stdout=json_resp,
            args=["fwupdmgr", "--version", "--json"],
        )
        mock_json.return_value = dict_resp

        fwupd_vers = get_firmware_info_fwupd.get_fwupdmgr_services_versions()
        mock_subporcess.assert_called_with(
            ["fwupdmgr", "--version", "--json"], capture_output=True
        )
        mock_json.assert_called_with(json_resp)
        self.assertListEqual(dict_resp["Versions"], fwupd_vers)

    @patch("json.loads")
    @patch("subprocess.run")
    def test_get_deb_fwupd_version_key_not_match(
        self, mock_subporcess, mock_json
    ):

        dict_resp = {
            "Services": [
                {
                    "Type": "runtime",
                    "AppstreamId": "org.freedesktop.fwupd",
                    "Version": "1.9.14",
                },
                {
                    "Type": "compile",
                    "AppstreamId": "org.freedesktop.fwupd",
                    "Version": "1.7.9",
                },
            ]
        }
        json_resp = json.dumps(dict_resp)
        mock_subporcess.return_value = subprocess.CompletedProcess(
            returncode=0,
            stdout=json_resp,
            args=["fwupdmgr", "--version", "--json"],
        )
        mock_json.return_value = dict_resp

        fwupd_vers = get_firmware_info_fwupd.get_fwupdmgr_services_versions()
        mock_subporcess.assert_called_with(
            ["fwupdmgr", "--version", "--json"], capture_output=True
        )
        mock_json.assert_called_with(json_resp)
        self.assertListEqual([], fwupd_vers)

    @patch("get_firmware_info_fwupd.get_fwupdmgr_services_versions")
    def test_get_deb_fwupd_runtime_version_success(self, mock_fwupd_vers):

        expected_fwupd_ver = (1, 7, 9)
        fwupd_vers_resp = [
            {
                "Type": "runtime",
                "AppstreamId": "org.freedesktop.fwupd",
                "Version": "1.7.9",
            },
            {
                "Type": "compile",
                "AppstreamId": "org.freedesktop.fwupd",
                "Version": "1.7.9",
            },
        ]

        mock_fwupd_vers.return_value = fwupd_vers_resp
        runtime_ver = get_firmware_info_fwupd.get_fwupd_runtime_version()
        self.assertEqual(expected_fwupd_ver, runtime_ver)

    @patch("get_firmware_info_fwupd.get_fwupdmgr_services_versions")
    def test_get_deb_fwupd_runtime_version_failed(self, mock_fwupd_vers):

        fwupd_vers_resp = [
            {
                "Type": "compile",
                "AppstreamId": "org.freedesktop.fwupd",
                "Version": "1.7.9",
            }
        ]

        mock_fwupd_vers.return_value = fwupd_vers_resp
        runtime_ver = get_firmware_info_fwupd.get_fwupd_runtime_version()
        self.assertEqual((), runtime_ver)

    @patch("subprocess.run")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_firmware_data_by_fwupd_snap(
        self, mock_snapd, mock_subporcess
    ):

        mock_snapd.return_value = {
            "id": "HpOj37PuyuaMUZY0NQhtwnp7oS5P8u5R",
            "title": "fwupd",
            "summary": "Firmware updates for Linux",
        }
        get_firmware_info_fwupd.get_firmware_info_fwupd()
        mock_snapd.assert_called_with("fwupd")
        mock_subporcess.assert_called_with(
            ["fwupd.fwupdmgr", "get-devices", "--json"]
        )

    @patch.dict(os.environ, {"SNAP": "checkbox-snap"})
    @patch("subprocess.run")
    @patch("get_firmware_info_fwupd.get_fwupd_runtime_version")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_firmware_data_by_fwupd1914_deb_on_checkbox_snap(
        self, mock_snapd, mock_fwupd_ver, mock_subporcess
    ):

        mock_snapd.return_value = None
        mock_fwupd_ver.return_value = (1, 9, 14)

        get_firmware_info_fwupd.get_firmware_info_fwupd()
        mock_snapd.assert_called_with("fwupd")
        self.assertEqual(os.environ.get("SNAP"), "checkbox-snap")
        mock_subporcess.assert_called_with(
            ["fwupdmgr", "get-devices", "--json"]
        )

    @patch.dict(os.environ, {"SNAP": "checkbox-snap"})
    @patch("subprocess.run")
    @patch("get_firmware_info_fwupd.get_fwupd_runtime_version")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_firmware_data_by_fwupd_deb179_on_checkbox_snap(
        self, mock_snapd, mock_fwupd_ver, mock_subporcess
    ):

        mock_snapd.return_value = False
        mock_fwupd_ver.return_value = (1, 7, 9)

        # SNAP env is available before get_firmware_info_fwupd been called
        self.assertEqual(os.environ.get("SNAP"), "checkbox-snap")
        get_firmware_info_fwupd.get_firmware_info_fwupd()
        mock_snapd.assert_called_with("fwupd")
        # SNAP env is empty after get_firmware_info_fwupd been called
        self.assertIsNone(os.environ.get("SNAP"))
        mock_subporcess.assert_called_with(
            ["fwupdmgr", "get-devices", "--json"]
        )

    @patch("subprocess.run")
    @patch("get_firmware_info_fwupd.get_fwupd_runtime_version")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_firmware_data_by_fwupd_deb_on_checkbox_deb(
        self, mock_snapd, mock_fwupd_ver, mock_subporcess
    ):

        mock_snapd.return_value = False
        mock_fwupd_ver.return_value = (1, 7, 9)

        # SNAP env is empty
        self.assertIsNone(os.environ.get("SNAP"))
        get_firmware_info_fwupd.get_firmware_info_fwupd()
        mock_snapd.assert_called_with("fwupd")
        mock_subporcess.assert_called_with(
            ["fwupdmgr", "get-devices", "--json"]
        )
