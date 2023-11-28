import unittest
import re
from checkbox_support.parsers.udevadm import UdevadmDevice, UdevadmParser


GENERIC_CAN_DEVICE_PARENT = """
P: /devices/platform/soc/401b4000.flexcan
L: 0
E: DEVPATH=/devices/platform/soc/401b4000.flexcan
E: SUBSYSTEM=platform
E: DRIVER=flexcan
E: OF_NAME=flexcan
E: OF_FULLNAME=/soc/flexcan@401b4000
E: OF_COMPATIBLE_0=nxp,s32cc-flexcan
E: OF_COMPATIBLE_N=1
E: OF_ALIAS_0=can0
E: MODALIAS=of:NflexcanT(null)Cnxp,s32cc-flexcan
E: USEC_INITIALIZED=13934580
E: ID_PATH=platform-401b4000.flexcan
E: ID_PATH_TAG=platform-401b4000_flexcan
"""

GENERIC_CAN_DEVICE_CHILD = """
P: /devices/platform/soc/401b4000.flexcan/net/can0
L: 0
E: DEVPATH=/devices/platform/soc/401b4000.flexcan/net/can0
E: SUBSYSTEM=net
E: INTERFACE=can0
E: IFINDEX=2
E: USEC_INITIALIZED=15630262
E: ID_MM_CANDIDATE=1
E: ID_PATH=platform-401b4000.flexcan
E: ID_PATH_TAG=platform-401b4000_flexcan
E: ID_NET_DRIVER=flexcan
E: ID_NET_LINK_FILE=/usr/lib/systemd/network/99-default.link
E: ID_NET_NAME=can0
E: SYSTEMD_ALIAS=/sys/subsystem/net/devices/can0
E: TAGS=:systemd:
E: CURRENT_TAGS=:systemd:
"""

LLCE_CAN_DEVICE_PARENT = """
P: /devices/platform/soc/43ff8000.llce/43ff8000.llce:llce_can0
L: 0
E: DEVPATH=/devices/platform/soc/43ff8000.llce/43ff8000.llce:llce_can0
E: SUBSYSTEM=platform
E: DRIVER=llce_can
E: OF_NAME=llce_can0
E: OF_FULLNAME=/soc/llce@43a00000/llce_can0
E: OF_COMPATIBLE_0=nxp,s32g-llce-can
E: OF_COMPATIBLE_N=1
E: MODALIAS=of:Nllce_can0T(null)Cnxp,s32g-llce-can
E: USEC_INITIALIZED=16020353
E: ID_PATH=platform-43ff8000.llce:llce_can0
E: ID_PATH_TAG=platform-43ff8000_llce_llce_can0
"""

LLCE_CAN_DEVICE_CHILD = """
P: /devices/platform/soc/43ff8000.llce/43ff8000.llce:llce_can0/net/llcecan0
L: 0
E: DEVPATH=/devices/platform/soc/43ff8000.llce/43ff8000.llce:llce_can0/net/llcecan0
E: SUBSYSTEM=net
E: INTERFACE=llcecan0
E: IFINDEX=8
E: USEC_INITIALIZED=16326396
E: ID_MM_CANDIDATE=1
E: ID_PATH=platform-43ff8000.llce:llce_can0
E: ID_PATH_TAG=platform-43ff8000_llce_llce_can0
E: ID_NET_DRIVER=llce_can
E: ID_NET_LINK_FILE=/usr/lib/systemd/network/99-default.link
E: ID_NET_NAME=llcecan0
E: SYSTEMD_ALIAS=/sys/subsystem/net/devices/llcecan0
E: TAGS=:systemd:
E: CURRENT_TAGS=:systemd:
"""


class UdevadmDeviceCANTest(unittest.TestCase):
    """
    Tests for UdevadmDevice class
    """
    def __parse_udev_block(self, record):
        line_pattern = re.compile(r"(?P<key>[A-Z]):\s*(?P<value>.*)")
        multi_pattern = re.compile(r"(?P<key>[^=]+)=(?P<value>.*)")

        path = None
        name = None
        element = None
        symlinks = []
        environment = {}
        for line in record.splitlines():
            line_match = line_pattern.match(line)
            if not line_match:
                if environment:
                    # Append to last environment element
                    environment[element] += line
                continue
            key = line_match.group("key")
            value = line_match.group("value")
            if key == "P":
                path = value
            elif key == "N":
                name = value
            elif key == "S":
                symlinks.append(value)
            elif key == "E":
                key_match = multi_pattern.match(value)
                if not key_match:
                    raise Exception(
                        "Device property not supported: %s" % value)
                element = key_match.group("key")
                environment[element] = key_match.group("value")

        # Set default DEVPATH
        environment.setdefault("DEVPATH", path)

        return environment, name, symlinks

    def test_can_device_parent(self):
        environment, name, symlinks = self.__parse_udev_block(
            GENERIC_CAN_DEVICE_PARENT)

        udevadm_dev_can = UdevadmDevice(environment, name, symlinks=symlinks)
        self.assertIsInstance(udevadm_dev_can, UdevadmDevice)
        self.assertEqual(udevadm_dev_can.name, None)
        self.assertEqual(udevadm_dev_can.bus, "platform")
        self.assertEqual(udevadm_dev_can.category, None)
        self.assertEqual(udevadm_dev_can.driver, "flexcan")
        self.assertEqual(udevadm_dev_can.path,
                         "/devices/platform/soc/401b4000.flexcan")
        self.assertEqual(udevadm_dev_can.product_id, None)
        self.assertEqual(udevadm_dev_can.vendor_id, None)
        self.assertEqual(udevadm_dev_can.subproduct_id, None)
        self.assertEqual(udevadm_dev_can.subvendor_id, None)
        self.assertEqual(udevadm_dev_can.product_slug, None)
        self.assertEqual(udevadm_dev_can.vendor_slug, None)
        self.assertEqual(udevadm_dev_can.product, None)
        self.assertEqual(udevadm_dev_can.vendor, None)
        self.assertEqual(udevadm_dev_can.interface, None)
        self.assertEqual(udevadm_dev_can.mac, None)
        self.assertEqual(udevadm_dev_can.symlink_uuid, None)

    def test_can_device_child(self):
        environment, name, symlinks = self.__parse_udev_block(
            GENERIC_CAN_DEVICE_CHILD)

        udevadm_dev_can = UdevadmDevice(environment, name, symlinks=symlinks)
        self.assertIsInstance(udevadm_dev_can, UdevadmDevice)
        self.assertEqual(udevadm_dev_can.name, None)
        self.assertEqual(udevadm_dev_can.bus, "net")
        self.assertEqual(udevadm_dev_can.category, "SOCKETCAN")
        self.assertEqual(udevadm_dev_can.driver, None)
        self.assertEqual(udevadm_dev_can.path,
                         "/devices/platform/soc/401b4000.flexcan")
        self.assertEqual(udevadm_dev_can.product_id, None)
        self.assertEqual(udevadm_dev_can.vendor_id, None)
        self.assertEqual(udevadm_dev_can.subproduct_id, None)
        self.assertEqual(udevadm_dev_can.subvendor_id, None)
        self.assertEqual(udevadm_dev_can.product_slug, None)
        self.assertEqual(udevadm_dev_can.vendor_slug, None)
        self.assertEqual(udevadm_dev_can.product, None)
        self.assertEqual(udevadm_dev_can.vendor, None)
        self.assertEqual(udevadm_dev_can.interface, "can0")
        self.assertEqual(udevadm_dev_can.mac, None)
        self.assertEqual(udevadm_dev_can.symlink_uuid, None)

    def test_can_device_full(self):
        environment, name, symlinks = self.__parse_udev_block(
            GENERIC_CAN_DEVICE_PARENT)

        can_parent = UdevadmDevice(environment, name, symlinks=symlinks)

        environment, name, symlinks = self.__parse_udev_block(
            GENERIC_CAN_DEVICE_CHILD)

        udevadm_dev_can = UdevadmDevice(
            environment, name, stack=[can_parent], symlinks=symlinks)
        self.assertIsInstance(udevadm_dev_can, UdevadmDevice)
        self.assertEqual(udevadm_dev_can.name, None)
        self.assertEqual(udevadm_dev_can.bus, "net")
        self.assertEqual(udevadm_dev_can.category, "SOCKETCAN")
        self.assertEqual(udevadm_dev_can.driver, "flexcan")
        self.assertEqual(udevadm_dev_can.path,
                         "/devices/platform/soc/401b4000.flexcan")
        self.assertEqual(udevadm_dev_can.product_id, None)
        self.assertEqual(udevadm_dev_can.vendor_id, None)
        self.assertEqual(udevadm_dev_can.subproduct_id, None)
        self.assertEqual(udevadm_dev_can.subvendor_id, None)
        self.assertEqual(udevadm_dev_can.product_slug, "flexcan")
        self.assertEqual(udevadm_dev_can.vendor_slug, None)
        self.assertEqual(udevadm_dev_can.product, "flexcan")
        self.assertEqual(udevadm_dev_can.vendor, None)
        self.assertEqual(udevadm_dev_can.interface, "can0")
        self.assertEqual(udevadm_dev_can.mac, None)
        self.assertEqual(udevadm_dev_can.symlink_uuid, None)

    def test_llcecan_device_parent(self):
        environment, name, symlinks = self.__parse_udev_block(
            LLCE_CAN_DEVICE_PARENT)

        udevadm_dev_can = UdevadmDevice(environment, name, symlinks=symlinks)
        self.assertIsInstance(udevadm_dev_can, UdevadmDevice)
        self.assertEqual(udevadm_dev_can.name, None)
        self.assertEqual(udevadm_dev_can.bus, "platform")
        self.assertEqual(udevadm_dev_can.category, None)
        self.assertEqual(udevadm_dev_can.driver, "llce_can")
        self.assertEqual(
            udevadm_dev_can.path,
            "/devices/platform/soc/43ff8000.llce/43ff8000.llce:llce_can0")
        self.assertEqual(udevadm_dev_can.product_id, None)
        self.assertEqual(udevadm_dev_can.vendor_id, None)
        self.assertEqual(udevadm_dev_can.subproduct_id, None)
        self.assertEqual(udevadm_dev_can.subvendor_id, None)
        self.assertEqual(udevadm_dev_can.product_slug, None)
        self.assertEqual(udevadm_dev_can.vendor_slug, None)
        self.assertEqual(udevadm_dev_can.product, None)
        self.assertEqual(udevadm_dev_can.vendor, None)
        self.assertEqual(udevadm_dev_can.interface, None)
        self.assertEqual(udevadm_dev_can.mac, None)
        self.assertEqual(udevadm_dev_can.symlink_uuid, None)

    def test_llcecan_device_child(self):
        environment, name, symlinks = self.__parse_udev_block(
            LLCE_CAN_DEVICE_CHILD)

        udevadm_dev_can = UdevadmDevice(environment, name, symlinks=symlinks)
        self.assertIsInstance(udevadm_dev_can, UdevadmDevice)
        self.assertEqual(udevadm_dev_can.name, None)
        self.assertEqual(udevadm_dev_can.bus, "net")
        self.assertEqual(udevadm_dev_can.category, "SOCKETCAN")
        self.assertEqual(udevadm_dev_can.driver, None)
        self.assertEqual(
            udevadm_dev_can.path,
            "/devices/platform/soc/43ff8000.llce/43ff8000.llce:llce_can0")
        self.assertEqual(udevadm_dev_can.product_id, None)
        self.assertEqual(udevadm_dev_can.vendor_id, None)
        self.assertEqual(udevadm_dev_can.subproduct_id, None)
        self.assertEqual(udevadm_dev_can.subvendor_id, None)
        self.assertEqual(udevadm_dev_can.product_slug, None)
        self.assertEqual(udevadm_dev_can.vendor_slug, None)
        self.assertEqual(udevadm_dev_can.product, None)
        self.assertEqual(udevadm_dev_can.vendor, None)
        self.assertEqual(udevadm_dev_can.interface, "llcecan0")
        self.assertEqual(udevadm_dev_can.mac, None)
        self.assertEqual(udevadm_dev_can.symlink_uuid, None)

    def test_llcecan_device_full(self):
        environment, name, symlinks = self.__parse_udev_block(
            LLCE_CAN_DEVICE_PARENT)

        can_parent = UdevadmDevice(environment, name, symlinks=symlinks)

        environment, name, symlinks = self.__parse_udev_block(
            LLCE_CAN_DEVICE_CHILD)

        udevadm_dev_can = UdevadmDevice(
            environment, name, stack=[can_parent], symlinks=symlinks)
        self.assertIsInstance(udevadm_dev_can, UdevadmDevice)
        self.assertEqual(udevadm_dev_can.name, None)
        self.assertEqual(udevadm_dev_can.bus, "net")
        self.assertEqual(udevadm_dev_can.category, "SOCKETCAN")
        self.assertEqual(udevadm_dev_can.driver, "llce_can")
        self.assertEqual(
            udevadm_dev_can.path,
            "/devices/platform/soc/43ff8000.llce/43ff8000.llce:llce_can0")
        self.assertEqual(udevadm_dev_can.product_id, None)
        self.assertEqual(udevadm_dev_can.vendor_id, None)
        self.assertEqual(udevadm_dev_can.subproduct_id, None)
        self.assertEqual(udevadm_dev_can.subvendor_id, None)
        self.assertEqual(udevadm_dev_can.product_slug, "llce_can0")
        self.assertEqual(udevadm_dev_can.vendor_slug, None)
        self.assertEqual(udevadm_dev_can.product, "llce_can0")
        self.assertEqual(udevadm_dev_can.vendor, None)
        self.assertEqual(udevadm_dev_can.interface, "llcecan0")
        self.assertEqual(udevadm_dev_can.mac, None)
        self.assertEqual(udevadm_dev_can.symlink_uuid, None)


class UdevadmParserCANTest(unittest.TestCase):
    """
    Tests for UdevadmParser class
    """

    def test_can_device_by_udevadm_parser(self):

        log = "\n".join([GENERIC_CAN_DEVICE_PARENT, GENERIC_CAN_DEVICE_CHILD])

        udevadm_devices = UdevadmParser(log).run()
        self.assertEqual(1, len(udevadm_devices))
        udevadm_dev_can = udevadm_devices[0]
        self.assertIsInstance(udevadm_dev_can, UdevadmDevice)
        self.assertEqual(udevadm_dev_can.name, None)
        self.assertEqual(udevadm_dev_can.bus, "net")
        self.assertEqual(udevadm_dev_can.category, "SOCKETCAN")
        self.assertEqual(udevadm_dev_can.driver, "flexcan")
        self.assertEqual(udevadm_dev_can.path,
                         "/devices/platform/soc/401b4000.flexcan")
        self.assertEqual(udevadm_dev_can.product_id, None)
        self.assertEqual(udevadm_dev_can.vendor_id, None)
        self.assertEqual(udevadm_dev_can.subproduct_id, None)
        self.assertEqual(udevadm_dev_can.subvendor_id, None)
        self.assertEqual(udevadm_dev_can.product_slug, "flexcan")
        self.assertEqual(udevadm_dev_can.vendor_slug, None)
        self.assertEqual(udevadm_dev_can.product, "flexcan")
        self.assertEqual(udevadm_dev_can.vendor, None)
        self.assertEqual(udevadm_dev_can.interface, "can0")
        self.assertEqual(udevadm_dev_can.mac, None)
        self.assertEqual(udevadm_dev_can.symlink_uuid, None)

    def test_llcecan_device_by_udevadm_parser(self):
        log = "\n".join([LLCE_CAN_DEVICE_PARENT, LLCE_CAN_DEVICE_CHILD])

        udevadm_devices = UdevadmParser(log).run()
        self.assertEqual(1, len(udevadm_devices))
        udevadm_dev_can = udevadm_devices[0]
        self.assertIsInstance(udevadm_dev_can, UdevadmDevice)
        self.assertEqual(udevadm_dev_can.name, None)
        self.assertEqual(udevadm_dev_can.bus, "net")
        self.assertEqual(udevadm_dev_can.category, "SOCKETCAN")
        self.assertEqual(udevadm_dev_can.driver, "llce_can")
        self.assertEqual(
            udevadm_dev_can.path,
            "/devices/platform/soc/43ff8000.llce/43ff8000.llce:llce_can0")
        self.assertEqual(udevadm_dev_can.product_id, None)
        self.assertEqual(udevadm_dev_can.vendor_id, None)
        self.assertEqual(udevadm_dev_can.subproduct_id, None)
        self.assertEqual(udevadm_dev_can.subvendor_id, None)
        self.assertEqual(udevadm_dev_can.product_slug, "llce_can0")
        self.assertEqual(udevadm_dev_can.vendor_slug, None)
        self.assertEqual(udevadm_dev_can.product, "llce_can0")
        self.assertEqual(udevadm_dev_can.vendor, None)
        self.assertEqual(udevadm_dev_can.interface, "llcecan0")
        self.assertEqual(udevadm_dev_can.mac, None)
        self.assertEqual(udevadm_dev_can.symlink_uuid, None)
