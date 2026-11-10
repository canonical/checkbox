import os
import json
import unittest
import subprocess
from unittest.mock import patch
import get_firmware_info_fwupd


class TestGetFirmwareInfo(unittest.TestCase):

    @patch("json.loads")
    @patch("subprocess.check_output")
    def test_get_deb_fwupd_version_success(self, mock_subprocess, mock_json):

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
        mock_subprocess.return_value = json_resp

        mock_json.return_value = dict_resp

        fwupd_vers = get_firmware_info_fwupd.get_fwupdmgr_services_versions()
        mock_subprocess.assert_called_with(["fwupdmgr", "--version", "--json"])
        mock_json.assert_called_with(json_resp)
        self.assertListEqual(dict_resp["Versions"], fwupd_vers)

    @patch("json.loads")
    @patch("subprocess.check_output")
    def test_get_deb_fwupd_version_key_not_match(
        self, mock_subprocess, mock_json
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
        mock_subprocess.return_value = json_resp

        mock_json.return_value = dict_resp

        fwupd_vers = get_firmware_info_fwupd.get_fwupdmgr_services_versions()
        mock_subprocess.assert_called_with(["fwupdmgr", "--version", "--json"])
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

    @patch("builtins.print")
    @patch("subprocess.check_output")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_firmware_data_by_fwupd_snap(
        self, mock_snapd, mock_subprocess, mock_print
    ):

        mock_snapd.return_value = {
            "id": "HpOj37PuyuaMUZY0NQhtwnp7oS5P8u5R",
            "title": "fwupd",
            "summary": "Firmware updates for Linux",
        }
        test_output = b'{"Devices": []}'
        mock_subprocess.return_value = test_output
        get_firmware_info_fwupd.get_firmware_info_fwupd()
        mock_snapd.assert_called_with("fwupd")
        mock_subprocess.assert_called_with(
            ["fwupd.fwupdmgr", "get-devices", "--json"], env=unittest.mock.ANY
        )
        mock_print.assert_called_once_with(test_output.decode("utf-8"))

    @patch.dict(os.environ, {"SNAP": "checkbox-snap"})
    @patch("builtins.print")
    @patch("subprocess.check_output")
    @patch("get_firmware_info_fwupd.get_fwupd_runtime_version")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_firmware_data_by_fwupd1914_deb_on_checkbox_snap(
        self, mock_snapd, mock_fwupd_ver, mock_subprocess, mock_print
    ):

        mock_snapd.return_value = None
        mock_fwupd_ver.return_value = (1, 9, 14)
        test_output = b'{"Devices": []}'
        mock_subprocess.return_value = test_output

        get_firmware_info_fwupd.get_firmware_info_fwupd()
        mock_snapd.assert_called_with("fwupd")
        self.assertEqual(os.environ.get("SNAP"), "checkbox-snap")
        mock_subprocess.assert_called_with(
            ["fwupdmgr", "get-devices", "--json"], env=unittest.mock.ANY
        )
        mock_print.assert_called_once_with(test_output.decode("utf-8"))

    @patch.dict(os.environ, {"SNAP": "checkbox-snap"})
    @patch("builtins.print")
    @patch("subprocess.check_output")
    @patch("get_firmware_info_fwupd.get_fwupd_runtime_version")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_firmware_data_by_fwupd_deb179_on_checkbox_snap(
        self, mock_snapd, mock_fwupd_ver, mock_subprocess, mock_print
    ):

        mock_snapd.return_value = False
        mock_fwupd_ver.return_value = (1, 7, 9)
        test_output = b'{"Devices": []}'
        mock_subprocess.return_value = test_output

        # SNAP env is available before get_firmware_info_fwupd been called
        self.assertEqual(os.environ.get("SNAP"), "checkbox-snap")
        get_firmware_info_fwupd.get_firmware_info_fwupd()
        mock_snapd.assert_called_with("fwupd")
        # SNAP env should still be present in os.environ (not deleted globally)
        self.assertEqual(os.environ.get("SNAP"), "checkbox-snap")
        # But subprocess should be called with env that has SNAP removed
        call_args = mock_subprocess.call_args
        self.assertEqual(
            call_args[0][0], ["fwupdmgr", "get-devices", "--json"]
        )
        self.assertNotIn("SNAP", call_args[1]["env"])
        mock_print.assert_called_once_with(test_output.decode("utf-8"))

    @patch("builtins.print")
    @patch("subprocess.check_output")
    @patch("get_firmware_info_fwupd.get_fwupd_runtime_version")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_firmware_data_by_fwupd_deb_on_checkbox_deb(
        self, mock_snapd, mock_fwupd_ver, mock_subprocess, mock_print
    ):

        mock_snapd.return_value = False
        mock_fwupd_ver.return_value = (1, 7, 9)
        test_output = b'{"Devices": []}'
        mock_subprocess.return_value = test_output

        get_firmware_info_fwupd.get_firmware_info_fwupd()
        mock_snapd.assert_called_with("fwupd")
        mock_subprocess.assert_called_with(
            ["fwupdmgr", "get-devices", "--json"], env=unittest.mock.ANY
        )
        mock_print.assert_called_once_with(test_output.decode("utf-8"))

    @patch("builtins.print")
    @patch("subprocess.check_output")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_bios_setting_fwupd_snap(
        self, mock_snapd, mock_subprocess, mock_print
    ):
        """Test get_bios_setting_fwupd with fwupd snap"""
        mock_snapd.return_value = {
            "id": "HpOj37PuyuaMUZY0NQhtwnp7oS5P8u5R",
            "title": "fwupd",
            "summary": "Firmware updates for Linux",
        }
        test_output = b'{"BiosSettings": []}'
        mock_subprocess.return_value = test_output

        get_firmware_info_fwupd.get_bios_setting_fwupd()
        mock_snapd.assert_called_with("fwupd")
        mock_subprocess.assert_called_with(
            ["fwupd.fwupdmgr", "get-bios-setting", "--json"],
            env=unittest.mock.ANY,
        )
        mock_print.assert_called_once_with(test_output.decode("utf-8"))

    @patch("builtins.print")
    @patch("subprocess.check_output")
    @patch("get_firmware_info_fwupd.get_fwupd_runtime_version")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_bios_setting_fwupd_deb(
        self, mock_snapd, mock_fwupd_ver, mock_subprocess, mock_print
    ):
        """Test get_bios_setting_fwupd with fwupd deb"""
        mock_snapd.return_value = False
        mock_fwupd_ver.return_value = (1, 9, 14)
        test_output = b'{"BiosSettings": []}'
        mock_subprocess.return_value = test_output

        get_firmware_info_fwupd.get_bios_setting_fwupd()
        mock_snapd.assert_called_with("fwupd")
        mock_subprocess.assert_called_with(
            ["fwupdmgr", "get-bios-setting", "--json"], env=unittest.mock.ANY
        )
        mock_print.assert_called_once_with(test_output.decode("utf-8"))

    @patch("subprocess.check_output")
    @patch("get_firmware_info_fwupd.get_fwupd_runtime_version")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_firmware_info_fwupd_failure(
        self, mock_snapd, mock_fwupd_ver, mock_subprocess
    ):
        """Test get_firmware_info_fwupd handles subprocess failure"""
        mock_snapd.return_value = False
        mock_fwupd_ver.return_value = (1, 9, 14)
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["fwupdmgr", "get-devices", "--json"]
        )

        with self.assertRaises(SystemExit) as context:
            get_firmware_info_fwupd.get_firmware_info_fwupd()

    @patch("subprocess.check_output")
    @patch("get_firmware_info_fwupd.get_fwupd_runtime_version")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_bios_setting_fwupd_failure(
        self, mock_snapd, mock_fwupd_ver, mock_subprocess
    ):
        """Test get_bios_setting_fwupd handles subprocess failure"""
        mock_snapd.return_value = False
        mock_fwupd_ver.return_value = (1, 9, 14)
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=2, cmd=["fwupdmgr", "get-bios-setting", "--json"]
        )

        with self.assertRaises(SystemExit) as context:
            get_firmware_info_fwupd.get_bios_setting_fwupd()

    def test_parse_args_default(self):
        """Test parse_args with default arguments"""
        args = get_firmware_info_fwupd.parse_args([])
        self.assertEqual(args.command, "get-devices")

    def test_parse_args_get_devices(self):
        """Test parse_args with get-devices command"""
        args = get_firmware_info_fwupd.parse_args(["-c", "get-devices"])
        self.assertEqual(args.command, "get-devices")

    def test_parse_args_get_bios_setting(self):
        """Test parse_args with get-bios-setting command"""
        args = get_firmware_info_fwupd.parse_args(
            ["--command", "get-bios-setting"]
        )
        self.assertEqual(args.command, "get-bios-setting")

    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_choose_command_snap(self, mock_snapd):
        """Test choose_command returns fwupd.fwupdmgr when fwupd snap exists"""
        mock_snapd.return_value = {
            "id": "HpOj37PuyuaMUZY0NQhtwnp7oS5P8u5R",
            "title": "fwupd",
        }
        cmd = get_firmware_info_fwupd.choose_command()
        self.assertEqual(cmd, "fwupd.fwupdmgr")

    @patch("get_firmware_info_fwupd.get_fwupd_runtime_version")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_choose_command_deb(self, mock_snapd, mock_fwupd_ver):
        """Test choose_command returns fwupdmgr when fwupd deb is used"""
        mock_snapd.return_value = None
        cmd = get_firmware_info_fwupd.choose_command()
        self.assertEqual(cmd, "fwupdmgr")

    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_environment_snap(self, mock_snapd):
        """Test get_environment returns env with SNAP when using snap"""
        mock_snapd.return_value = {"id": "test"}
        with patch.dict(os.environ, {"SNAP": "checkbox-snap"}):
            env = get_firmware_info_fwupd.get_environment()
            self.assertEqual(env.get("SNAP"), "checkbox-snap")

    @patch.dict(os.environ, {"SNAP": "checkbox-snap"})
    @patch("get_firmware_info_fwupd.get_fwupd_runtime_version")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_environment_deb_old_version(self, mock_snapd, mock_fwupd_ver):
        """Test get_environment removes SNAP for old fwupd deb"""
        mock_snapd.return_value = None
        mock_fwupd_ver.return_value = (1, 7, 9)
        env = get_firmware_info_fwupd.get_environment()
        self.assertNotIn("SNAP", env)

    @patch.dict(os.environ, {"SNAP": "checkbox-snap"})
    @patch("get_firmware_info_fwupd.get_fwupd_runtime_version")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_environment_deb_new_version(self, mock_snapd, mock_fwupd_ver):
        """Test get_environment keeps SNAP for new fwupd deb"""
        mock_snapd.return_value = None
        mock_fwupd_ver.return_value = (1, 9, 14)
        env = get_firmware_info_fwupd.get_environment()
        self.assertEqual(env.get("SNAP"), "checkbox-snap")

    @patch("get_firmware_info_fwupd.get_fwupd_runtime_version")
    @patch("checkbox_support.snap_utils.snapd.Snapd.list")
    def test_get_environment_deb_no_snap_env(self, mock_snapd, mock_fwupd_ver):
        """Test get_environment when no SNAP env variable exists"""
        mock_snapd.return_value = None
        mock_fwupd_ver.return_value = (1, 7, 9)
        env = get_firmware_info_fwupd.get_environment()
        self.assertNotIn("SNAP", env)
