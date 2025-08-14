import unittest
import sys
from unittest.mock import patch, Mock, MagicMock
from io import StringIO
from contextlib import redirect_stdout
import argparse
import subprocess

# Mock the dbus module due to is is not available on CI testing environment
sys.modules["dbus"] = MagicMock()

import wwan_tests


class TestMMDbus(unittest.TestCase):

    @patch("wwan_tests.MMDbus.__init__", Mock(return_value=None))
    def test_get_firmware_revision(self):
        fw_revision_pattern = "81600.0000.00.29.21.24_GC\r\nD24"
        mock_get = Mock(return_value=fw_revision_pattern)
        obj_mmdbus = wwan_tests.MMDbus()
        obj_mmdbus._modem_props_iface = Mock(return_value=Mock(Get=mock_get))

        resp = obj_mmdbus.get_firmware_revision(1)

        self.assertEqual(obj_mmdbus.__init__.call_count, 1)
        obj_mmdbus._modem_props_iface.assert_called_with(1)
        mock_get.assert_called_with(wwan_tests.DBUS_MM1_IF_MODEM, "Revision")
        self.assertEqual(resp, "81600.0000.00.29.21.24_GC D24")

    @patch("wwan_tests.MMDbus.__init__", Mock(return_value=None))
    def test_get_hardware_revision(self):
        hw_revision_pattern = "V1.0.6"
        mock_get = Mock(return_value=hw_revision_pattern)
        obj_mmdbus = wwan_tests.MMDbus()
        obj_mmdbus._modem_props_iface = Mock(return_value=Mock(Get=mock_get))

        resp = obj_mmdbus.get_hardware_revision(1)

        self.assertEqual(obj_mmdbus.__init__.call_count, 1)
        obj_mmdbus._modem_props_iface.assert_called_with(1)
        mock_get.assert_called_with(
            wwan_tests.DBUS_MM1_IF_MODEM, "HardwareRevision"
        )
        self.assertEqual(resp, hw_revision_pattern)


class TestMMCli(unittest.TestCase):

    @patch("wwan_tests.MMCLI.__init__", Mock(return_value=None))
    @patch("wwan_tests._value_from_table")
    def test_get_firmware_revision(self, mock_value_from_table):
        fw_revision_pattern = "81600.0000.00.29.21.24_GC"
        obj_mmcli = wwan_tests.MMCLI()
        mock_value_from_table.return_value = fw_revision_pattern

        resp = obj_mmcli.get_firmware_revision(1)

        self.assertEqual(obj_mmcli.__init__.call_count, 1)
        mock_value_from_table.assert_called_with(
            "modem", 1, "firmware revision"
        )
        self.assertEqual(resp, fw_revision_pattern)

    @patch("wwan_tests.MMCLI.__init__", Mock(return_value=None))
    @patch("wwan_tests._value_from_table")
    def test_get_hardware_revision(self, mock_value_from_table):
        hw_revision_pattern = "81600.0000.00.29.21.24_GC"
        obj_mmcli = wwan_tests.MMCLI()
        mock_value_from_table.return_value = hw_revision_pattern

        resp = obj_mmcli.get_hardware_revision(1)

        self.assertEqual(obj_mmcli.__init__.call_count, 1)
        mock_value_from_table.assert_called_with("modem", 1, "h/w revision")
        self.assertEqual(resp, hw_revision_pattern)


class TestResources(unittest.TestCase):

    @patch("wwan_tests.MMCLI")
    def test_invoked_with_mmcli(self, mock_mmcli):
        mmcli_instance = Mock()
        mmcli_instance.get_modem_ids.return_value = ["test"]
        mock_mmcli.return_value = mmcli_instance

        sys.argv = ["wwan_tests.py", "resources", "--use-cli"]

        with redirect_stdout(StringIO()):
            wwan_tests.Resources().invoked()
            self.assertTrue(mock_mmcli.called)
            self.assertTrue(mmcli_instance.get_equipment_id.called)
            self.assertTrue(mmcli_instance.get_manufacturer.called)
            self.assertTrue(mmcli_instance.get_model_name.called)
            self.assertTrue(mmcli_instance.get_firmware_revision.called)
            self.assertTrue(mmcli_instance.get_hardware_revision.called)

    @patch("wwan_tests.MMDbus")
    def test_invoked_with_mmdbus(self, mock_mmdbus):
        mmdbus_instance = Mock()
        mmdbus_instance.get_modem_ids.return_value = ["test"]
        mock_mmdbus.return_value = mmdbus_instance

        sys.argv = ["wwan_tests.py", "resources"]

        with redirect_stdout(StringIO()):
            wwan_tests.Resources().invoked()
            self.assertTrue(mock_mmdbus.called)
            self.assertTrue(mmdbus_instance.get_equipment_id.called)
            self.assertTrue(mmdbus_instance.get_manufacturer.called)
            self.assertTrue(mmdbus_instance.get_model_name.called)
            self.assertTrue(mmdbus_instance.get_firmware_revision.called)
            self.assertTrue(mmdbus_instance.get_hardware_revision.called)


class TestCommonFunctions(unittest.TestCase):

    @patch("subprocess.run")
    def test_wwan_radio_status(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"disabled", stderr=b""
        )
        with redirect_stdout(StringIO()):
            status = wwan_tests._wwan_radio_status()
        self.assertEqual(status, "disabled")

    @patch("subprocess.run")
    def test_wwan_radio_status_exception(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
        with redirect_stdout(StringIO()):
            with self.assertRaises(subprocess.CalledProcessError):
                wwan_tests._wwan_radio_status()


class TestWWANTestCtx(unittest.TestCase):

    @patch("wwan_tests._wwan_radio_off")
    @patch("wwan_tests._wwan_radio_on")
    @patch("wwan_tests._wwan_radio_status")
    @patch("wwan_tests.MMDbus")
    def test_wwan_ctx_init_with_dbus(
        self, mock_mmdbus, mock_r_status, mock_r_on, mock_r_off
    ):
        mmdbus_instance = Mock()
        mmdbus_instance.equipment_id_to_mm_id.return_value = "0"
        mock_mmdbus.return_value = mmdbus_instance
        mock_r_status.return_value = "enabled"

        with wwan_tests.WWANTestCtx("test_id", False):
            pass

        mmdbus_instance.equipment_id_to_mm_id.assert_called_with("test_id")
        self.assertTrue(mock_mmdbus.called)
        self.assertFalse(mock_r_on.called)
        self.assertFalse(mock_r_off.called)
        self.assertTrue(mock_r_status.called)

    @patch("wwan_tests._wwan_radio_off")
    @patch("wwan_tests._wwan_radio_on")
    @patch("wwan_tests._wwan_radio_status")
    @patch("wwan_tests.MMCLI")
    def test_wwan_ctx_init_with_mmcli(
        self, mock_mmcli, mock_r_status, mock_r_on, mock_r_off
    ):
        mmcli_instance = Mock()
        mmcli_instance.equipment_id_to_mm_id.return_value = "0"
        mock_mmcli.return_value = mmcli_instance
        mock_r_status.return_value = "disabled"

        with wwan_tests.WWANTestCtx("test_id", True, True):
            pass

        mmcli_instance.equipment_id_to_mm_id.assert_called_with("test_id")
        self.assertTrue(mock_mmcli.called)
        self.assertTrue(mock_r_on.called)
        self.assertTrue(mock_r_off.called)
        self.assertTrue(mock_r_status.called)


class TestThreeGppScanTest(unittest.TestCase):

    def test_register_argument(self):

        sys.argv = ["wwan_tests.py", "3gpp-scan", "2", "--timeout", "600"]
        obj_3gppscan = wwan_tests.ThreeGppScanTest()
        ret_args = obj_3gppscan.register_argument()
        self.assertEqual(ret_args.hw_id, "2")
        self.assertEqual(ret_args.timeout, 600)

    @patch("subprocess.run")
    @patch("wwan_tests.WWANTestCtx")
    @patch("wwan_tests.ThreeGppScanTest.register_argument")
    def test_invoked_successfully(self, mock_arg, mock_mmctx, mock_run):
        mock_arg.return_value = argparse.Namespace(hw_id="2", timeout=200)
        mmcli_instance = Mock()
        mmcli_instance.modem_idx = "0"
        mock_mmctx.return_value.__enter__.return_value = mmcli_instance
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"output", stderr=b""
        )

        with redirect_stdout(StringIO()):
            with self.assertRaises(SystemExit) as context:
                obj_3gppscan = wwan_tests.ThreeGppScanTest()
                obj_3gppscan.invoked()

        self.assertEqual(context.exception.code, 0)
        mock_mmctx.assert_called_with("2", True, True)
        mock_run.assert_called_with(
            ["mmcli", "-m", "0", "--3gpp-scan", "--timeout", "200"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    @patch("subprocess.run")
    @patch("wwan_tests.WWANTestCtx")
    @patch("wwan_tests.ThreeGppScanTest.register_argument")
    def test_invoked_failed_exit_code(self, mock_arg, mock_mmctx, mock_run):
        mock_arg.return_value = argparse.Namespace(hw_id="2", timeout=200)
        mmcli_instance = Mock()
        mmcli_instance.modem_idx = "0"
        mock_mmctx.return_value.__enter__.return_value = mmcli_instance
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=b"output", stderr=b""
        )

        with redirect_stdout(StringIO()):
            with self.assertRaises(SystemExit) as context:
                obj_3gppscan = wwan_tests.ThreeGppScanTest()
                obj_3gppscan.invoked()

        self.assertEqual(context.exception.code, 1)
        mock_mmctx.assert_called_with("2", True, True)
        mock_run.assert_called_with(
            ["mmcli", "-m", "0", "--3gpp-scan", "--timeout", "200"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    @patch("subprocess.run")
    @patch("wwan_tests.WWANTestCtx")
    @patch("wwan_tests.ThreeGppScanTest.register_argument")
    def test_invoked_call_error(self, mock_arg, mock_mmctx, mock_run):
        mock_arg.return_value = argparse.Namespace(hw_id="2", timeout=200)
        mmcli_instance = Mock()
        mmcli_instance.modem_idx = "0"
        mock_mmctx.return_value.__enter__.return_value = mmcli_instance
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=b"output",
            stderr=b"",
        )

        with redirect_stdout(StringIO()):
            with self.assertRaises(SystemExit) as context:
                obj_3gppscan = wwan_tests.ThreeGppScanTest()
                obj_3gppscan.invoked()

        self.assertEqual(context.exception.code, 1)
        mock_mmctx.assert_called_with("2", True, True)
        mock_run.assert_called_with(
            ["mmcli", "-m", "0", "--3gpp-scan", "--timeout", "200"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )


class TestThreeGppConnectionTest(unittest.TestCase):

    def test_register_argument(self):

        sys.argv = [
            "wwan_tests.py",
            "3gpp-connection",
            "hw_id",
            "wwan_net_if",
            "apn",
            "30",
        ]
        obj_3gppscan = wwan_tests.ThreeGppConnection()
        ret_args = obj_3gppscan.register_argument()
        self.assertEqual(ret_args.hw_id, "hw_id")
        self.assertEqual(ret_args.wwan_net_if, "wwan_net_if")
        self.assertEqual(ret_args.apn, "apn")
        self.assertEqual(ret_args.wwan_setup_time, 30)

    @patch("wwan_tests._ping_test")
    @patch("wwan_tests._destroy_3gpp_connection")
    @patch("wwan_tests._create_3gpp_connection")
    @patch("wwan_tests.WWANTestCtx")
    @patch("wwan_tests.ThreeGppConnection.register_argument")
    def test_invoked_successfully(
        self, mock_arg, mock_mmctx, mock_create_conn, mock_rm_conn, mock_ping
    ):
        mock_arg.return_value = argparse.Namespace(
            hw_id="2", wwan_net_if="wwan0", apn="internet", wwan_setup_time=0.1
        )
        mock_get_primary_port = Mock()
        mmcli_instance = Mock()
        mmcli_instance.modem_idx = "0"
        mmcli_instance.mm_obj = Mock(get_primary_port=mock_get_primary_port)
        mock_mmctx.return_value.__enter__.return_value = mmcli_instance
        mock_ping.return_value = 0

        with redirect_stdout(StringIO()):
            with self.assertRaises(SystemExit) as context:
                obj_3gppscan = wwan_tests.ThreeGppConnection()
                obj_3gppscan.invoked()

        mock_mmctx.assert_called_with("2", True, True)
        self.assertEqual(mock_arg.call_count, 1)
        self.assertEqual(mock_get_primary_port.call_count, 1)
        self.assertEqual(mock_ping.call_count, 1)
        self.assertEqual(mock_create_conn.call_count, 1)
        self.assertEqual(mock_rm_conn.call_count, 1)
        self.assertEqual(context.exception.code, 0)

    @patch("wwan_tests._ping_test")
    @patch("wwan_tests._destroy_3gpp_connection")
    @patch("wwan_tests._create_3gpp_connection")
    @patch("wwan_tests.WWANTestCtx")
    @patch("wwan_tests.ThreeGppConnection.register_argument")
    def test_invoked_failed_exit_code(
        self, mock_arg, mock_mmctx, mock_create_conn, mock_rm_conn, mock_ping
    ):
        mock_arg.return_value = argparse.Namespace(
            hw_id="2", wwan_net_if="wwan0", apn="internet", wwan_setup_time=0.1
        )
        mock_get_primary_port = Mock()
        mmcli_instance = Mock()
        mmcli_instance.modem_idx = "0"
        mmcli_instance.mm_obj = Mock(get_primary_port=mock_get_primary_port)
        mock_mmctx.return_value.__enter__.return_value = mmcli_instance
        mock_ping.return_value = 1

        with redirect_stdout(StringIO()):
            with self.assertRaises(SystemExit) as context:
                obj_3gppscan = wwan_tests.ThreeGppConnection()
                obj_3gppscan.invoked()

        mock_mmctx.assert_called_with("2", True, True)
        self.assertEqual(mock_arg.call_count, 1)
        self.assertEqual(mock_ping.call_count, 1)
        self.assertEqual(mock_create_conn.call_count, 1)
        self.assertEqual(mock_rm_conn.call_count, 1)
        self.assertEqual(context.exception.code, 1)
