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
import os
import unittest
from contextlib import redirect_stdout
from unittest import TestCase
from unittest.mock import MagicMock, patch

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


class TestFilterIgnoreTest(TestCase):
    def test_retains_devices_without_mutating_parser_objects(self):
        devices = [
            make_device(name="sda", category="DISK"),
            make_device(name="eth0", category="NETWORK"),
        ]
        policy = MagicMock()
        policy.fields.side_effect = [{"ignore_test": True}, {}]

        result = udev_resource.filter_ignore_test(iter(devices), policy)

        self.assertIsInstance(result, list)
        self.assertEqual(
            [record["name"] for record in result], ["sda", "eth0"]
        )
        self.assertEqual(
            [record["category"] for record in result], ["DISK", "NETWORK"]
        )
        self.assertTrue(result[0]["ignore_test"])
        self.assertNotIn("ignore_test", result[1])
        self.assertEqual(policy.fields.call_count, 2)
        for device in devices:
            self.assertFalse(hasattr(device, "ignore_test"))

    def test_all_output_paths_use_enrichment_and_keep_display_format(self):
        device = make_device(
            name="eth0", category="NETWORK", vendor="Vendor", product="NIC"
        )
        udev = MagicMock()
        udev.run.return_value = [device]
        for output, args, expected in (
            (udev_resource.dump_udev_db, (udev,), "ignore_test: True\n"),
            (
                udev_resource.filter_by_categories,
                (udev, ("NETWORK",)),
                "ignore_test: True\n",
            ),
            (
                udev_resource.display_by_categories,
                (udev, ("NETWORK",)),
                "NETWORK (1):\n - Vendor NIC [0000:0000]\n\n",
            ),
        ):
            with self.subTest(output=output.__name__):
                with patch("udev_resource.DeviceTestPolicy") as policy:
                    policy.return_value.fields.return_value = {
                        "ignore_test": True
                    }
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        output(*args)
                    policy.return_value.fields.assert_called_once_with(device)
                    self.assertIn(expected, buf.getvalue())


UFS_HOST = "/devices/platform/soc@0/1d84000.ufs/host0/target0:0:0"


class TestStorageTestPolicy(TestCase):
    def setUp(self):
        env_patch = patch.dict(
            os.environ, {"CHECKBOX_STORAGE_TEST_EXCLUDE": ""}
        )
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def disk(self, name, lun):
        return make_device(
            name=name,
            category="DISK",
            path=f"{UFS_HOST}/0:0:0:{lun}",
            product="KM2L9001CM-B518",
        )

    def policy(self, selectors):
        os.environ["CHECKBOX_STORAGE_TEST_EXCLUDE"] = selectors
        return udev_resource.StorageTestPolicy()

    def test_path_selectors_match_exactly(self):
        policy = self.policy(
            f" path:{UFS_HOST}/0:0:0:6 | path:{UFS_HOST}/0:0:0:7 "
        )
        fields = policy.fields(self.disk("sdg", 6))
        self.assertTrue(fields["ignore_test"])
        self.assertIn(
            "CHECKBOX_STORAGE_TEST_EXCLUDE", fields["ignore_test_reason"]
        )
        self.assertTrue(policy.fields(self.disk("sdh", 7))["ignore_test"])
        sda = policy.fields(self.disk("sda", 0))
        self.assertEqual(sda, {"ignore_test": False})

    def test_name_selector_is_exact(self):
        policy = self.policy("name:sda")
        self.assertTrue(policy.fields(self.disk("sda", 0))["ignore_test"])
        self.assertFalse(policy.fields(self.disk("sdaa", 1))["ignore_test"])

    def test_any_device_property_can_be_used(self):
        policy = self.policy("product:KM2L9001CM-B518")
        self.assertTrue(policy.fields(self.disk("sdb", 1))["ignore_test"])

    def test_empty_configuration_marks_storage_eligible(self):
        fields = self.policy("").fields(self.disk("sdg", 6))
        self.assertEqual(fields, {"ignore_test": False})

    def test_partitions_are_not_covered(self):
        partition = make_device(
            name="sdg1",
            category="PARTITION",
            path=f"{UFS_HOST}/0:0:0:6/block/sdg/sdg1",
        )
        self.assertEqual(self.policy("name:sdg1").fields(partition), {})

    def test_invalid_configuration_is_rejected(self):
        for selector in ("sdg", "name:", "ufs-lun:6", "name:sda|/dev/sdb"):
            with self.subTest(selector=selector):
                with self.assertRaises(ValueError):
                    self.policy(selector)

    def test_both_resource_output_modes_preserve_excluded_disk(self):
        os.environ["CHECKBOX_STORAGE_TEST_EXCLUDE"] = "name:sdg"
        udev = MagicMock()
        udev.run.return_value = [self.disk("sdg", 6)]
        for dump, args in (
            (udev_resource.dump_udev_db, (udev,)),
            (udev_resource.filter_by_categories, (udev, ("DISK",))),
        ):
            with self.subTest(dump=dump.__name__):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    dump(*args)
                self.assertIn("name: sdg\n", buf.getvalue())
                self.assertIn("category: DISK\n", buf.getvalue())
                self.assertIn("ignore_test: True\n", buf.getvalue())

    def test_device_policy_dispatches_by_device_type(self):
        class NetworkTestPolicy(udev_resource.IgnoreTestPolicy):
            env_var = "CHECKBOX_NETWORK_TEST_EXCLUDE"

            def applies_to(self, device):
                return device.category == "NETWORK"

        os.environ["CHECKBOX_NETWORK_TEST_EXCLUDE"] = "interface:eth0"
        self.addCleanup(os.environ.pop, "CHECKBOX_NETWORK_TEST_EXCLUDE")
        with patch.object(
            udev_resource.DeviceTestPolicy,
            "policy_classes",
            (udev_resource.StorageTestPolicy, NetworkTestPolicy),
        ):
            policy = udev_resource.DeviceTestPolicy()
        eth0 = policy.fields(make_device(interface="eth0", category="NETWORK"))
        self.assertTrue(eth0["ignore_test"])
        self.assertIn(
            "CHECKBOX_NETWORK_TEST_EXCLUDE", eth0["ignore_test_reason"]
        )
        self.assertFalse(policy.fields(self.disk("sda", 0))["ignore_test"])
        self.assertEqual(
            policy.fields(make_device(name="hci0", category="BLUETOOTH")), {}
        )

    def test_non_storage_records_are_unchanged(self):
        fields = self.policy("name:eth0").fields(
            make_device(name="eth0", category="NETWORK")
        )
        self.assertEqual(fields, {})


if __name__ == "__main__":
    unittest.main()
