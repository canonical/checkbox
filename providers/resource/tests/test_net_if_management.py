#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2019 Canonical Ltd.
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
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
# from unittest import mock

from checkbox_support.parsers.netplan import Netplan
from checkbox_support.parsers.udevadm import UdevadmParser, UdevResult

import net_if_management


class NetIfMngrTest():

    has_netplan = True
    has_nm = True

    def get_results(self):
        if self.netplan_yaml is None:
            self.has_netplan = False
        if self.nm_device_state is None:
            self.has_nm = False
        return net_if_management.identify_managers(self.interfaces,
                                                   self.has_netplan,
                                                   self.netplan_yaml,
                                                   self.has_nm,
                                                   self.nm_device_state)


class Test_CARA_T(unittest.TestCase, NetIfMngrTest):
    # the interfaces we interested in (as provided by the udev parser)
    interfaces = ['eth0', 'eth1', 'wlan0']

    # the combined netplan configuration
    netplan_yaml = """network:
  renderer: NetworkManager
"""
    # capture output of `sudo nmcli -t -f DEVICE,STATE d`
    # or None if no NM available
    nm_device_state = """eth0:connected
eth1:unavailable
wlan0:disconnected
lo:unmanaged
"""

    def test(self):
        res = self.get_results()
        self.assertEqual(res['eth0'].value, 'NetworkManager')
        self.assertEqual(res['eth1'].value, 'NetworkManager')
        self.assertEqual(res['wlan0'].value, 'NetworkManager')


class Test_XENIAL_DESKTOP(unittest.TestCase, NetIfMngrTest):
    # the interfaces we interested in (as provided by the udev parser)
    interfaces = ['eth0', 'wlan0']

    # the combined netplan configuration or `None` if netplan not installed
    netplan_yaml = None

    # capture output of `sudo nmcli -t -f DEVICE,STATE d`
    # or None if NM is not installed
    nm_device_state = """eth0:connected
wlan0:disconnected
lo:unmanaged
"""

    def test(self):
        res = self.get_results()
        self.assertEqual(res['eth0'].value, 'NetworkManager')
        self.assertEqual(res['wlan0'].value, 'NetworkManager')


class Test_CASCADE_500(unittest.TestCase, NetIfMngrTest):
    # the interfaces we interested in (as provided by the udev parser)
    interfaces = ['eth0', 'wlan0']

    # the combined netplan configuration or `None` if netplan not installed
    netplan_yaml = """network:
  renderer: NetworkManager
"""

    # capture output of `sudo nmcli -t -f DEVICE,STATE d`
    # or None if NM is not installed
    nm_device_state = """eth0:connected
wlan0:connected
ttyACM1:unavailable
lo:unmanaged
p2p0:unmanaged
"""

    def test(self):
        res = self.get_results()
        self.assertEqual(res['eth0'].value, 'NetworkManager')
        self.assertEqual(res['wlan0'].value, 'NetworkManager')


class Test_RPI2_UC16_CCONF(unittest.TestCase, NetIfMngrTest):
    # the interfaces we interested in (as provided by the udev parser)
    interfaces = ['eth0']

    # the combined netplan configuration or `None` if netplan not installed
    netplan_yaml = """# This is the network config written by 'console_conf'
network:
  ethernets:
    eth0:
      addresses: []
      dhcp4: true
  version: 2
"""

    # capture output of `sudo nmcli -t -f DEVICE,STATE d`
    # or None if NM is not installed
    nm_device_state = None

    def test(self):
        res = self.get_results()
        self.assertEqual(res['eth0'].value, 'networkd')


class Test_RPI3B_UC16_CLOUDINIT(unittest.TestCase, NetIfMngrTest):
    # the interfaces we interested in (as provided by the udev parser)
    interfaces = ['eth0', 'wlan0']

    # the combined netplan configuration or `None` if netplan not installed
    netplan_yaml = """# This file is generated from information provided by
# the datasource.  Changes to it will not persist across an instance.
# To disable cloud-init's network configuration capabilities, write a file
# /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg with the following:
# network: {config: disabled}
network:
    version: 2
    ethernets:
        eth0:
            dhcp4: true
            match:
                macaddress: 00:00:00:00:00:00
            set-name: eth0
"""

    # capture output of `sudo nmcli -t -f DEVICE,STATE d`
    # or None if NM is not installed
    nm_device_state = None

    def test(self):
        res = self.get_results()
        self.assertEqual(res['eth0'].value, 'networkd')
        self.assertEqual(res['wlan0'].value, 'networkd')
