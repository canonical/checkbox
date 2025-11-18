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

import unittest
from unittest import TestCase
from unittest.mock import MagicMock

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
            "All-in-One",
            "aio",
            "Mini PC",
        ]
        category = set(map(dmi_resource.sane_product, products))
        self.assertEqual(category, {"non-portable"})

    def test_sane_product_unknown(self):
        products = ["strange-iot-product"]
        category = set(map(dmi_resource.sane_product, products))
        self.assertEqual(category, {"unknown"})
