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

import unittest
from unittest.mock import patch, Mock

from checkbox_support.vendor.beacontools.scanner import HCIVersion
from checkbox_support.vendor.beacontools.scanner import Monitor
from checkbox_support.vendor.beacontools.device_filters import (
    BtAddrFilter,
    DeviceFilter,
)


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
            debug=True,
        )
        self.assertEqual(mon.backend, "import")
        self.assertEqual(mon.daemon, False)
        self.assertEqual(mon.keep_going, True)
        self.assertEqual(mon.callback, "callback")
        self.assertEqual(mon.debug, True)
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
        mock_instance.finalize.assert_called_once()

    def test_run_ok(self):
        pass

    def test_set_scan_parameters(self):
        pass

    def test_toggle_scan(self):
        pass

    @patch("builtins.print")
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_analyze_le_adv_event_report(self, mock_mon_init, mock_print):
        mock_mon_init.return_value = None

        pkts = (
            "03 6e 02 02 11 22 33 44 55 66 77 88 99 00 11 22 33 44 55 66"
        ).split()
        packet = b"".join(
            [int(p, 16).to_bytes(1, byteorder="big") for p in pkts]
        )
        mon = Monitor()
        mon.debug = True
        event, payload, rssi, addr = mon.analyze_le_adv_event(packet)
        self.assertEqual(event, int(pkts[3], 16))
        self.assertEqual(payload, packet[14:-1])
        self.assertEqual(rssi, int(pkts[-1], 16))
        self.assertEqual(addr, "99:88:77:66:55:44")
        mock_print.assert_called_with(
            "LE Meta Event: subevent: 0x2, payload: 0x11 0x22 0x33 0x44 0x55, "
            "rssi: 102, bt_addr: 99:88:77:66:55:44"
        )

    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_analyze_le_adv_ext_event_report(self, mock_mon_init):
        mock_mon_init.return_value = None

        pkts = (
            "03 6e 02 0d 11 22 33 44 55 66 77 88 99 00 11 22 33 44 55 66 "
            "77 88 99 00 11 22 33 44 55 66 77 88 99 00 11 22 33 44 55 66"
        ).split()
        packet = b"".join(
            [int(p, 16).to_bytes(1, byteorder="big") for p in pkts]
        )
        mon = Monitor()
        mon.debug = False
        event, payload, rssi, addr = mon.analyze_le_adv_event(packet)
        self.assertEqual(event, int(pkts[3], 16))
        self.assertEqual(payload, packet[29:])
        self.assertEqual(rssi, int(pkts[18], 16))
        self.assertEqual(addr, "99:88:77:66:55:44")

    @patch("builtins.print")
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_analyze_le_adv_ext_event_report_failed(
        self, mock_mon_init, mock_print
    ):
        mock_mon_init.return_value = None

        pkts = ["03", "6e", "02", "ff", "11", "22", "33", "44", "55", "66"]

        packet = b"".join(
            [int(p, 16).to_bytes(1, byteorder="big") for p in pkts]
        )
        mon = Monitor()
        mon.debug = False
        event, payload, rssi, addr = mon.analyze_le_adv_event(packet)
        self.assertEqual(event, None)
        self.assertEqual(payload, None)
        self.assertEqual(rssi, None)
        self.assertEqual(addr, None)
        mock_print.assert_called_with("Error pkt: ", packet)

    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.get_properties"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.save_bt_addr")
    @patch("checkbox_support.vendor.beacontools.scanner.parse_packet")
    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.analyze_le_adv_event"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_process_packet_no_filter_ok(
        self, mock_init, mock_ana, mock_parse, mock_addr, mock_properties
    ):
        mock_init.return_value = None
        mock_callback = Mock()
        mock_ana.return_value = (2, "payload", "rssi", "addr")
        mock_packet = Mock()
        mock_packet.url = "url"
        mock_parse.return_value = mock_packet
        mock_properties.return_value = "properties"

        mon = Monitor()
        mon.hci_version = 8
        mon.callback = mock_callback
        mon.device_filter = None
        mon.packet_filter = None

        mon.process_packet("packets")
        mock_ana.assert_called_with("packets")
        mock_parse.assert_called_with("payload")
        mock_addr.assert_called_with(mock_packet, "addr")
        mock_properties.assert_called_with(mock_packet, "addr")
        mock_callback.assert_called_with(
            2, "addr", "rssi", mock_packet, "properties"
        )

    @patch("checkbox_support.vendor.beacontools.scanner.is_one_of")
    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.get_properties"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.save_bt_addr")
    @patch("checkbox_support.vendor.beacontools.scanner.parse_packet")
    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.analyze_le_adv_event"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_process_packet_packet_filter_ok(
        self,
        mock_init,
        mock_ana,
        mock_parse,
        mock_addr,
        mock_properties,
        mock_func,
    ):
        mock_init.return_value = None
        mock_callback = Mock()
        mock_ana.return_value = (2, "payload", "rssi", "addr")
        mock_packet = Mock()
        mock_packet.url = "url"
        mock_parse.return_value = mock_packet
        mock_properties.return_value = "properties"
        mock_func.return_value = True

        mon = Monitor()
        mon.hci_version = 8
        mon.callback = mock_callback
        mon.device_filter = None
        mon.packet_filter = "pkt_filter"

        mon.process_packet("packets")
        mock_ana.assert_called_with("packets")
        mock_parse.assert_called_with("payload")
        mock_addr.assert_called_with(mock_packet, "addr")
        mock_properties.assert_called_with(mock_packet, "addr")
        mock_func.assert_called_with(mock_packet, "pkt_filter")
        mock_callback.assert_called_with(
            2, "addr", "rssi", mock_packet, "properties"
        )

    @patch("checkbox_support.vendor.beacontools.scanner.is_one_of")
    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.get_properties"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.save_bt_addr")
    @patch("checkbox_support.vendor.beacontools.scanner.parse_packet")
    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.analyze_le_adv_event"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_process_packet_device_filter_not_match(
        self,
        mock_init,
        mock_ana,
        mock_parse,
        mock_addr,
        mock_properties,
        mock_is_one_of,
    ):
        mock_init.return_value = None
        mock_callback = Mock()
        mock_ana.return_value = (2, "payload", "rssi", "addr")
        mock_packet = Mock()
        mock_packet.url = "url"
        mock_parse.return_value = mock_packet
        mock_properties.return_value = "properties"
        mock_is_one_of.return_value = False

        mon = Monitor()
        mon.hci_version = 8
        mon.callback = mock_callback
        mon.device_filter = "dev_filter"
        mon.packet_filter = "pkt_filter"

        mon.process_packet("packets")
        mock_ana.assert_called_with("packets")
        mock_parse.assert_called_with("payload")
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
    @patch("checkbox_support.vendor.beacontools.scanner.parse_packet")
    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.analyze_le_adv_event"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_process_packet_filters_addr_ok(
        self,
        mock_init,
        mock_ana,
        mock_parse,
        mock_addr,
        mock_properties,
        mock_is_one_of,
        mock_addr_filter,
    ):
        mock_init.return_value = None
        mock_callback = Mock()
        mock_ana.return_value = (2, "payload", "rssi", "addr")
        mock_packet = Mock()
        mock_packet.url = "url"
        mock_parse.return_value = mock_packet
        mock_properties.return_value = "properties"
        mock_is_one_of.return_value = True
        mock_addr_filter.return_value = True

        mon = Monitor()
        mon.hci_version = 8
        mon.callback = mock_callback
        mon.device_filter = [BtAddrFilter("00:11:22:33:44:55")]
        mon.packet_filter = "pkt_filter"

        mon.process_packet("packets")
        mock_ana.assert_called_with("packets")
        mock_parse.assert_called_with("payload")
        mock_addr.assert_called_with(mock_packet, "addr")
        mock_properties.assert_called_with(mock_packet, "addr")
        mock_is_one_of.assert_called_with(mock_packet, "pkt_filter")
        mock_callback.assert_called_with(
            2, "addr", "rssi", mock_packet, "properties"
        )

    @patch.object(DeviceFilter, "matches")
    @patch("checkbox_support.vendor.beacontools.scanner.is_one_of")
    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.get_properties"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.save_bt_addr")
    @patch("checkbox_support.vendor.beacontools.scanner.parse_packet")
    @patch(
        "checkbox_support.vendor.beacontools.scanner.Monitor.analyze_le_adv_event"
    )
    @patch("checkbox_support.vendor.beacontools.scanner.Monitor.__init__")
    def test_process_packet_filters_device_ok(
        self,
        mock_init,
        mock_ana,
        mock_parse,
        mock_addr,
        mock_properties,
        mock_is_one_of,
        mock_addr_filter,
    ):
        mock_init.return_value = None
        mock_callback = Mock()
        mock_ana.return_value = (2, "payload", "rssi", "addr")
        mock_packet = Mock()
        mock_packet.url = "url"
        mock_parse.return_value = mock_packet
        mock_properties.return_value = "properties"
        mock_is_one_of.return_value = True
        mock_addr_filter.return_value = True

        mon = Monitor()
        mon.hci_version = 8
        mon.callback = mock_callback
        mon.device_filter = [DeviceFilter()]
        mon.packet_filter = "pkt_filter"

        mon.process_packet("packets")
        mock_ana.assert_called_with("packets")
        mock_parse.assert_called_with("payload")
        mock_addr.assert_called_with(mock_packet, "addr")
        mock_properties.assert_called_with(mock_packet, "addr")
        mock_is_one_of.assert_called_with(mock_packet, "pkt_filter")
        mock_callback.assert_called_with(
            2, "addr", "rssi", mock_packet, "properties"
        )
