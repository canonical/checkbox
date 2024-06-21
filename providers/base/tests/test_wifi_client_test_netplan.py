#!/usr/bin/env python3
# encoding: utf-8
# Copyright 2024 Canonical Ltd.
# Written by:
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
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

import textwrap
from unittest import TestCase
from unittest.mock import patch, MagicMock


from wifi_client_test_netplan import generate_test_config, parse_args


class WifiClientTestNetplanTests(TestCase):
    def test_open_ap_with_dhcp(self):
        expected_output = textwrap.dedent(
            """
            # This is the network config written by checkbox
            network:
              version: 2
              wifis:
                eth0:
                  access-points:
                    my_ap: {}
                  dhcp4: true
                  nameservers: {}
            """
        )

        result = generate_test_config("eth0", "my_ap", None, "", True, False)
        self.assertEqual(result.strip(), expected_output.strip())

    def test_private_ap_with_dhcp(self):
        expected_output = textwrap.dedent(
            """
            # This is the network config written by checkbox
            network:
              version: 2
              wifis:
                eth0:
                  access-points:
                    my_ap:
                      auth:
                        key-management: psk
                        password: s3cr3t
                  dhcp4: true
                  nameservers: {}
            """
        )
        result = generate_test_config(
            "eth0", "my_ap", "s3cr3t", "", True, False
        )
        self.assertEqual(result.strip(), expected_output.strip())

    def test_private_ap_with_wpa3(self):
        expected_output = textwrap.dedent(
            """
            # This is the network config written by checkbox
            network:
              version: 2
              wifis:
                eth0:
                  access-points:
                    my_ap_wpa3:
                      auth:
                        key-management: sae
                        password: s3cr3t
                  dhcp4: false
                  nameservers: {}
            """
        )
        result = generate_test_config(
            "eth0", "my_ap_wpa3", "s3cr3t", "", False, True
        )
        self.assertEqual(result.strip(), expected_output.strip())

    def test_static_ip_no_dhcp(self):
        expected_output = textwrap.dedent(
            """
            # This is the network config written by checkbox
            network:
              version: 2
              wifis:
                eth0:
                  access-points:
                    my_ap:
                      auth:
                        key-management: psk
                        password: s3cr3t
                  addresses:
                  - 192.168.1.1
                  dhcp4: false
                  nameservers: {}
            """
        )
        result = generate_test_config(
            "eth0", "my_ap", "s3cr3t", "192.168.1.1", False, False
        )
        self.assertEqual(result.strip(), expected_output.strip())

    def test_no_ssid_fails(self):
        with self.assertRaises(SystemExit):
            generate_test_config(
                "eth0", "", "s3cr3t", "192.168.1.1", False, False
            )

    def test_parser_psk_and_wpa3(self):
        with patch(
            "sys.argv",
            [
                "script.py",
                "-i",
                "eth0",
                "-s",
                "SSID",
                "-k",
                "pswd",
                "-d",
                "--wpa3",
            ],
        ):
            args = parse_args()
            self.assertEqual(args.interface, "eth0")
            self.assertEqual(args.psk, "pswd")
            self.assertTrue(args.wpa3)

    def test_parser_custom_interface_with_address(self):
        with patch(
            "sys.argv",
            ["script.py", "-s", "SSID", "-a", "192.168.1.1/24", "--wpa3"],
        ):
            args = parse_args()
            self.assertEqual(args.address, "192.168.1.1/24")
            self.assertTrue(args.wpa3)
            self.assertFalse(args.dhcp)

    @patch(
        "sys.argv", ["script.py", "-s", "SSID", "-a", "192.168.1.1/24", "-d"]
    )
    def test_parser_mutually_exclusive_fail(self):
        with patch(
            "sys.argv",
            ["script.py", "-s", "SSID", "-a", "192.168.1.1/24", "-d"],
        ):
            with self.assertRaises(SystemExit):
                parse_args()
