#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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
import io
import unittest
from contextlib import redirect_stdout
from unittest import TestCase
from unittest.mock import MagicMock

from checkbox_support.parsers.udevadm import UdevadmParser

import udev_resource

# Real udevadm export for a rndis_host usb_interface device. Its
# INTERFACE value (224/1/3) contains slashes and used to break
# template expansion downstream. See checkbox issue #2563.
RNDIS_INTERFACE_DEVICE = """\
P: /devices/pci0000:00/0000:00:00.0/0000:01:00.0/usb1/1-2/1-2.6/1-2.6.1/1-2.6.1:1.0
M: 1-2.6.1:1.0
R: 0
U: usb
T: usb_interface
V: rndis_host
E: DEVPATH=/devices/pci0000:00/0000:00:00.0/0000:01:00.0/usb1/1-2/1-2.6/1-2.6.1/1-2.6.1:1.0
E: SUBSYSTEM=usb
E: DEVTYPE=usb_interface
E: DRIVER=rndis_host
E: PRODUCT=b1f/3ee/612
E: TYPE=0/0/0
E: INTERFACE=224/1/3
E: MODALIAS=usb:v0B1Fp03EEd0612dc00dsc00dp00icE0isc01ip03in00
E: USEC_INITIALIZED=2935531
E: ID_VENDOR_FROM_DATABASE=Insyde Software Corp.
E: ID_PATH_WITH_USB_REVISION=pci-0000:01:00.0-usbv2-0:2.6.1:1.0
E: ID_PATH=pci-0000:01:00.0-usb-0:2.6.1:1.0
E: ID_PATH_TAG=pci-0000_01_00_0-usb-0_2_6_1_1_0

"""


def make_device(**attrs):
    """Return a MagicMock exposing only `udev_resource.attributes`.

    Every attribute defaults to None unless overridden in `attrs`, which
    mirrors how `UdevadmDevice` behaves for absent properties.
    """
    device = MagicMock(spec=udev_resource.attributes)
    for attribute in udev_resource.attributes:
        setattr(device, attribute, attrs.get(attribute))
    return device


class TestDumpUdevDb(TestCase):
    def test_skips_interface_names_with_slash(self):
        # interface names like "224/1/3" must not be dumped because they break
        # template expansion.
        udev = MagicMock()
        udev.run.return_value = [
            make_device(path="/dev/foo", interface="224/1/3")
        ]

        buf = io.StringIO()
        with redirect_stdout(buf):
            udev_resource.dump_udev_db(udev)

        self.assertEqual(buf.getvalue(), "")

    def test_keeps_interface_names_without_slash(self):
        udev = MagicMock()
        udev.run.return_value = [
            make_device(path="/dev/foo", interface="usb0")
        ]

        buf = io.StringIO()
        with redirect_stdout(buf):
            udev_resource.dump_udev_db(udev)

        output = buf.getvalue()
        self.assertIn("path: /dev/foo", output)
        self.assertIn("interface: usb0", output)

    def test_keeps_devices_without_interface(self):
        udev = MagicMock()
        udev.run.return_value = [make_device(path="/dev/foo")]

        buf = io.StringIO()
        with redirect_stdout(buf):
            udev_resource.dump_udev_db(udev)

        self.assertIn("path: /dev/foo", buf.getvalue())

    def test_real_udevadm_output_with_slash_interface_is_skipped(self):
        udev = UdevadmParser(
            RNDIS_INTERFACE_DEVICE, lsblk={"blockdevices": []}
        )

        buf = io.StringIO()
        with redirect_stdout(buf):
            udev_resource.dump_udev_db(udev)

        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
