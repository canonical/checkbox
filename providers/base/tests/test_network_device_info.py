#!/usr/bin/env python3
# Copyright 2020 Canonical Ltd.
# Written by:
#   Dio He <dio.he@canonical.com>
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
from unittest.mock import Mock, patch

from network_device_info import Utils

class GetIpv4AddressTests(unittest.TestCase):
    # There are 2 output we could get from fcntl.ioctl():
    # 1. No WiFi connected 
    #    (It pulls out bytes data directly from kernel, so if the given SIOCGIFADDR doesn't exist, it raise a OSError)
    #    "None"

    # 2. Connected with WiFi
    #    It will pulls out a 256 bytes data into buffer, then we get to parse the IP address
    #    "192.168.68.101"
    def test_get_ipv4_address_without_connection(self):
        test_input = b""
        mock_ioctl = Mock(return_value=test_input)
        with patch("fcntl.ioctl", mock_ioctl):
            interface = "wlo1"
            addr = Utils.get_ipv4_address(interface)
            self.assertEqual(addr, "***NOT CONFIGURED***")

    def test_get_ipv4_address_with_connection(self):
        test_input = (b'wlo1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x02\x00\x00\x00\xc0\xa8De\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        # test_input = b"I'm fake!!!"
        mock_inet_ntoa = Mock(return_value=test_input)
        with patch("fcntl.ioctl", mock_inet_ntoa):
            interface = "wlo1"
            addr = Utils.get_ipv4_address(interface)
            self.assertEqual(addr, "192.168.68.101")

class GetIpv6AddressTests(unittest.TestCase):
    # There are 3 output we could get, but only 2 cases will happen due to the way we command it
    # 1. No WiFi connected 
    #    ""

    # 2. Connected with WiFi
    #    "2: wlo1    inet6 fe80::d9eb:3f93:c7b2:86ba/64 scope link noprefixroute \       valid_lft forever preferred_lft forever"

    # 3. Connected with WiFi, but we ask the wrong interface name (This would not happen in our case, because the name is given by NetworkManager)
    #    "Device "wlan0" does not exist."
    def test_get_ipv6_address_without_connection(self):
        test_input = ""
        mock_check_output = Mock(return_value=test_input)
        with patch("network_device_info.check_output", mock_check_output):
            interface = "wlo1"
            addr = Utils.get_ipv6_address(interface)
            self.assertEqual(addr, "***NOT CONFIGURED***")

    def test_get_ipv6_address_with_connection(self):
        test_input = "2: wlo1    inet6 fe80::d9eb:3f93:c7b2:86ba/64 scope link noprefixroute \       valid_lft forever preferred_lft forever"
        mock_check_output = Mock(return_value=test_input)
        with patch("network_device_info.check_output", mock_check_output): # somehow it don't regonize check_output() if I don't put subprocess in front
            interface = "wlo1"
            addr = Utils.get_ipv6_address(interface)
            self.assertEqual(addr, "fe80::d9eb:3f93:c7b2:86ba/64")

if __name__ == '__main__':
    unittest.main()
