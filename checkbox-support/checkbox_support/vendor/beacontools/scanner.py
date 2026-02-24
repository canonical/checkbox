"""Classes responsible for Beacon scanning."""
import logging
import struct
import sys
import threading
from importlib import import_module
from enum import IntEnum
from checkbox_support.vendor.construct import Struct, Byte, Bytes, GreedyRange, ConstructError

from checkbox_support.vendor.ahocorapy.keywordtree import KeywordTree

from .const import (CJ_MANUFACTURER_ID, EDDYSTONE_UUID,
                    ESTIMOTE_MANUFACTURER_ID, ESTIMOTE_UUID,
                    EVT_LE_ADVERTISING_REPORT, EXPOSURE_NOTIFICATION_UUID,
                    IBEACON_MANUFACTURER_ID, IBEACON_PROXIMITY_TYPE,
                    LE_META_EVENT, MANUFACTURER_SPECIFIC_DATA_TYPE,
                    MS_FRACTION_DIVIDER, OCF_LE_SET_SCAN_ENABLE,
                    OCF_LE_SET_SCAN_PARAMETERS, OGF_LE_CTL,
                    BluetoothAddressType, ScanFilter, ScannerMode, ScanType,
                    OCF_LE_SET_EXT_SCAN_PARAMETERS, OCF_LE_SET_EXT_SCAN_ENABLE,
                    EVT_LE_EXT_ADVERTISING_REPORT, OGF_INFO_PARAM,
                    OCF_LE_READ_LOCAL_SUPPORTED_FEATURES,
                    OCF_LE_READ_MAX_ADVERTISING_DATA_LENGTH,
                    OCF_READ_LOCAL_VERSION, EVT_CMD_COMPLETE)
from .structs.common import HciAdReportEvent
from .const import MetaEventReportTypeEnum as MERTE
from .device_filters import BtAddrFilter, DeviceFilter
from .packet_types import (EddystoneEIDFrame, EddystoneEncryptedTLMFrame,
                           EddystoneTLMFrame, EddystoneUIDFrame,
                           EddystoneURLFrame)
from .parser import parse_packet
from .utils import (bin_to_int, bt_addr_to_string, get_mode, is_one_of,
                    is_packet_type, to_int)


class HCIVersion(IntEnum):
    """HCI version enumeration

    https://www.bluetooth.com/specifications/assigned-numbers/host-controller-interface/
    """
    BT_CORE_SPEC_1_0 = 0
    BT_CODE_SPEC_1_1 = 1
    BT_CODE_SPEC_1_2 = 2
    BT_CORE_SPEC_2_0 = 3
    BT_CORE_SPEC_2_1 = 4
    BT_CORE_SPEC_3_0 = 5
    BT_CORE_SPEC_4_0 = 6
    BT_CORE_SPEC_4_1 = 7
    BT_CORE_SPEC_4_2 = 8
    BT_CORE_SPEC_5_0 = 9
    BT_CORE_SPEC_5_1 = 10
    BT_CORE_SPEC_5_2 = 11
    BT_CORE_SPEC_5_3 = 12
    BT_CORE_SPEC_5_4 = 13
    BT_CORE_SPEC_6_0 = 14
    BT_CORE_SPEC_6_1 = 15


_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)
stdout_handler = logging.StreamHandler(sys.stdout)
_LOGGER.addHandler(stdout_handler)

# pylint: disable=no-member


class BeaconScanner(object):
    """Scan for Beacon advertisements."""

    def __init__(self, callback, bt_device_id=0, device_filter=None, packet_filter=None, scan_parameters=None, debug=False):
        """Initialize scanner."""
        # check if device filters are valid
        if debug:
            _LOGGER.setLevel(logging.DEBUG)
        if device_filter is not None:
            if not isinstance(device_filter, list):
                device_filter = [device_filter]
            if len(device_filter) > 0:
                for filtr in device_filter:
                    if not isinstance(filtr, DeviceFilter):
                        raise ValueError("Device filters must be instances of DeviceFilter")
            else:
                device_filter = None

        # check if packet filters are valid
        if packet_filter is not None:
            if not isinstance(packet_filter, list):
                packet_filter = [packet_filter]
            if len(packet_filter) > 0:
                for filtr in packet_filter:
                    if not is_packet_type(filtr):
                        raise ValueError("Packet filters must be one of the packet types")
            else:
                packet_filter = None

        if scan_parameters is None:
            scan_parameters = {}

        self._mon = Monitor(callback, bt_device_id, device_filter, packet_filter, scan_parameters)

    def start(self):
        """Start beacon scanning."""
        self._mon.start()

    def stop(self):
        """Stop beacon scanning."""
        self._mon.terminate()


class Monitor(threading.Thread):
    """Continously scan for BLE advertisements."""

    def __init__(self, callback, bt_device_id, device_filter, packet_filter, scan_parameters):
        """Construct interface object."""
        # do import here so that the package can be used in parsing-only mode (no bluez required)
        self.backend = import_module('checkbox_support.vendor.beacontools.backend')

        threading.Thread.__init__(self)
        self.daemon = False
        self.keep_going = True
        self.callback = callback

        # number of the bt device (hciX)
        self.bt_device_id = bt_device_id
        # list of beacons to monitor
        self.device_filter = device_filter
        self.mode = get_mode(device_filter)
        # list of packet types to monitor
        self.packet_filter = packet_filter
        # bluetooth socket
        self.socket = None
        # keep track of Eddystone Beacon <-> bt addr mapping
        self.eddystone_mappings = []
        # parameters to pass to bt device
        self.scan_parameters = scan_parameters
        # hci version
        self.hci_version = HCIVersion.BT_CORE_SPEC_1_0

        # construct an aho-corasick search tree for efficient prefiltering
        service_uuid_prefix = b"\x03\x03"
        self.kwtree = KeywordTree()
        if self.mode & ScannerMode.MODE_IBEACON:
            self.kwtree.add(bytes([MANUFACTURER_SPECIFIC_DATA_TYPE]) + IBEACON_MANUFACTURER_ID + IBEACON_PROXIMITY_TYPE)
        if self.mode & ScannerMode.MODE_EDDYSTONE:
            self.kwtree.add(service_uuid_prefix + EDDYSTONE_UUID)
        if self.mode & ScannerMode.MODE_ESTIMOTE:
            self.kwtree.add(service_uuid_prefix + ESTIMOTE_UUID)
            self.kwtree.add(bytes([MANUFACTURER_SPECIFIC_DATA_TYPE]) + ESTIMOTE_MANUFACTURER_ID)
        if self.mode & ScannerMode.MODE_CJMONITOR:
            self.kwtree.add(bytes([MANUFACTURER_SPECIFIC_DATA_TYPE]) + CJ_MANUFACTURER_ID)
        if self.mode & ScannerMode.MODE_EXPOSURE_NOTIFICATION:
            self.kwtree.add(service_uuid_prefix + EXPOSURE_NOTIFICATION_UUID)
        self.kwtree.finalize()

    def run(self):
        """Continously scan for BLE advertisements."""
        self.socket = self.backend.open_dev(self.bt_device_id)

        self.hci_version = self.get_hci_version()
        self.support_ext_advertising = self.is_le_extended_advertising_support()
        _LOGGER.info(
            "# Extended advertising support: %s", self.support_ext_advertising
        )
        max_advertising_data_length = self.get_le_adv_report_length()
        _LOGGER.info(
            "# Max advertising data length: %s", max_advertising_data_length
        )
        self.toggle_scan(False)
        self.set_scan_parameters(**self.scan_parameters)
        self.toggle_scan(True)

        while self.keep_going:
            pkt = self.socket.recv(max_advertising_data_length)
            event = to_int(pkt[1])

            # Print opcode and error code when HCI command failed
            # This may helps to identify issue
            if event == EVT_CMD_COMPLETE:
                # HCI completed command event
                # pkt[1] = event type
                # pkt[2] = the length of data
                # pkt[3] = number of packets
                # pkt[5] + pkt[4] = opcode
                # pkt[6:] = return parameter(s)
                # pkt[6] is the command status for following commands
                #   - LE_Set_Extended_Scan_Enable
                #   - LE_Set_Extended_Scan_Parameters
                #   - LE_Set_Scan_Enable
                #   - LE_Set_Scan_Parameters
                # 0x0 means command succeeded for following commands
                # Others means command failed.
                error_code = to_int(pkt[6])
                if error_code != 0:
                    _LOGGER.warning(
                        "Warning: HCI Command failed. "
                        "Error code: {}, Payload: {}".format(
                            hex(error_code), pkt
                        )
                    )
            elif event == LE_META_EVENT:
                subevent = to_int(pkt[3])
                if subevent in [
                    EVT_LE_ADVERTISING_REPORT, EVT_LE_EXT_ADVERTISING_REPORT
                ]:
                    # we have an BLE advertisement
                    self.process_packet(pkt)
        self.socket.close()

    def get_hci_version(self):
        """Gets the HCI version"""
        local_version = Struct(
            "status" / Byte,
            "hci_version" / Byte,
            "hci_revision" / Bytes(2),
            "lmp_version" / Byte,
            "manufacturer_name" / Bytes(2),
            "lmp_subversion" / Bytes(2),
        )

        try:
            resp = self.backend.send_req(self.socket, OGF_INFO_PARAM, OCF_READ_LOCAL_VERSION,
                                         EVT_CMD_COMPLETE, local_version.sizeof(), bytes(), 0)
            return HCIVersion(GreedyRange(local_version).parse(resp)[0]["hci_version"])
        except (ConstructError, NotImplementedError):
            return HCIVersion.BT_CORE_SPEC_1_0

    def get_le_adv_report_length(self):
        """
        Read the maximum length of data supported by the Controller
        for use as advertisement data or
            scan response data in an advertising event or
            as periodic advertisement data.

        set the _max_advertising_data_length to 255 when this command is not supported

        Reference: https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-60/out/en/host-controller-interface/host-controller-interface-functional-specification.html#UUID-e1de0ec4-eba6-5365-4f6a-0de9d5bfb7be
        """
        try:
            _LOGGER.info("# Checking the LE Extended advertising length")
            resp = self.backend.send_req(
                self.socket,
                OGF_LE_CTL,
                OCF_LE_READ_MAX_ADVERTISING_DATA_LENGTH,
                EVT_CMD_COMPLETE,
                1000,
                bytes(),
                0,
            )
            _LOGGER.debug(
                "Received response from controller. raw: %s",
                " ".join([hex(pk) for pk in resp]),
            )

            status = struct.unpack("B", resp[0:1])[0]
            if status != 0:
                _LOGGER.error("HCI command failed with status 0x%02x.", status)
            else:
                data = struct.unpack_from("<H", resp, 1)[0]
                return data
        except (struct.error, TypeError) as err:
            _LOGGER.error(err)
        _LOGGER.warning(
            "Failed to get the max_advertising_data_length from controller"
            ", return '255'"
        )
        return 255

    def is_le_extended_advertising_support(self):
        is_supported = False
        _LOGGER.info("# Checking the LE Extended advertising capability")
        resp = self.backend.send_req(
            self.socket,
            OGF_LE_CTL,
            OCF_LE_READ_LOCAL_SUPPORTED_FEATURES,
            EVT_CMD_COMPLETE,
            1000,
            bytes(),
            0,
        )
        _LOGGER.info("Received response from controller.")
        # The response is a binary string containing the event data.
        # For a successful Command Complete event for this command, the structure is:
        # Index 0-2: Event header (already processed by hci_send_req)
        # Index 3: Status (1 byte). 0x00 means success.
        # Index 4-11: LE Features (8 bytes / 64 bits). This is the feature mask.
        status, data = struct.unpack_from("<B8s", resp)

        if status != 0:
            _LOGGER.error("HCI command failed with status 0x%02x.", status)
            return False

        _LOGGER.info(
            "Raw 8-byte LE feature mask: %s",
            " ".join(["%x" % pk for pk in data]),
        )

        # According to the Bluetooth Core Specification (v5.0+), support for
        # "LE Extended Advertising" is indicated by bit 12 of the 64-bit feature mask.
        #
        # Let's break down the 8-byte (64-bit) mask:
        # Byte 0: bits 0-7
        # Byte 1: bits 8-15
        # ... and so on.
        #
        # Bit 12 falls within the second byte (Byte 1).
        # Specifically, it is the 5th bit within that byte (12 % 8 = 4).
        # Bit position (0-indexed): 0 1 2 3 [4] 5 6 7
        # Bit value:               1 2 4 8 [16] 32 64 128
        #
        # So we need to check if the 5th bit (value 16 or 0x10) is set in the second byte.

        # Extract the second byte (index 1)
        byte_1 = data[1]

        # Check if the 5th bit (mask 0x10) is set
        # (1 << 4) is a programmatic way to create the mask for the 5th bit (0x10).
        if (byte_1 & (1 << 4)):
            is_supported = True

        return is_supported

    def set_scan_parameters(self, scan_type=ScanType.ACTIVE, interval_ms=10, window_ms=10,
                            address_type=BluetoothAddressType.RANDOM, filter_type=ScanFilter.ALL):
        """"Sets the le scan parameters

        For extended set scan parameters command additional parameter scanning PHYs has to be provided.
        The parameter indicates the PHY(s) on which the advertising packets should be received on the
        primary advertising physical channel. For further information have a look on BT Core 5.1 Specification,
        page 1439 ( LE Set Extended Scan Parameters command).

        Args:
            scan_type: ScanType.(PASSIVE|ACTIVE)
            interval: ms (as float) between scans (valid range 2.5ms - 10240ms or 40.95s for extended version)
                ..note:: when interval and window are equal, the scan
                    runs continuos
            window: ms (as float) scan duration (valid range 2.5ms - 10240ms or 40.95s for extended version)
            address_type: Bluetooth address type BluetoothAddressType.(PUBLIC|RANDOM)
                * PUBLIC = use device MAC address
                * RANDOM = generate a random MAC address and use that
            filter: ScanFilter.(ALL|WHITELIST_ONLY) only ALL is supported, which will
                return all fetched bluetooth packets (WHITELIST_ONLY is not supported,
                because OCF_LE_ADD_DEVICE_TO_WHITE_LIST command is not implemented)

        Raises:
            ValueError: A value had an unexpected format or was not in range
        """
        max_interval = (0xFFFF if self.support_ext_advertising else 0x4000)
        interval_fractions = interval_ms / MS_FRACTION_DIVIDER
        if interval_fractions < 0x0004 or interval_fractions > max_interval:
            raise ValueError(
                "Invalid interval given {}, must be in range of 2.5ms to {}ms!".format(
                    interval_fractions, max_interval * MS_FRACTION_DIVIDER))
        window_fractions = window_ms / MS_FRACTION_DIVIDER
        if window_fractions < 0x0004 or window_fractions > max_interval:
            raise ValueError(
                "Invalid window given {}, must be in range of 2.5ms to {}ms!".format(
                    window_fractions, max_interval * MS_FRACTION_DIVIDER))

        interval_fractions, window_fractions = int(interval_fractions), int(window_fractions)

        if self.support_ext_advertising:
            _LOGGER.info("# Issue LE Set Extended Scan Parameters by hci command")
            command_field = OCF_LE_SET_EXT_SCAN_PARAMETERS
            scan_parameter_pkg = struct.pack(
                "<BBBBHH",
                address_type,
                filter_type,
                1,  # scan advertisements on the LE 1M PHY
                scan_type,
                interval_fractions,
                window_fractions)
        else:
            _LOGGER.info("# Issue LE Set Scan Parameters by hci command")
            command_field = OCF_LE_SET_SCAN_PARAMETERS
            scan_parameter_pkg = struct.pack(
                "<BHHBB",
                scan_type,
                interval_fractions,
                window_fractions,
                address_type,
                filter_type)

        self.backend.send_cmd(self.socket, OGF_LE_CTL, command_field, scan_parameter_pkg)

    def toggle_scan(self, enable, filter_duplicates=False):
        """Enables or disables BLE scanning

        For extended set scan enable command additional parameters duration and period have
        to be provided. When both are zero, the controller shall continue scanning until
        scanning is disabled. For non-zero values have a look on BT Core 5.1 Specification,
        page 1442 (LE Set Extended Scan Enable command).

        Args:
            enable: boolean value to enable (True) or disable (False) scanner
            filter_duplicates: boolean value to enable/disable filter, that
                omits duplicated packets"""
        if self.support_ext_advertising:
            _LOGGER.info("# Issue LE Set Extended Scan Enable to '%s' by hci command", enable)
            command_field = OCF_LE_SET_EXT_SCAN_ENABLE
            command = struct.pack("<BBHH", enable, filter_duplicates,
                                  0,  # duration
                                  0   # period
                                  )
        else:
            _LOGGER.info("# Issue LE Set Scan Enable to '%s' by hci command", enable)
            command_field = OCF_LE_SET_SCAN_ENABLE
            command = struct.pack("BB", enable, filter_duplicates)

        self.backend.send_cmd(self.socket, OGF_LE_CTL, command_field, command)

    def dump_reports(self, reports):
        for report in reports:
            _LOGGER.debug(
                "<evt_type: %s> <mac: %s> <rssi: %s> <data: %s>",
                report.evt_type,
                bt_addr_to_string(report.bdaddr),
                to_int(report.rssi),
                report.data
            )

    def process_packet(self, pkt):
        """Parse the packet and call callback if one of the filters matches."""
        subevent = le_event_data = None
        _LOGGER.debug(
            "## Received packet. Length: %d. Data: %s",
            len(pkt),
            " ".join([hex(pk) for pk in pkt]),
        )
        try:
            le_event_data = HciAdReportEvent.parse(pkt)
        except ConstructError:
            _LOGGER.warning("Unexpected pkt: %s", pkt)
            return

        if not le_event_data:
            return

        subevent = MERTE(le_event_data.subevent)
        # the EVT_LE_EXT_ADVERTISING_REPORT with eddystone URL frame is
        # expected to received when LE extended advertising is supported.
        # Otherwise the EVT_LE_ADVERTISING_REPORT with eddystone URL frame
        # is expected to received
        expect_evt = (
            MERTE.LE_EXT_ADVERTISING_REPORT
            if self.support_ext_advertising
            else MERTE.LE_ADVERTISING_REPORT
        )

        if isinstance(subevent, MERTE):
            subevent_str = "{}({})".format(subevent.name, subevent.value)
        else:
            subevent_str = subevent

        self.dump_reports(le_event_data.reports)
        if subevent != expect_evt:
            _LOGGER.error(
                "Unexpected event detected: Type: {}".format(subevent_str)
            )
            return

        if le_event_data.reports:
            _LOGGER.debug(
                "  Parsing %d reports in  %s event (packet length: %d)...",
                le_event_data.num_reports,
                subevent_str,
                len(pkt),
            )
            for report in le_event_data.reports:
                eddystone_data = parse_packet(report.data)
                if not eddystone_data:
                    continue

                _LOGGER.info("  Found an eddystone report")
                self.process_report_data(
                    eddystone_data,
                    bt_addr_to_string(report.bdaddr),
                    to_int(report.rssi),
                    subevent,
                )

    def process_report_data(self, packet, bt_addr, rssi, subevent):
        # we need to remeber which eddystone beacon has which bt address
        # because the TLM and URL frames do not contain the namespace and instance
        self.save_bt_addr(packet, bt_addr)
        # properties holds the identifying information for a beacon
        # e.g. instance and namespace for eddystone; uuid, major, minor for iBeacon
        properties = self.get_properties(packet, bt_addr)

        if self.device_filter is None and self.packet_filter is None:
            # no filters selected
            self.callback(subevent, bt_addr, rssi, packet, properties)

        elif self.device_filter is None:
            # filter by packet type
            if is_one_of(packet, self.packet_filter):
                self.callback(subevent, bt_addr, rssi, packet, properties)
        else:
            # filter by device and packet type
            if self.packet_filter and not is_one_of(packet, self.packet_filter):
                # return if packet filter does not match
                return

            # iterate over filters and call .matches() on each
            for filtr in self.device_filter:
                if isinstance(filtr, BtAddrFilter):
                    if filtr.matches({'bt_addr':bt_addr}):
                        self.callback(subevent, bt_addr, rssi, packet, properties)
                        return

                elif filtr.matches(properties):
                    self.callback(subevent, bt_addr, rssi, packet, properties)
                    return

    def save_bt_addr(self, packet, bt_addr):
        """Add to the list of mappings."""
        if isinstance(packet, EddystoneUIDFrame):
            # remove out old mapping
            new_mappings = [m for m in self.eddystone_mappings if m[0] != bt_addr]
            new_mappings.append((bt_addr, packet.properties))
            self.eddystone_mappings = new_mappings

    def get_properties(self, packet, bt_addr):
        """Get properties of beacon depending on type."""
        if is_one_of(packet, [EddystoneTLMFrame, EddystoneURLFrame, \
                              EddystoneEncryptedTLMFrame, EddystoneEIDFrame]):
            # here we retrieve the namespace and instance which corresponds to the
            # eddystone beacon with this bt address
            return self.properties_from_mapping(bt_addr)
        else:
            return packet.properties

    def properties_from_mapping(self, bt_addr):
        """Retrieve properties (namespace, instance) for the specified bt address."""
        for addr, properties in self.eddystone_mappings:
            if addr == bt_addr:
                return properties
        return None

    def terminate(self):
        """Signal runner to stop and join thread."""
        self.toggle_scan(False)
        self.keep_going = False
        self.join(timeout=5)
