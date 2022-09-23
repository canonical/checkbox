#!/usr/bin/env python3
# encoding: utf-8
# Copyright 2015 Canonical Ltd.
# Written by:
#   Shawn Wang <shawn.wang@canonical.com>
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Jonathan Cave <jonathan.cave@canonical.com>
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

import io
import unittest
from unittest import mock

import dkms_info


class SystemInfoTests(unittest.TestCase):

    """Tests for System Information Parsing and Collection."""

    _proc_modules = """\
xt_REDIRECT 16384 3 - Live 0x0000000000000000
nf_nat_redirect 16384 1 xt_REDIRECT, Live 0x0000000000000000
xt_hl 16384 3 - Live 0x0000000000000000
hid_generic 16384 0 - Live 0x0000000000000000
usbhid 53248 0 - Live 0x0000000000000000
hid 110592 2 hid_generic,usbhid, Live 0x0000000000000000
overlay 45056 1 - Live 0x0000000000000000
"""
    _modalias = """\
usb:v1D6Bp0003d0319dc09dsc00dp03ic09isc00ip00in00
"""

    def setUp(self):
        """Common setup code."""
        dkms_info.get_system_module_list.cache_clear()
        dkms_info.get_system_modaliases.cache_clear()

    @mock.patch('io.open', mock.mock_open(read_data=_proc_modules))
    def test_get_module_list__calls_and_parses_lsmod(self):
        """Ensure that get_module_list() parses lsmod output."""
        # NOTE: Return value was loaded from my system running kernel 4.0.
        # The first few and last rows to be precise.
        modules = dkms_info.get_system_module_list()
        self.assertEqual(modules, [
            'xt_REDIRECT', 'nf_nat_redirect', 'xt_hl', 'hid_generic',
            'usbhid', 'hid', 'overlay'])

    @mock.patch('io.open', mock.mock_open(read_data=_proc_modules))
    def test_get_module_list_is_cached(self):
        """Ensure that get_module_list() cache works."""
        modules1 = dkms_info.get_system_module_list()
        modules2 = dkms_info.get_system_module_list()
        self.assertIn('xt_REDIRECT', modules1)
        self.assertIn('overlay', modules2)
        self.assertEqual(modules1, modules2)

    @mock.patch('os.walk')
    @mock.patch('io.open', mock.mock_open(read_data=_modalias))
    def test_get_system_modalias(self, mock_os_walk):
        """test_get_system_modalias."""
        mock_os_walk.return_value = [
            ("/sys/devices/pci0000:00/0000:00:14.0/usb2/2-0:1.0/modalias",
             ["driver", "subsystem"],
             ["modalias", "uevent"]),
        ]

        """fetch hw_modaliases from machine and check modalis types."""
        modaliases = dkms_info.get_system_modaliases()
        self.assertEqual(len(modaliases), 1)
        self.assertIn("usb", modaliases)

    @mock.patch('os.uname')
    @mock.patch('os.walk')
    def test_get_installed_dkms_modules(self, mock_os_walk, mock_os_uname):
        """test_get_installed_dkms_modules."""
        mock_os_walk.return_value = [
            ("/var/lib/dkms/hello/0.1",
             ["3.19.0-15-generic", "build", "source"],
             []),
        ]
        o = mock.Mock()
        o.release = "3.19.0-15-generic"
        mock_os_uname.return_value = o
        self.assertEqual([['hello', '0.1']],
                         dkms_info.get_installed_dkms_modules())

    @mock.patch('dkms_info.get_system_modaliases')
    def test_match_patterns(self, mock_get_system_modaliases):
        """Test of match_patterns."""
        mock_get_system_modaliases.return_value = {
            "pci": ["v0000168Cd00000036sv0000103Csd0000217Fbc02sc80i00",
                    "v00008086d00008C26sv0000103Csd000022D9bc0Csc03i20"],
            "usb": ["v8087p8000d0005dc09dsc00dp01ic09isc00ip00in00",
                    "v1D6Bp0002d0319dc09dsc00dp00ic09isc00ip00in00"],
        }
        pkg_modalieses = ["pci:v00008086d00008C26sv*sd*bc*sc*i*",
                          "usb:v07B4p010Ad0102dc*dsc*dp*ic*isc*ip*in*",
                          "oemalias:test"]
        matched_modalieses = dkms_info.match_patterns(tuple(pkg_modalieses))
        # match_patterns
        self.assertIn("pci:v00008086d00008C26sv*sd*bc*sc*i*",
                      matched_modalieses)
        self.assertIn("oemalias:test",
                      matched_modalieses)
        self.assertNotIn("usb:v07B4p010Ad0102dc*dsc*dp*ic*isc*ip*in*",
                         matched_modalieses)


class DebianPackageHandlerTest(unittest.TestCase):

    """Test of DebianPackageHandler."""

    _var_lib_dpkg_status = """\
Package: foo
Status: install ok installed
Modaliases: hwe(pci:v000099DDd00000036sv*sd*bc*sc*i*)

Package: foo1
Status: install ok installed
Modaliases: hwe(pci:v0000AADDd00000036sv*sd*bc*sc*i*)

Package: foo2
Status: install ok installed

Package: foo3
Status: install ok installed

Package: bar
Status: install ok installed

"""

    @mock.patch('io.open', mock.mock_open(read_data=_var_lib_dpkg_status))
    @mock.patch('dkms_info.get_system_modaliases')
    def test_get_pkgs(self, mock_get_system_modaliases):
        """Test of test_get_pkgs."""
        mock_get_system_modaliases.return_value = {
            "pci": ["v0000168Cd00000036sv0000103Csd0000217Fbc02sc80i00",
                    "v00008086d00008C26sv0000103Csd000022D9bc0Csc03i20"],
            "usb": ["v8087p8000d0005dc09dsc00dp01ic09isc00ip00in00",
                    "v1D6Bp0002d0319dc09dsc00dp00ic09isc00ip00in00"],
        }

        self.pkg_handler = dkms_info.DebianPackageHandler(
            file_object=io.StringIO(self._var_lib_dpkg_status))
        self.assertEqual(len(self.pkg_handler.pkgs), 2)
