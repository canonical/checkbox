import unittest
import sys
from unittest.mock import patch, call, Mock, MagicMock
from io import StringIO
from contextlib import redirect_stdout

# Mock the dbus module due to is is not available on CI testing environment
sys.modules["dbus"] = MagicMock()

import wwan_tests


class TestMMDbus(unittest.TestCase):

    @patch("wwan_tests.MMDbus.__init__", Mock(return_value=None))
    def test_get_firmware_revision(self):
        fw_revision_pattern = "81600.0000.00.29.21.24_GC\r\nD24"
        mock_get = Mock(return_value=fw_revision_pattern)
        obj_mmdbus = wwan_tests.MMDbus()
        obj_mmdbus._modem_props_iface = Mock(
            return_value=Mock(Get=mock_get)
        )

        resp = obj_mmdbus.get_firmware_revision(1)

        self.assertEqual(obj_mmdbus.__init__.call_count, 1)
        obj_mmdbus._modem_props_iface.assert_called_with(1)
        mock_get.assert_called_with(
            wwan_tests.DBUS_MM1_IF_MODEM, "Revision")
        self.assertEqual(
            resp, "81600.0000.00.29.21.24_GC D24"
        )

    @patch("wwan_tests.MMDbus.__init__", Mock(return_value=None))
    def test_get_hardware_revision(self):
        hw_revision_pattern = "V1.0.6"
        mock_get = Mock(return_value=hw_revision_pattern)
        obj_mmdbus = wwan_tests.MMDbus()
        obj_mmdbus._modem_props_iface = Mock(
            return_value=Mock(Get=mock_get)
        )

        resp = obj_mmdbus.get_hardware_revision(1)

        self.assertEqual(obj_mmdbus.__init__.call_count, 1)
        obj_mmdbus._modem_props_iface.assert_called_with(1)
        mock_get.assert_called_with(
            wwan_tests.DBUS_MM1_IF_MODEM, "HardwareRevision")
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
            "modem", 1, "firmware revision")
        self.assertEqual(resp, fw_revision_pattern)

    @patch("wwan_tests.MMCLI.__init__", Mock(return_value=None))
    @patch("wwan_tests._value_from_table")
    def test_get_hardware_revision(self, mock_value_from_table):
        hw_revision_pattern = "81600.0000.00.29.21.24_GC"
        obj_mmcli = wwan_tests.MMCLI()
        mock_value_from_table.return_value = hw_revision_pattern

        resp = obj_mmcli.get_hardware_revision(1)

        self.assertEqual(obj_mmcli.__init__.call_count, 1)
        mock_value_from_table.assert_called_with(
            "modem", 1, "h/w revision")
        self.assertEqual(resp, hw_revision_pattern)


class TestResources(unittest.TestCase):

    @patch("wwan_tests.MMCLI.__init__")
    @patch("wwan_tests.MMCLI.get_hardware_revision")
    @patch("wwan_tests.MMCLI.get_firmware_revision")
    @patch("wwan_tests.MMCLI.get_model_name")
    @patch("wwan_tests.MMCLI.get_manufacturer")
    @patch("wwan_tests.MMCLI.get_equipment_id")
    @patch("wwan_tests.MMCLI.get_modem_ids")
    def test_invoked_with_mmcli(
            self, mock_get_modem_ids, mock_get_equipment_id,
            mock_get_manufacturer, mock_get_model_name,
            mock_get_firmware_revision, mock_get_hardware_revision,
            mock_mmcli_init):

        values = {
            "mm_id": [1, 2],
            "hw_id": ["d43f035387373e", None],
            "manufacturer": ["generic", "sierra"],
            "model": ["MBIM [14C3:4D75]", "MBIM [14C3:9999]"],
            "firmware_revision": [
                "81600.0000.00.29.21.24_GC",
                "81600.0000.00.29.21.25_GC"],
            "hardware_revision": ["V1.0.6", "V1.0.7"]
        }

        mock_mmcli_init.return_value = None
        mock_get_modem_ids.return_value = values["mm_id"]
        mock_get_equipment_id.side_effect = values["hw_id"]
        mock_get_manufacturer.side_effect = values["manufacturer"]
        mock_get_model_name.side_effect = values["model"]
        mock_get_firmware_revision.side_effect = values["firmware_revision"]
        mock_get_hardware_revision.side_effect = values["hardware_revision"]

        sys.argv = ["wwan_tests.py", "resources", "--use-cli"]
        with redirect_stdout(StringIO()) as stdout:
            wwan_tests.Resources().invoked()

        mock_mmcli_init.assert_called_with()
        mock_get_modem_ids.assert_called_with()
        calls = [call(1), call(2)]

        mock_get_equipment_id.assert_has_calls(calls)
        mock_get_manufacturer.assert_has_calls(calls)
        mock_get_model_name.assert_has_calls(calls)
        mock_get_firmware_revision.assert_has_calls(calls)
        mock_get_hardware_revision.assert_has_calls(calls)

        expected_info = []
        for i in range(2):
            expected_info.append("\n".join(
                ["{}: {}".format(k, v[i]) for k, v in values.items()]
            ))
        expected_info = "{}\n\n".format("\n\n".join(expected_info))

        self.assertEqual(expected_info, stdout.getvalue())

    @patch("wwan_tests.MMDbus.__init__")
    @patch("wwan_tests.MMDbus.get_hardware_revision")
    @patch("wwan_tests.MMDbus.get_firmware_revision")
    @patch("wwan_tests.MMDbus.get_model_name")
    @patch("wwan_tests.MMDbus.get_manufacturer")
    @patch("wwan_tests.MMDbus.get_equipment_id")
    @patch("wwan_tests.MMDbus.get_modem_ids")
    def test_invoked_with_mmdbus(
            self, mock_get_modem_ids, mock_get_equipment_id,
            mock_get_manufacturer, mock_get_model_name,
            mock_get_firmware_revision, mock_get_hardware_revision,
            mock_mmdbus_init):

        values = {
            "mm_id": [1, 2],
            "hw_id": ["d43f035387373e", "335464"],
            "manufacturer": ["generic", "sierra"],
            "model": ["MBIM [14C3:4D75]", "MBIM [14C3:9999]"],
            "firmware_revision": [
                "81600.0000.00.29.21.24_GC",
                "81600.0000.00.29.21.25_GC"],
            "hardware_revision": ["V1.0.6", "V1.0.7"]
        }

        mock_mmdbus_init.return_value = None
        mock_get_modem_ids.return_value = values["mm_id"]
        mock_get_equipment_id.side_effect = values["hw_id"]
        mock_get_manufacturer.side_effect = values["manufacturer"]
        mock_get_model_name.side_effect = values["model"]
        mock_get_firmware_revision.side_effect = values["firmware_revision"]
        mock_get_hardware_revision.side_effect = values["hardware_revision"]

        sys.argv = ["wwan_tests.py", "resources"]
        with redirect_stdout(StringIO()) as stdout:
            wwan_tests.Resources().invoked()

        mock_mmdbus_init.assert_called_with()
        mock_get_modem_ids.assert_called_with()
        calls = [call(1), call(2)]

        mock_get_equipment_id.assert_has_calls(calls)
        mock_get_manufacturer.assert_has_calls(calls)
        mock_get_model_name.assert_has_calls(calls)
        mock_get_firmware_revision.assert_has_calls(calls)
        mock_get_hardware_revision.assert_has_calls(calls)

        expected_info = []
        for i in range(2):
            expected_info.append("\n".join(
                ["{}: {}".format(k, v[i]) for k, v in values.items()]
            ))
        expected_info = "{}\n\n".format("\n\n".join(expected_info))
        self.assertEqual(expected_info, stdout.getvalue())
