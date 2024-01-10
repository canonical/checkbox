#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# Written by:
#   Nancy Chen <nancy.chen@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import unittest
import os
from boot_mode_test_snappy import get_bootloader, get_uboot_kernel


class TestBootModeTestSnappy(unittest.TestCase):
    def test_get_bootloader(self):
        """Test for get_bootloader function"""
        kdrp_kdrp_k4500_gadget_yaml = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "test_data/kdrp-kdrp-k4500-gadget.yaml",
        )
        self.assertEqual("u-boot", get_bootloader(kdrp_kdrp_k4500_gadget_yaml))

    def test_get_uboot_kernel(self):
        """
        Test if system-backup interface is included in kernel.img file path
        https://snapcraft.io/docs/the-system-backup-interface
        """
        self.assertIn(
            "/var/lib/snapd/hostfs/boot/uboot/", get_uboot_kernel("kernel")
        )
