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
import subprocess as sp
import sys

from checkbox_support.parsers.netplan import Netplan
from checkbox_support.parsers.udevadm import UdevadmParser, UdevResult


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


class NmInterfaceState():

    def __init__(self):
        self.devices = {}
        cmd = 'nmcli -v'
        rc = sp.call(cmd, shell=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        if rc != 0:
            self.available = False
            return
        self.available = True
        cmd = 'nmcli -t -f DEVICE,STATE d'
        output = sp.check_output(cmd, shell=True).decode(sys.stdout.encoding)
        for line in output.splitlines():
            dev, state = line.strip().split(':')
            self.devices[dev] = state


class States(Enum):
    unspecified = 'unspecified'
    error = 'error'
    networkd = 'networkd'
    nm = 'NetworkManager'


def main():
    # Use udev as definitive source of network interfaces
    all_interfaces = UdevInterfaceLister(['NETWORK', 'WIRELESS'])

    # Get the neplan config
    netplan_conf = Netplan()
    netplan_conf.parse()

    # Get the NetworkManager config
    nm_conf = NmInterfaceState()

    # fallback state
    global_scope_manager = States.unspecified.value

    # if netplan has a top-level renderer use that as default:
    if netplan_conf.network.get('renderer'):
        global_scope_manager = netplan_conf.network['renderer']

    for n in all_interfaces.names:
        print('device: {}'.format(n))
        print('nmcli_available: {}'.format(nm_conf.available))

        # Netplan config indcates NM
        if global_scope_manager == States.nm.value:
            # if NM isnt actually available this is a bad config
            if not nm_conf.available:
                print('managed_by: {}'.format(States.error.value))
                print()
                continue
            # NM does not know the interface
            if nm_conf.devices.get(n) is None:
                print('managed_by: {}'.format(States.error.value))
                print()
                continue
            # NM thinks it doesnt managed the device despite netplan config
            if nm_conf.devices.get(n) == 'unmanaged':
                print('managed_by: {}'.format(States.error.value))
                print()
                continue
            print('managed_by: {}'.format(States.nm.value))
            print()
            continue

        # No renderer specified
        print('managed_by: {}'.format(States.networkd.value))
        print()


if __name__ == "__main__":
    main()
