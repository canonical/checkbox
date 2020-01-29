#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2019-2020 Canonical Ltd.
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

import os
import tempfile
import unittest

from checkbox_support.parsers.netplan import Netplan
from checkbox_support.parsers.udevadm import UdevadmParser, UdevResult

import net_if_management

# create a session dir for logging to be written to
os.environ['PLAINBOX_SESSION_SHARE'] = tempfile.mkdtemp(prefix='cbox-test')


class NetIfMngrTest():

    has_netplan = True
    has_nm = True

    @staticmethod
    def get_text(filename):
        full_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'test_net_if_management_data',
            filename)
        with open(full_path, 'rt', encoding='UTF-8') as stream:
            return stream.read()

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
    netplan_yaml = NetIfMngrTest.get_text('CARA_T_netplan.yaml')

    # capture output of `sudo nmcli -t -f DEVICE,STATE d`
    # or None if no NM available
    nm_device_state = NetIfMngrTest.get_text('CARA_T_nmcli.txt')

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
    nm_device_state = NetIfMngrTest.get_text('XENIAL_DESKTOP_nmcli.txt')

    def test(self):
        res = self.get_results()
        self.assertEqual(res['eth0'].value, 'NetworkManager')
        self.assertEqual(res['wlan0'].value, 'NetworkManager')


class Test_CASCADE_500(unittest.TestCase, NetIfMngrTest):
    # the interfaces we interested in (as provided by the udev parser)
    interfaces = ['eth0', 'wlan0']

    # the combined netplan configuration or `None` if netplan not installed
    netplan_yaml = NetIfMngrTest.get_text('CASCADE_500_netplan.yaml')

    # capture output of `sudo nmcli -t -f DEVICE,STATE d`
    # or None if NM is not installed
    nm_device_state = NetIfMngrTest.get_text('CASCADE_500_nmcli.txt')

    def test(self):
        res = self.get_results()
        self.assertEqual(res['eth0'].value, 'NetworkManager')
        self.assertEqual(res['wlan0'].value, 'NetworkManager')


class Test_RPI2_UC16_CCONF(unittest.TestCase, NetIfMngrTest):
    # the interfaces we interested in (as provided by the udev parser)
    interfaces = ['eth0']

    # the combined netplan configuration or `None` if netplan not installed
    netplan_yaml = NetIfMngrTest.get_text('RPI2_UC16_CCONF_netplan.yaml')

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
    netplan_yaml = NetIfMngrTest.get_text('RPI3B_UC16_CLOUDINIT_netplan.yaml')

    # capture output of `sudo nmcli -t -f DEVICE,STATE d`
    # or None if NM is not installed
    nm_device_state = None

    def test(self):
        res = self.get_results()
        self.assertEqual(res['eth0'].value, 'networkd')
        self.assertEqual(res['wlan0'].value, 'networkd')
