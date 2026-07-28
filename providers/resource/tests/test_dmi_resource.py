#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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

from unittest import TestCase

import contextlib
import io

from checkbox_ng.support.lib.dmi import DmiDevice

import dmi_resource


class TestDmiResource(TestCase):
    def test_sane_product_portable(self):
        products = [
            "Notebook",
            "Laptop",
            "Portable",
            "Convertible",
            "Tablet",
            "Detachable",
        ]
        category = set(map(dmi_resource.sane_product, products))
        self.assertEqual(category, {"portable"})

    def test_sane_product_non_portable(self):
        products = [
            "Desktop",
            "Low Profile Desktop",
            "Tower",
            "Mini-Tower",
            "Space Saving",
            "Mini PC",
            "Rack Mount Chassis",
        ]
        category = set(map(dmi_resource.sane_product, products))
        self.assertEqual(category, {"non-portable"})

    def test_sane_product_unknown(self):
        products = ["strange-iot-product"]
        category = set(map(dmi_resource.sane_product, products))
        self.assertEqual(category, {"unknown"})

    def test_display_type_integrated(self):
        products = [
            "Notebook",
            "Laptop",
            "Portable",
            "Convertible",
            "Tablet",
            "Detachable",
            "All-In-One",
            "All In One",
            "AIO",
        ]
        category = set(map(dmi_resource.display_type, products))
        self.assertEqual(category, {"integrated"})

    def test_display_type_external(self):
        products = [
            "Desktop",
            "Low Profile Desktop",
            "Tower",
            "Mini-Tower",
            "Space Saving",
            "Mini PC",
        ]
        category = set(map(dmi_resource.display_type, products))
        self.assertEqual(category, {"external"})

    def test_display_type_unknown(self):
        products = ["strange-iot-product"]
        category = set(map(dmi_resource.display_type, products))
        self.assertEqual(category, {"external"})


class TestDmiResultChassis(TestCase):
    def output_for(self, device):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            dmi_resource.DmiResult().addDmiDevice(device)
        return stream.getvalue()

    def test_chassis_device_outputs_mapped_chassis_type(self):
        """Test that a CHASSIS device outputs its mapped chassis type."""
        device = DmiDevice({"chassis_type": "10"}, "CHASSIS")
        self.assertIn("chassis: Notebook", self.output_for(device))

    def test_chassis_field_only_outputs_for_chassis_devices(self):
        """Test that the chassis field is only included for CHASSIS devices."""
        device = DmiDevice({"system_name": "20AMOS3"}, "SYSTEM")
        self.assertNotIn("chassis:", self.output_for(device))
