# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
checkbox_support.tests.test_vendor_beacontools_scanner
================================================

Tests for checkbox_support.vendor.beacontools.scanner module
"""
import logging
import time
import unittest
from unittest.mock import patch, Mock, call

from checkbox_support.vendor.beacontools.scanner import HCIVersion
from checkbox_support.vendor.beacontools.scanner import Monitor
from checkbox_support.vendor.beacontools.device_filters import (
    BtAddrFilter,
    DeviceFilter,
)
from checkbox_support.vendor.beacontools.const import MetaEventReportTypeEnum


class HCIVersionTests(unittest.TestCase):
    """
    Tests for HCIVersion class
    """

    def test_included(self):
        self.assertEqual(HCIVersion(13), HCIVersion.BT_CORE_SPEC_5_4)

    def test_included_bt_6(self):
        self.assertEqual(HCIVersion(14), HCIVersion.BT_CORE_SPEC_6_0)
        self.assertEqual(HCIVersion(15), HCIVersion.BT_CORE_SPEC_6_1)

    def test_non_included(self):
        with self.assertRaises(ValueError):
            HCIVersion(-1)


class MonitorTests(unittest.TestCase):

    @patch("builtins.bytes")
    @patch("checkbox_support.vendor.beacontools.scanner.KeywordTree")
    @patch("checkbox_support.vendor.beacontools.scanner.get_mode")
    @patch("checkbox_support.vendor.beacontools.scanner.import_module")
    def test_initialize(
        self, mock_import, mock_get_mode, mock_keyword, mock_bytes
    ):
        mock_import.return_value = "import"
        mock_get_mode.return_value = 1000

        mock_instance = Mock()
        mock_instance.add.return_value = None
        mock_instance.finalize.return_value = None
        mock_keyword.return_value = mock_instance
        mock_bytes.return_value = b"bytes"

        mon = Monitor(
            "callback",
            "1",
            "dev_filter",
            "pkt_filter",
            "scan_params",
        )
        self.assertEqual(mon.backend, "import")
        self.assertEqual(mon.daemon, False)
        self.assertEqual(mon.keep_going, True)
        self.assertEqual(mon.callback, "callback")
        self.assertEqual(mon.bt_device_id, "1")
        self.assertEqual(mon.device_filter, "dev_filter")
        self.assertEqual(mon.mode, 1000)
        self.assertEqual(mon.packet_filter, "pkt_filter")
        self.assertEqual(mon.socket, None)
        self.assertEqual(mon.eddystone_mappings, [])
        self.assertEqual(mon.scan_parameters, "scan_params")
        self.assertEqual(mon.hci_version, HCIVersion.BT_CORE_SPEC_1_0)
        self.assertEqual(mon.kwtree, mock_instance)
        mock_instance.add.assert_called_with(b"bytesr\x04")
        mock_instance.finalize.assert_called_once_with()

    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_get_le_adv_report_length(self, mock_mon_init):
        mock_mon_init.return_value = None
        mon = Monitor()

        mock_backend = Mock()
        mock_backend.send_req.return_value = b"\x00\x00\x08\x00"
        mock_socket = Mock()

        mon.socket = mock_socket
        mon.backend = mock_backend

        self.assertEqual(mon.get_le_adv_report_length(), 2048)
        mock_backend.send_req.assert_called_with(
            mock_socket, 8, 58, 14, 1000, b"", 0
        )

    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_get_le_adv_report_length_failed(self, mock_mon_init):
        mock_mon_init.return_value = None
        mon = Monitor()

        mock_backend = Mock()
        mock_backend.send_req.return_value = b"\x01\x00\x08\x00"
        mock_socket = Mock()

        mon.socket = mock_socket
        mon.backend = mock_backend

        self.assertEqual(mon.get_le_adv_report_length(), 255)

    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_is_le_extended_advertising_support_true(self, mock_mon_init):
        mock_mon_init.return_value = None
        mon = Monitor()

        mock_backend = Mock()
        mock_backend.send_req.return_value = (
            b"\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00"
        )
        mock_socket = Mock()

        mon.socket = mock_socket
        mon.backend = mock_backend

        self.assertEqual(mon.is_le_extended_advertising_support(), True)

    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_is_le_extended_advertising_support_command_failed(
        self, mock_mon_init
    ):
        mock_mon_init.return_value = None
        mon = Monitor()

        mock_backend = Mock()
        mock_backend.send_req.return_value = (
            b"\x01\x00\x08\x00\x00\x00\x00\x00\x00\x00"
        )
        mock_socket = Mock()

        mon.socket = mock_socket
        mon.backend = mock_backend

        self.assertEqual(mon.is_le_extended_advertising_support(), False)

    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_set_scan_parameters_le_extended(self, mock_mon_init):
        mock_mon_init.return_value = None
        mon = Monitor()

        mock_send_cmd = Mock()
        mock_socket = Mock()

        mon.socket = mock_socket
        mon.backend = Mock(send_cmd=mock_send_cmd)
        mon.support_ext_advertising = True

        mon.set_scan_parameters()
        mock_send_cmd.assert_called_with(
            mock_socket, 8, 65, b"\x01\x00\x01\x01\x10\x00\x10\x00"
        )

    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_set_scan_parameters_le_legacy(self, mock_mon_init):
        mock_mon_init.return_value = None
        mon = Monitor()

        mock_send_cmd = Mock()
        mock_socket = Mock()

        mon.socket = mock_socket
        mon.backend = Mock(send_cmd=mock_send_cmd)
        mon.support_ext_advertising = False

        mon.set_scan_parameters()
        mock_send_cmd.assert_called_with(
            mock_socket, 8, 11, b"\x01\x10\x00\x10\x00\x01\x00"
        )

    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_toggle_scan_enable_le_extended(self, mock_mon_init):
        mock_mon_init.return_value = None
        mon = Monitor()

        mock_send_cmd = Mock()
        mock_socket = Mock()

        mon.socket = mock_socket
        mon.backend = Mock(send_cmd=mock_send_cmd)
        mon.support_ext_advertising = True

        mon.toggle_scan(True)
        mock_send_cmd.assert_called_with(
            mock_socket, 8, 66, b"\x01\x00\x00\x00\x00\x00"
        )

    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_toggle_scan_enable_le_legacy(self, mock_mon_init):
        mock_mon_init.return_value = None
        mon = Monitor()

        mock_send_cmd = Mock()
        mock_socket = Mock()

        mon.socket = mock_socket
        mon.backend = Mock(send_cmd=mock_send_cmd)
        mon.support_ext_advertising = False

        mon.toggle_scan(True)
        mock_send_cmd.assert_called_with(mock_socket, 8, 12, b"\x01\x00")

    @patch("checkbox_support.vendor.beacontools.scanner._LOGGER")
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_dump_reports(self, mock_mon_init, mock_logger):
        mock_mon_init.return_value = None
        mon = Monitor()

        report = Mock()
        report.evt_type = "le_ext"
        report.bdaddr = b"\x61\x62\x63\x64\x65\x66"
        report.rssi = "03"
        report.data = "data"

        mon.dump_reports([report])
        mock_logger.debug.assert_called_with(
            "<evt_type: %s> <mac: %s> <rssi: %s> <data: %s>",
            "le_ext",
            "66:65:64:63:62:61",
            48,
            "data",
        )

    @patch("checkbox_support.vendor.beacontools.scanner.parse_packet")
    @patch(
        "checkbox_support.vendor.beacontools.scanner."
        "Monitor.process_report_data"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.dump_reports")
    @patch(
        "checkbox_support.vendor.beacontools.structs"
        ".common.HciAdReportEvent.parse"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_process_packet_pass(
        self,
        mock_mon_init,
        mock_event_parse,
        mock_dump_reports,
        mock_process_report_data,
        mock_report_parse,
    ):
        mock_mon_init.return_value = None
        mock_report = [
            Mock(data=b"data", bdaddr=b"\x61\x62\x63\x64\x65\x66", rssi=100)
        ]
        mock_event_data = Mock(
            subevent=0x0D,
            reports=mock_report,
        )

        mock_event_parse.return_value = mock_event_data
        mock_report_parse.return_value = "report1"

        mon = Monitor()
        mon.support_ext_advertising = True

        src_packet = b"packet"
        mon.process_packet(src_packet)

        mock_event_parse.assert_called_with(src_packet)
        mock_dump_reports.assert_called_with(mock_report)
        mock_report_parse.assert_called_with(mock_report[0].data)
        mock_process_report_data.assert_called_with(
            "report1",
            "66:65:64:63:62:61",
            100,
            MetaEventReportTypeEnum.LE_EXT_ADVERTISING_REPORT,
        )

    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.dump_reports")
    @patch(
        "checkbox_support.vendor.beacontools.structs"
        ".common.HciAdReportEvent.parse"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_process_packet_unexpected_event(
        self,
        mock_mon_init,
        mock_event_parse,
        mock_dump_reports,
    ):
        mock_mon_init.return_value = None
        mock_event_data = Mock(subevent=0x02, reports=[])

        mock_event_parse.return_value = mock_event_data

        mon = Monitor()
        mon.support_ext_advertising = False

        src_packet = b"packet"
        self.assertEqual(mon.process_packet(src_packet), None)

        mock_event_parse.assert_called_with(src_packet)
        mock_dump_reports.assert_called_with(mock_event_data.reports)

    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.get_properties"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.save_bt_addr")
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_process_report_no_filter_ok(
        self, mock_init, mock_save_addr, mock_properties
    ):
        mock_init.return_value = None
        mock_callback = Mock()
        mock_packet = "packets"
        mock_properties.return_value = "properties"

        mon = Monitor()
        mon.hci_version = 8
        mon.callback = mock_callback
        mon.device_filter = None
        mon.packet_filter = None

        mon.process_report_data(mock_packet, "addr", "rssi", "type")
        mock_save_addr.assert_called_with(mock_packet, "addr")
        mock_properties.assert_called_with(mock_packet, "addr")
        mock_callback.assert_called_with(
            "type",
            "addr",
            "rssi",
            mock_packet,
            "properties",
        )

    @patch("checkbox_support.vendor.beacontools.scanner.is_one_of")
    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.get_properties"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.save_bt_addr")
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_process_report_packet_filter_ok(
        self,
        mock_init,
        mock_addr,
        mock_properties,
        mock_func_one_of,
    ):
        mock_init.return_value = None
        mock_callback = Mock()
        mock_packet = "packets"
        mock_properties.return_value = "properties"
        mock_func_one_of.return_value = True

        mon = Monitor()
        mon.hci_version = 8
        mon.callback = mock_callback
        mon.device_filter = None
        mon.packet_filter = "pkt_filter"

        mon.process_report_data(mock_packet, "addr", "rssi", "type")

        mock_addr.assert_called_with(mock_packet, "addr")
        mock_properties.assert_called_with(mock_packet, "addr")
        mock_func_one_of.assert_called_with(mock_packet, "pkt_filter")
        mock_callback.assert_called_with(
            "type",
            "addr",
            "rssi",
            mock_packet,
            "properties",
        )

    @patch("checkbox_support.vendor.beacontools.scanner.is_one_of")
    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.get_properties"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.save_bt_addr")
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_process_report_device_filter_not_match(
        self,
        mock_init,
        mock_addr,
        mock_properties,
        mock_is_one_of,
    ):
        mock_init.return_value = None
        mock_callback = Mock()
        mock_packet = "packets"
        mock_properties.return_value = "properties"
        mock_is_one_of.return_value = False

        mon = Monitor()
        mon.hci_version = 8
        mon.callback = mock_callback
        mon.device_filter = "dev_filter"
        mon.packet_filter = "pkt_filter"

        mon.process_report_data("packets", "addr", "rssi", "type")
        mock_addr.assert_called_with(mock_packet, "addr")
        mock_properties.assert_called_with(mock_packet, "addr")
        mock_is_one_of.assert_called_with(mock_packet, "pkt_filter")
        mock_callback.assert_not_called()

    @patch.object(BtAddrFilter, "matches")
    @patch("checkbox_support.vendor.beacontools.scanner.is_one_of")
    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.get_properties"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.save_bt_addr")
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_process_report_filters_addr_ok(
        self,
        mock_init,
        mock_addr,
        mock_properties,
        mock_is_one_of,
        mock_addr_filter,
    ):
        mock_init.return_value = None
        mock_callback = Mock()
        mock_packet = "packets"
        mock_properties.return_value = "properties"
        mock_is_one_of.return_value = True
        mock_addr_filter.return_value = True

        mon = Monitor()
        mon.hci_version = 8
        mon.callback = mock_callback
        mon.device_filter = [BtAddrFilter("00:11:22:33:44:55")]
        mon.packet_filter = "pkt_filter"

        mon.process_report_data("packets", "addr", "rssi", "type")
        mock_addr.assert_called_with(mock_packet, "addr")
        mock_properties.assert_called_with(mock_packet, "addr")
        mock_is_one_of.assert_called_with(mock_packet, "pkt_filter")
        mock_callback.assert_called_with(
            "type", "addr", "rssi", mock_packet, "properties"
        )

    @patch.object(DeviceFilter, "matches")
    @patch("checkbox_support.vendor.beacontools.scanner.is_one_of")
    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.get_properties"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.save_bt_addr")
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_process_report_filters_device_ok(
        self,
        mock_init,
        mock_addr,
        mock_properties,
        mock_is_one_of,
        mock_addr_filter,
    ):
        mock_init.return_value = None
        mock_callback = Mock()
        mock_packet = "packets"
        mock_properties.return_value = "properties"
        mock_is_one_of.return_value = True
        mock_addr_filter.return_value = True

        mon = Monitor()
        mon.hci_version = 8
        mon.callback = mock_callback
        mon.device_filter = [DeviceFilter()]
        mon.packet_filter = "pkt_filter"

        mon.process_report_data(mock_packet, "addr", "rssi", "type")
        mock_addr.assert_called_with(mock_packet, "addr")
        mock_properties.assert_called_with(mock_packet, "addr")
        mock_is_one_of.assert_called_with(mock_packet, "pkt_filter")
        mock_callback.assert_called_with(
            "type",
            "addr",
            "rssi",
            mock_packet,
            "properties",
        )
