# This file is part of Checkbox.
#
# Copyright 2012-2022 Canonical Ltd.
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

from io import StringIO
from unittest import TestCase
from textwrap import dedent

from pkg_resources import resource_filename

from checkbox_support.parsers.udevadm import UdevadmParser, decode_id
from checkbox_support.parsers.udevadm import parse_udevadm_output


class UdevadmDataMixIn(object):
    """
    Mix in with a helper method to load sample udevadm data
    """

    def get_text(self, name):
        resource = 'parsers/tests/udevadm_data/{}.txt'.format(name)
        filename = resource_filename('checkbox_support', resource)
        with open(filename, 'rt', encoding='UTF-8') as stream:
            return stream.read()

    def get_lsblk(self, name):
        resource = 'parsers/tests/udevadm_data/{}.lsblk'.format(name)
        filename = resource_filename('checkbox_support', resource)
        try:
            with open(filename, 'rt', encoding='UTF-8') as stream:
                return stream.read()
        except (IOError, OSError):
            return None


class TestUdevadmParser(TestCase, UdevadmDataMixIn):

    def parse(self, name, with_lsblk=True, with_partitions=False):
        # Uncomment only for debugging purpose
        """
        attributes = ("path", "driver", "bus", "product_id", "vendor_id",
            "product", "vendor", "interface",)

        devices = parse_udevadm_output(self.get_text(name), 64)["device_list"]
        for i,j in enumerate(devices):
            print(i, j.category, [getattr(j, a) for a in attributes])
        """
        lsblk = ''
        if with_lsblk:
            lsblk = self.get_lsblk(name)
        return parse_udevadm_output(
            self.get_text(name), lsblk, with_partitions, 64)

    def count(self, devices, category):
        return len([d for d in devices if d.category == category])

    def test_openfirmware_network(self):
        stream = StringIO(dedent("""
            P: /devices/soc.0/ffe64000.ethernet
            E: DEVPATH=/devices/soc.0/ffe64000.ethernet
            E: DRIVER=XXXXX
            E: MODALIAS=of:NethernetTXXXXXCXXXXX,XXXXX
            E: OF_COMPATIBLE_0=XXXXX,XXXXX
            E: OF_COMPATIBLE_N=1
            E: OF_NAME=ethernet
            E: OF_TYPE=XXXXX
            E: SUBSYSTEM=platform
            E: UDEV_LOG=3

            P: /devices/soc.0/ffe64000.ethernet/net/eth1
            E: DEVPATH=/devices/soc.0/ffe64000.ethernet/net/eth1
            E: IFINDEX=3
            E: INTERFACE=eth1
            E: SUBSYSTEM=net
            E: UDEV_LOG=3
            """))
        parser = UdevadmParser(stream)
        devices = parser.run()
        self.assertEqual(devices[0].category, "NETWORK")


    def test_DELL_INSPIRON3521_TOUCHSCREEN(self):
        """
        Check devices category having the ID_INPUT_TOUCHSCREEN property
        """
        devices = self.parse("DELL_INSPIRON3521_TOUCHSCREEN")
        self.assertEqual(len(devices), 66)
        # Check the Accelerometer device category/product
        self.assertEqual(devices[37].category, "TOUCHSCREEN")
        self.assertEqual(devices[37].product, "ELAN Touchscreen")
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 2)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 0)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 1)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)

    def test_DELL_LATITUDEE4310(self):
        devices = self.parse("DELL_LATITUDEE4310")
        self.assertEqual(len(devices), 75)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 1)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "RAID"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)

    def test_DELL_LATITUDEE6430(self):
        devices = self.parse("DELL_LATITUDEE6430")
        self.assertEqual(len(devices), 80)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 0)
        self.assertEqual(self.count(devices, "CARDREADER"), 1)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 2)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "RAID"), 1)
        self.assertEqual(self.count(devices, "DISK"), 1)
        # Check that a Bluetooth device is properly detected
        # See https://bugs.launchpad.net/checkbox/+bug/1075052
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)

    def test_DELL_OPTIPLEX9020AIO(self):
        devices = self.parse("DELL_OPTIPLEX9020AIO")
        self.assertEqual(len(devices), 64)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 4)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 0)
        self.assertEqual(self.count(devices, "CARDREADER"), 3)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 0)
        self.assertEqual(self.count(devices, "RAID"), 1)
        # At least one network device must be detected to solve
        # https://bugs.launchpad.net/checkbox/+bug/1167733
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "DISK"), 1)

    def test_DELL_VOSTRO3460_FINGERPRINT(self):
        """
        This system has a fingerprint reader

        usb.ids:
        138a  Validity Sensors, Inc.
                0011  VFS5011 Fingerprint Reader
        """
        devices = self.parse("DELL_VOSTRO3460_FINGERPRINT")
        self.assertEqual(len(devices), 79)
        self.assertEqual(devices[35].category, "OTHER")
        self.assertEqual(devices[35].vendor_id, 0x0138a)
        self.assertEqual(devices[35].product_id, 0x0011)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 0)
        self.assertEqual(self.count(devices, "CARDREADER"), 2)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 2)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)

    def test_DELL_VOSTROV131(self):
        devices = self.parse("DELL_VOSTROV131")
        expected_devices = [
            ("RTL8111/8168 PCI Express Gigabit Ethernet controller",
             "NETWORK", "pci", 0x10EC, 0x8168),
            ("AR9285 Wireless Network Adapter (PCI-Express)",
             "WIRELESS", "pci", 0x168C, 0x002B)
        ]
        self.assertEqual(len(devices), 65)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 0)
        self.assertEqual(self.count(devices, "CDROM"), 0)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 0)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 2)
        self.verify_devices(devices, expected_devices)

    def test_DELL_XPS1340(self):
        devices = self.parse("DELL_XPS1340")
        self.assertEqual(len(devices), 76)
        self.assertEqual(self.count(devices, "VIDEO"), 2)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 3)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 1)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 1)
        self.assertEqual(self.count(devices, "MOUSE"), 0)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)

    def test_DELL_INSPIRON_7737_NVIDIA(self):
        devices = self.parse("DELL_INSPIRON_7737_NVIDIA")
        expected_devices = [(None,
                             "WIRELESS", "pci", 0x8086, 0x08b1),
                            (None,
                             "VIDEO", "pci", 0x10de, 0x0fe4),
                            (None,
                             "VIDEO", "pci", 0x8086, 0x0a16)
                            ]
        # The first video device is an NVIDIA GPU, which is too new
        # to have a  device name. The second one is the built-in Haswell
        # GPU.
        self.assertEqual(len(devices), 63)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "VIDEO"), 2)
        self.assertEqual(self.count(devices, "AUDIO"), 4)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "HIDRAW"), 0)
        self.verify_devices(devices, expected_devices)

    def test_DELL_INSPIRON_3048_AMD(self):
        devices = self.parse("DELL_INSPIRON_3048")
        expected_devices = [(None,
                             "WIRELESS", "pci", 0x168c, 0x0036),
                            (None,
                             "VIDEO", "pci", 0x1002, 0x6664),
                            (None,
                             "VIDEO", "pci", 0x8086, 0x0402)
                            ]
        # The first video device is an AMD GPU, which is too new
        # to have a  device name. The second one is the built-in Haswell
        # GPU.
        self.assertEqual(len(devices), 70)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 4)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "VIDEO"), 2)
        self.verify_devices(devices, expected_devices)

    def test_DELL_POWEREDGE_R820_NVME(self):
        devices = self.parse("DELL_POWEREDGE_R820_NVME")
        expected_devices = [("NetXtreme BCM5720 Gigabit Ethernet PCIe",
                             "NETWORK", "pci", 0x14E4, 0x165F, 4),
                            ]
        self.assertEqual(len(devices), 257)
        self.assertEqual(self.count(devices, "NETWORK"), 4)
        self.assertEqual(self.count(devices, "AUDIO"), 0)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "DISK"), 3)
        self.verify_devices(devices, expected_devices)

    def test_REALTEK_CARD_READER_AND_NVME(self):
        devices = self.parse("REALTEK_CARD_READER_AND_NVME")
        self.assertEqual(len(devices), 130)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 4)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 1)
        # Check that the "Realtek PCIe card reader" is well reported as a
        # card reader even if "Realtek PCIe card reader" is actually reported
        # by udev as the driver name of this device O_o !
        self.assertEqual(self.count(devices, "CARDREADER"), 1)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "DISK"), 2)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 1)

    def test_TOSHIBA_NVME(self):
        devices = self.parse("TOSHIBA_NVME")
        self.assertEqual(len(devices), 133)
        self.assertEqual(self.count(devices, "VIDEO"), 2)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 1)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 2)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 1)
        self.assertEqual(self.count(devices, "HIDRAW"), 1)

    def test_HOME_MADE(self):
        devices = self.parse("HOME_MADE")
        self.assertEqual(len(devices), 71)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 4)
        self.assertEqual(self.count(devices, "KEYBOARD"), 2)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 0)
        self.assertEqual(self.count(devices, "CARDREADER"), 2)
        self.assertEqual(self.count(devices, "CDROM"), 2)
        self.assertEqual(self.count(devices, "FLOPPY"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 1)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 0)
        self.assertEqual(self.count(devices, "WIRELESS"), 0)
        self.assertEqual(self.count(devices, "DISK"), 2)
        self.assertEqual(self.count(devices, "NETWORK"), 1)

    def test_HP_PAVILIONSLEEKBOOK14_ACCELEROMETER(self):
        devices = self.parse("HP_PAVILIONSLEEKBOOK14_ACCELEROMETER")
        self.assertEqual(len(devices), 58)
        self.assertEqual(devices[56].product, "ST LIS3LV02DL Accelerometer")
        self.assertEqual(devices[56].category, "ACCELEROMETER")
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 1)
        self.assertEqual(self.count(devices, "CDROM"), 0)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 0)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 1)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        # Check that a Bluetooth device is properly detected on PCI bus
        # See https://bugs.launchpad.net/checkbox/+bug/1036124
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)

    def test_HP_400_G2(self):
        devices = self.parse("HP_400_G2")
        self.assertEqual(len(devices), 72)
        self.assertEqual(self.count(devices, "OTHER"), 28)
        self.assertEqual(self.count(devices, "VIDEO"), 2)
        self.assertEqual(self.count(devices, "AUDIO"), 4)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 0)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 0)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        expected_devices = [(None, "VIDEO", "pci", 0x8086, 0x0412)]
        expected_devices = [(None, "VIDEO", "pci", 0x10DE, 0x107D)]
        self.verify_devices(devices, expected_devices)

    def test_HP_PRO2110(self):
        devices = self.parse("HP_PRO2110")
        self.assertEqual(len(devices), 59)
        # Check that the Avocent IBM 73P5832 is not a CAPTURE device
        # See https://bugs.launchpad.net/checkbox/+bug/1065064
        self.assertEqual(devices[33].product, "Avocent IBM 73P5832")
        self.assertNotEqual(devices[33].category, "CAPTURE")
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 0)
        self.assertEqual(self.count(devices, "CARDREADER"), 8)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 0)
        self.assertEqual(self.count(devices, "WIRELESS"), 0)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        expected_devices = [(None, "VIDEO", "pci", 0x8086, 0x2E32)]
        self.verify_devices(devices, expected_devices)

    def test_HP_PROBOOK6550B_ACCELEROMETER(self):
        devices = self.parse("HP_PROBOOK6550B_ACCELEROMETER")
        expected_devices = [("Centrino Advanced-N 6200",
                             "WIRELESS", "pci", 0x8086, 0x4239),
                            ("82577LC Gigabit Network Connection",
                             "NETWORK", "pci", 0x8086, 0x10EB)
                            ]
        self.assertEqual(len(devices), 82)
        # Check the accelerometer device category/product
        self.assertEqual(devices[80].product, "ST LIS3LV02DL Accelerometer")
        self.assertEqual(devices[80].category, "ACCELEROMETER")
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 1)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 1)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 1)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.verify_devices(devices, expected_devices)

    def test_LENOVO_E431(self):
        devices = self.parse("LENOVO_E431")
        self.assertEqual(len(devices), 100)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 1)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)

    def test_LENOVO_E445(self):
        devices = self.parse("LENOVO_E445")
        self.assertEqual(len(devices), 81)
        self.assertEqual(self.count(devices, "VIDEO"), 2)
        self.assertEqual(self.count(devices, "AUDIO"), 4)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 1)  # rtsx
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        # System has two CPUs, AMD Richland [Radeon HD 8650G] and
        # Sun PRO [Radeon HD 8570A/8570M]
        expected_devices = [(None, "VIDEO", "pci", 0x1002, 0x990b),
                            (None, "VIDEO", "pci", 0x1002, 0x6663)]
        self.verify_devices(devices, expected_devices)

    def test_LENOVO_T430S(self):
        devices = self.parse("LENOVO_T430S")
        expected_devices = [("Centrino Ultimate-N 6300",
                             "WIRELESS", "pci", 0x8086, 0x4238),
                            ("82579LM Gigabit Network Connection",
                             "NETWORK", "pci", 0x8086, 0x1502),
                            ("H5321 gw",
                             "WWAN", "usb", 0x0bdb, 0x1926)
                            ]
        self.assertEqual(len(devices), 115)
        # Check that the Thinkpad hotkeys are not a CAPTURE device
        self.assertEqual(devices[113].product, "ThinkPad Extra Buttons")
        self.assertEqual(devices[113].category, "OTHER")
        # Check that the Ericsson MBM module is set as a NETWORK device with
        # proper vendor/product names
        self.assertEqual(devices[59].product, "H5321 gw")
        self.assertEqual(
            devices[59].vendor,
            "Ericsson Business Mobile Networks BV")
        self.assertEqual(devices[59].category, "WWAN")
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 9)
        # Logitech Illuminated keyboard + T430S keyboard + KVM
        self.assertEqual(self.count(devices, "KEYBOARD"), 3)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 1)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "WWAN"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 2)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.verify_devices(devices, expected_devices)

    def test_PANDABOARD(self):
        devices = self.parse("PANDABOARD")
        self.assertEqual(len(devices), 18)
        # Check that the wireless product name is extracted from the platform
        # modalias
        self.assertEqual(devices[3].product, "wl12xx")
        self.assertEqual(self.count(devices, "VIDEO"), 0)
        self.assertEqual(self.count(devices, "AUDIO"), 0)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 0)
        self.assertEqual(self.count(devices, "CARDREADER"), 1)
        self.assertEqual(self.count(devices, "CDROM"), 0)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 0)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 0)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "DISK"), 0)

    def test_EMMC_AS_MAIN_DRIVE(self):
        devices = self.parse("EMMC_AS_MAIN_DRIVE")
        self.assertEqual(len(devices), 70)
        # Check that the eMMC drive is reported as a DISK
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 0)
        self.assertEqual(self.count(devices, "CDROM"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 0)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 0)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)
        self.assertEqual(self.count(devices, "DISK"), 1)

    def test_EMMC_INTEL_NUC_SNAPPY(self):
        devices = self.parse("INTEL_NUC_SNAPPY")
        self.assertEqual(len(devices), 78)
        # Check that the eMMC drive is reported as a DISK
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "WATCHDOG"), 1)

    def test_EMMC_NOT_AS_MAIN_DRIVE(self):
        devices = self.parse("EMMC_AS_MAIN_DRIVE", with_lsblk=False)
        self.assertEqual(len(devices), 70)
        # Check that the eMMC drive is not reported as a DISK without lsblk
        # data
        self.assertEqual(self.count(devices, "DISK"), 0)

    def test_SAMSUNG_N310(self):
        devices = self.parse("SAMSUNG_N310")
        self.assertEqual(len(devices), 59)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 0)
        self.assertEqual(self.count(devices, "CDROM"), 0)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 0)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        # Check that wireless device are properly detected even if the usb
        # modalias is wrong.
        # The PCI_CLASS is 20000 for the Atheros cards in this Samsung netbook
        # but 28000 anywhere else.
        # See https://bugs.launchpad.net/checkbox/+bug/855382
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)

    def test_LENOVO_T420(self):
        devices = self.parse("LENOVO_T420")
        expected_devices = [("Centrino Advanced-N 6205 [Taylor Peak]",
                             "WIRELESS", "pci", 0x8086, 0x85),
                            ("82579LM Gigabit Network Connection",
                             "NETWORK", "pci", 0x8086, 0x1502)
                            ]
        self.assertEqual(len(devices), 69)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.verify_devices(devices, expected_devices)

    def test_HP_ENVY_15_MEDIATEK_BT(self):
        devices = self.parse("HP_ENVY_15_MEDIATEK_BT")
        expected_devices = [
            (None, "WIRELESS", "pci", 0x14C3, 0x7630),
            ("RTL8111/8168B PCI Express Gigabit "
             "Ethernet controller", "NETWORK", "pci",
             0x10EC, 0x8168),
            (None, "BLUETOOTH", "usb", 0x0e8d, 0x763f)]
        self.assertEqual(len(devices), 66)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.verify_devices(devices, expected_devices)

    def test_HP_PAVILION14_NOTEBOOK_MEDIATEK_BT(self):
        devices = self.parse("HP_PAVILION14_NOTEBOOK_MEDIATEK_BT")
        expected_devices = [
            (None, "WIRELESS", "pci", 0x14C3, 0x7630),
            ("RTL8101E/RTL8102E PCI Express Fast "
             "Ethernet controller", "NETWORK", "pci",
             0x10EC, 0x8136),
            (None, "BLUETOOTH", "usb", 0x0e8d, 0x763f)]
        self.assertEqual(len(devices), 70)
        self.verify_devices(devices, expected_devices)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 1)

    def test_CALXEDA_HIGHBANK(self):
        # This is a very bare-bones SoC meant for server use
        devices = self.parse("CALXEDA_HIGHBANK")
        self.assertEqual(len(devices), 3)
        self.assertEqual(self.count(devices, "VIDEO"), 0)
        self.assertEqual(self.count(devices, "AUDIO"), 0)
        self.assertEqual(self.count(devices, "KEYBOARD"), 0)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 0)
        self.assertEqual(self.count(devices, "CARDREADER"), 0)
        self.assertEqual(self.count(devices, "CDROM"), 0)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 0)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "WIRELESS"), 0)
        self.assertEqual(self.count(devices, "NETWORK"), 2)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 0)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)

    def test_IBM_PSERIES_P7(self):
        # Apparently a virtualized system on a pSeries P7
        # Quite bare-bones, server-oriented system
        devices = self.parse("IBM_PSERIES_POWER7")
        self.assertEqual(self.count(devices, "VIDEO"), 0)
        self.assertEqual(self.count(devices, "AUDIO"), 0)
        self.assertEqual(self.count(devices, "KEYBOARD"), 0)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 0)
        self.assertEqual(self.count(devices, "CARDREADER"), 0)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 0)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "WIRELESS"), 0)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 0)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "DISK"), 2)
        self.assertEqual(len(devices), 4)

    def test_IBM_PSERIES_P8(self):
        # server-oriented system
        devices = self.parse("IBM_PSERIES_POWER8")
        self.assertEqual(self.count(devices, "VIDEO"), 0)
        self.assertEqual(self.count(devices, "AUDIO"), 0)
        self.assertEqual(self.count(devices, "KEYBOARD"), 0)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 0)
        self.assertEqual(self.count(devices, "CARDREADER"), 0)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 0)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "WIRELESS"), 0)
        self.assertEqual(self.count(devices, "NETWORK"), 4)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 0)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "RAID"), 2)
        self.assertEqual(self.count(devices, "DISK"), 9)
        self.assertEqual(len(devices), 46)

    def test_XEON(self):
        devices = self.parse("XEON")
        self.assertEqual(len(devices), 74)
        self.assertEqual(self.count(devices, "VIDEO"), 2)

    def test_QEMU_KVM(self):
        # A virtual machine, QEMU-KVM-based. Some of its devices are those
        # of the host system, we're interested mainly in network and disk
        # devices.
        # See https://bugs.launchpad.net/bugs/1355282
        devices = self.parse("QEMU_KVM")
        self.assertEqual(len(devices), 23)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 0)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 0)
        self.assertEqual(self.count(devices, "CDROM"), 0)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 0)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 0)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "SCSI"), 1)

    def test_VM_WITH_FLOPPY(self):
        # A virtual machine, with a floppy drive enabled.
        # We're interested mainly in the floppy device.
        # See https://bugs.launchpad.net/bugs/1539041
        devices = self.parse("VM_WITH_FLOPPY")
        self.assertEqual(len(devices), 83)
        self.assertEqual(self.count(devices, "FLOPPY"), 1)

    def test_ONE_CDROM_ONLY(self):
        # A system with only one BD drive but previously seen as two devices.
        # See https://bugs.launchpad.net/bugs/1328481
        devices = self.parse("ONE_CDROM_ONLY")
        self.assertEqual(len(devices), 98)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "HIDRAW"), 1)

    def test_DELL_IDRAC(self):
        # Ignore virtual devices created by Dell iDRAC manager
        # See https://bugs.launchpad.net/bugs/1308702
        devices = self.parse("DELL_IDRAC")
        self.assertEqual(len(devices), 246)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "DISK"), 2)
        self.assertEqual(self.count(devices, "FLOPPY"), 0)

    def test_DELL_IDRAC_2(self):
        # Ignore iDRAC Virtual NIC
        # See https://bugs.launchpad.net/bugs/1672415
        devices = self.parse("DELL_IDRAC_2")
        self.assertEqual(len(devices), 241)
        self.assertEqual(self.count(devices, "NETWORK"), 4)

    def test_DELL_VOSTRO_270(self):
        # Interesting because while its Intel video card has the same PCI
        # vendor/product ID as others (8086:0152) the subvendor_id and
        # subproduct_id attributes were causing it to not be recognized as
        # video.  HOWEVER, we can't just assume that all Intel video cards are
        # doing the same, so some creative quirking will be needed in the
        # parser to single these out.  It's a desktop system so no touchpad and
        # has an external mouse. 4 card readers.
        # Finally, it's a hybrid video system with a second Nvidia GPU.
        devices = self.parse("DELL_VOSTRO_270")
        self.assertEqual(self.count(devices, "VIDEO"), 2)
        self.assertEqual(self.count(devices, "AUDIO"), 4)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "TOUCHPAD"), 0)
        self.assertEqual(self.count(devices, "CARDREADER"), 4)
        self.assertEqual(self.count(devices, "CDROM"), 1)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 1)
        self.assertEqual(self.count(devices, "ACCELEROMETER"), 0)
        self.assertEqual(self.count(devices, "TOUCHSCREEN"), 0)
        self.assertEqual(self.count(devices, "DISK"), 2)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "RAID"), 0)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 0)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(len(devices), 68)
        # First card is an Intel Xeon E3-1200 v2/3rd Gen Core processor
        # Graphics Controller Second one is NVidia  GF119 [GeForce GT 620 OEM]
        expected_devices = [
            (None, "VIDEO", "pci", 0x8086, 0x0152),
            (None, "VIDEO", "pci", 0x10de, 0x1049),
            ("RTL8111/8168/8411 PCI Express Gigabit Ethernet Controller",
             "NETWORK", "pci", 0x10EC, 0x8168),
        ]
        self.verify_devices(devices, expected_devices)

    def test_CARA_T(self):
        # A Snappy system with CANBus
        devices = self.parse("CARA_T")
        self.assertEqual(len(devices), 79)
        self.assertEqual(self.count(devices, "VIDEO"), 0)
        self.assertEqual(self.count(devices, "AUDIO"), 0)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 1)
        self.assertEqual(self.count(devices, "CDROM"), 0)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 0)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 2)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "CANBUS"), 1)
        self.assertEqual(self.count(devices, "WATCHDOG"), 1)

    def test_CARA_T_SOCKETCAN(self):
        # A Snappy system with a SocketCAN device
        devices = self.parse("CARA_T_SOCKETCAN")
        self.assertEqual(len(devices), 79)
        self.assertEqual(self.count(devices, "VIDEO"), 0)
        self.assertEqual(self.count(devices, "AUDIO"), 0)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 1)
        self.assertEqual(self.count(devices, "CDROM"), 0)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 0)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "NETWORK"), 2)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "CANBUS"), 0)
        self.assertEqual(self.count(devices, "SOCKETCAN"), 1)
        self.assertEqual(self.count(devices, "WATCHDOG"), 1)

    def test_IBM_s390x_DASD(self):
        devices = self.parse("IBM_s390x_DASD")
        self.assertEqual(len(devices), 8)
        self.assertEqual(self.count(devices, "DISK"), 3)

    def test_MELLANOX_40GBPS(self):
        # An IBM Power S822LC with a 40 Gbps Mellanox NIC reported too few
        # network devices because one device's name (enP8p1s0) was a
        # substring of another (enP8p1s0d1), and was therefore ignored. See
        # https://bugs.launchpad.net/ubuntu/+source/linux/+bug/1675091
        devices = self.parse("MELLANOX_40GBPS")
        self.assertEqual(self.count(devices, "NETWORK"), 8)

    def test_VESTA_300(self):
        devices = self.parse("VESTA_300")
        self.assertEqual(len(devices), 15)
        self.assertEqual(self.count(devices, "NETWORK"), 1)
        self.assertEqual(self.count(devices, "WIRELESS"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 0)
        self.assertEqual(self.count(devices, "DISK"), 5)

    def test_NVIDIA_DGX_STATION(self):
        devices = self.parse("NVIDIA_DGX_STATION")
        self.assertEqual(len(devices), 230)
        self.assertEqual(self.count(devices, "NETWORK"), 2)
        self.assertEqual(self.count(devices, "VIDEO"), 4)
        self.assertEqual(self.count(devices, "DISK"), 2)

    def test_DELL_MICROCHIP_USB_TO_SPI(self):
        # USB to SPI reported as HIDRAW
        devices = self.parse("DELL_MICROCHIP_USB_TO_SPI")
        self.assertEqual(len(devices), 92)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "AUDIO"), 2)
        self.assertEqual(self.count(devices, "KEYBOARD"), 1)
        self.assertEqual(self.count(devices, "CARDREADER"), 2)
        self.assertEqual(self.count(devices, "CDROM"), 0)
        self.assertEqual(self.count(devices, "FIREWIRE"), 0)
        self.assertEqual(self.count(devices, "MOUSE"), 0)
        self.assertEqual(self.count(devices, "WIRELESS"), 0)
        self.assertEqual(self.count(devices, "NETWORK"), 4)
        self.assertEqual(self.count(devices, "BLUETOOTH"), 0)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "DISK"), 1)
        self.assertEqual(self.count(devices, "CANBUS"), 0)
        self.assertEqual(self.count(devices, "SOCKETCAN"), 0)
        self.assertEqual(self.count(devices, "HIDRAW"), 1)

    def test_INTEL_OPTANE_DC(self):
        devices = self.parse("INTEL_OPTANE_DC")
        self.assertEqual(len(devices), 365)
        self.assertEqual(self.count(devices, "NETWORK"), 2)
        self.assertEqual(self.count(devices, "DISK"), 2)

    def test_ELEMENT_BIOSCIENCES_INSTRUMENT(self):
        devices = self.parse("ELEMENT_BIOSCIENCES_INSTRUMENT")
        self.assertEqual(len(devices), 92)
        self.assertEqual(self.count(devices, "WATCHDOG"), 1)

    def test_SHUTTLE_DH170_WITH_USB_DISK(self):
        """ DH170 with USB stick comparing pre and post reboot. """
        devices_pre = self.parse("SHUTTLE_DH170_WITH_USB_DISK",
                                 with_partitions=True, with_lsblk=False)
        self.assertEqual(len(devices_pre), 70)
        self.assertEqual(self.count(devices_pre, "PARTITION"), 1)
        devices_post = self.parse("SHUTTLE_DH170_WITH_USB_DISK_REBOOTED",
                                  with_partitions=True, with_lsblk=False)
        self.assertEqual(len(devices_post), 70)
        self.assertEqual(self.count(devices_post, "PARTITION"), 1)
        # Pre and post have same number of deviecs and partitions
        self.assertEqual(len(devices_pre), len(devices_post))
        self.assertEqual(self.count(devices_pre, "PARTITION"),
                         self.count(devices_post, "PARTITION"))
        symlink_pre = symlink_post = ""
        for d in devices_pre:
            if d.category == "PARTITION":
                self.assertIsNotNone(d.symlink_uuid)
                self.assertEqual(d.name, "sdc1")
                self.assertEqual(d.symlink_uuid, "disk/by-uuid/C9DC-C426")
                symlink_pre = d.symlink_uuid
        for d in devices_post:
            if d.category == "PARTITION":
                self.assertIsNotNone(d.symlink_uuid)
                self.assertEqual(d.name, "sdb1")
                self.assertEqual(d.symlink_uuid, "disk/by-uuid/C9DC-C426")
                symlink_post = d.symlink_uuid
        # The symlink should follow the device
        self.assertEqual(symlink_pre, symlink_post)

    def test_SHUTTLE_DH270_WITH_CORAL(self):
        devices = self.parse("SHUTTLE_DH270_WITH_CORAL")
        self.assertEqual(self.count(devices, "TPU"), 1)

    def test_RPI2_WITH_CAMERA(self):
        devices = self.parse("RPI2_WITH_CAMERA")
        self.assertEqual(self.count(devices, "MMAL"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "DRI"), 0)

    def test_RPI2_WITH_CAMERA_V4L2(self):
        devices = self.parse("RPI2_WITH_CAMERA_V4L2")
        self.assertEqual(self.count(devices, "MMAL"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)

    def test_RPI3B_NO_M2M_CAPTURE(self):
        devices = self.parse("RPI3B")
        self.assertEqual(self.count(devices, "MMAL"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "DRI"), 0)

    def test_RPI4B4G_NO_M2M_CAPTURE(self):
        devices = self.parse("RPI4B4G")
        self.assertEqual(self.count(devices, "MMAL"), 1)
        self.assertEqual(self.count(devices, "CAPTURE"), 0)
        self.assertEqual(self.count(devices, "VIDEO"), 2)
        self.assertEqual(self.count(devices, "DRI"), 0)

    def test_ZCU104(self):
        devices = self.parse("ZCU104")
        self.assertEqual(self.count(devices, "VIDEO"), 1)
        self.assertEqual(self.count(devices, "DRI"), 0)

    def test_CAPTURE_METADATA(self):
        devices = self.parse("CAPTURE_METADATA")
        self.assertEqual(len(devices), 111)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)
        self.assertEqual(devices[41].category, "CAPTURE")
        self.assertTrue(devices[41].path.endswith("video0"))

    def test_CAPTURE_METADATA_2(self):
        devices = self.parse("CAPTURE_METADATA_2")
        self.assertEqual(len(devices), 135)
        self.assertEqual(self.count(devices, "CAPTURE"), 1)
        self.assertEqual(devices[45].category, "CAPTURE")
        self.assertTrue(devices[45].path.endswith("video0"))

    def test_RNDIS_AS_USB(self):
        devices = self.parse("RNDIS")
        self.assertEqual(len(devices), 226)
        self.assertEqual(self.count(devices, "USB"), 4)
        self.assertEqual(self.count(devices, "NETWORK"), 6)

    def test_NO_VIRTUAL_CDROM(self):
        devices = self.parse("VIRT_CDROM")
        self.assertEqual(len(devices), 107)
        self.assertEqual(self.count(devices, "CDROM"), 0)

    def test_CRYPTO_FDE_UC20(self):
        devices = self.parse("CRYPTO_FDE", with_partitions=True)
        self.assertEqual(len(devices), 93)
        self.assertEqual(self.count(devices, "PARTITION"), 1)

    def verify_devices(self, devices, expected_device_list):
        """
        Verify we have the expected quantity of each device given in the list,
        and that product name, category, bus, vendor_id and product_id match.
        The list contains a tuple with product name, category, bus, vendor and
        product.
        They look like (if we want to ensure there's one and only one device
        with these characteristics):
        [(name, category, bus, vendor_id, product_id)]
        OR if we want to ensure a system has X identical devices:
        [(name, category, bus, vendor_id, product_id, quantity)]
        Note that name can be None, in which case we don't need the
        name to match. All other attributes must have a value and match.
        """
        # See this bug, that prompted for closer inspection of
        # devices and IDs:
        # https://bugs.launchpad.net/checkbox/+bug/1211521
        for device in expected_device_list:
            # If it's a 5-tuple, then quantity to verify is 1.
            # If it's a 6-tuple, then 6th element is quantity to verify
            if len(device) == 5:
                quantity = 1
            elif len(device) == 6:
                quantity = device[5]

            # Find indices of devices that match this expected device by
            # product and vendor ID
            indices = [idx for idx, elem in enumerate(devices)
                       if elem.product_id == device[4] and
                       elem.vendor_id == device[3]]
            # If we have a name to match, eliminate everyhing without
            # that name (as they are bogus, uninteresting devices)
            if device[0] is not None:
                indices = [idx for idx in indices
                           if devices[idx].product == device[0]]
            # Here, devices that matched the one I'm looking for will be
            # pointed to in indices. These indices refer to the devices
            # list.

            # Now I can do my validation checks.
            # Do we have expected number of devices?
            self.assertEqual(len(indices), quantity,
                             "{} items of {} (id {}:{}) found".format(
                                 len(indices),
                                 device[0],
                                 device[3],
                                 device[4]))
            # For specific attribute checks, we will use only the first device.
            # If there were multiple devices found, they are all identical
            if device[0] is not None:
                self.assertEqual(devices[indices[0]].product, device[0],
                                 "Bad product name for {}".format(device[0]))
            self.assertEqual(devices[indices[0]].category, device[1],
                             "Bad category for {}".format(device[0]))
            self.assertEqual(devices[indices[0]].bus, device[2],
                             "Bad bus for {}".format(device[0]))
            self.assertEqual(devices[indices[0]].vendor_id, device[3],
                             "Bad vendor_id for {}".format(device[0]))
            self.assertEqual(devices[indices[0]].product_id, device[4],
                             "Bad product_id for {}".format(device[0]))


class TestDecodeId(TestCase):

    def test_string(self):
        self.assertEqual("USB 2.0", decode_id("USB 2.0"))

    def test_escape(self):
        self.assertEqual("USB 2.0", decode_id("USB\\x202.0"))

    def test_strip_whitespace(self):
        self.assertEqual("USB 2.0", decode_id("  USB 2.0  "))
