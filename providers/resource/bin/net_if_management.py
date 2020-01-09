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

from enum import Enum
import os
from shutil import which
import subprocess as sp
import sys

from checkbox_support.parsers.netplan import Netplan
from checkbox_support.parsers.udevadm import UdevadmParser, UdevResult


def log(msg):
    file = os.path.expandvars('$PLAINBOX_SESSION_SHARE/net_if_management.log')
    with open(file, 'a') as f:
        f.write(msg + '\n')


class UdevInterfaceLister(UdevResult):

    def __init__(self, categories):
        self.categories = categories
        self.names = []
        cmd = 'udevadm info --export-db'
        output = sp.check_output(cmd, shell=True).decode(sys.stdout.encoding)
        udev = UdevadmParser(output)
        udev.run(self)

    def addDevice(self, device):
        c = getattr(device, "category", None)
        if c in self.categories:
            p = getattr(device, "interface", None)
            if p is not None:
                self.names.append(p)


def is_nm_available():
    return which('nmcli') is not None


def is_netplan_available():
    return which('netplan') is not None


class NmInterfaceState():

    def __init__(self):
        self.devices = {}

    def parse(self, data=None):
        if data is None:
            cmd = 'nmcli -t -f DEVICE,STATE d'
            data = sp.check_output(cmd, shell=True).decode(sys.stdout.encoding)
        for line in data.splitlines():
            dev, state = line.strip().split(':')
            self.devices[dev] = state


class States(Enum):
    unspecified = 'unspecified'
    error = 'error'
    networkd = 'networkd'
    nm = 'NetworkManager'


def identify_managers(interfaces=None,
                      has_netplan=True, netplan_yaml=None,
                      has_nm=True, nm_device_state=None):
    if interfaces is None:
        interfaces = UdevInterfaceLister(['NETWORK', 'WIRELESS']).names

    results = dict.fromkeys(interfaces, States.unspecified)

    if has_nm:
        nm_conf = NmInterfaceState()
        nm_conf.parse(nm_device_state)

    # fallback state
    global_scope_manager = States.unspecified.value
    if has_netplan:
        netplan_conf = Netplan()
        netplan_conf.parse(data=netplan_yaml)
        # if netplan has a top-level renderer use that as default:
        if netplan_conf.network.get('renderer'):
            global_scope_manager = netplan_conf.network['renderer']

    for n in results:
        log('=={}=='.format(n))
        category_scope_manager = States.unspecified.value
        if has_netplan:
            log('has netplan')
            if n in netplan_conf.wifis:
                category_scope_manager = netplan_conf.wifis.get(
                    'renderer', States.unspecified.value)
            elif n in netplan_conf.ethernets:
                category_scope_manager = netplan_conf.ethernets.get(
                    'renderer', States.unspecified.value)

        # Netplan config indcates NM
        if (global_scope_manager == States.nm.value or
                category_scope_manager == States.nm.value or
                not has_netplan):
            log('NM indicated')
            # if NM isnt actually available this is a bad config
            if not has_nm:
                log('error: netplan defines NM or there is no netplan, '
                    'but NM unavailable')
                results[n] = States.error
                continue
            # NM does not know the interface
            if nm_conf.devices.get(n) is None:
                log('error: netplan defines NM or there is no netplan, '
                    'but interface unknown to NM')
                results[n] = States.error
                continue
            # NM thinks it doesnt manage the device despite netplan config
            if nm_conf.devices.get(n) == 'unmanaged':
                log('error: netplan defines NM or there is no netplan, '
                    'but NM reports unmanaged')
                results[n] = States.unspecified
                continue
            results[n] = States.nm
            continue

        # has netplan but no renderer specified
        if has_netplan:
            results[n] = States.networkd
    return results


def main():
    results = identify_managers(has_netplan=is_netplan_available(),
                                has_nm=is_nm_available())
    for interface, state in results.items():
        print('device: {}'.format(interface))
        print('managed_by: {}'.format(state.value))
        print()


if __name__ == "__main__":
    main()
