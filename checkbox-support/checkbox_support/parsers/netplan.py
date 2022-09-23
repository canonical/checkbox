# This file is based on the parser from the netplan project:
# https://github.com/CanonicalLtd/netplan/blob/master/netplan/configmanager.py
#
# Copyright 2019 Canonical Ltd.
#
# Authors:
#   Mathieu Trudel-Lapierre <mathieu.trudel-lapierre@canonical.com>
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

import glob
import io
import logging
import os
import yaml


class Netplan():

    def __init__(self, prefix="/"):
        self.prefix = prefix
        self.config = {}

    @property
    def network(self):
        return self.config['network']

    @property
    def interfaces(self):
        interfaces = {}
        interfaces.update(self.ethernets)
        interfaces.update(self.wifis)
        interfaces.update(self.bridges)
        interfaces.update(self.bonds)
        interfaces.update(self.vlans)
        return interfaces

    @property
    def physical_interfaces(self):
        interfaces = {}
        interfaces.update(self.ethernets)
        interfaces.update(self.wifis)
        return interfaces

    @property
    def ethernets(self):
        return self.network['ethernets']

    @property
    def wifis(self):
        return self.network['wifis']

    @property
    def bridges(self):
        return self.network['bridges']

    @property
    def bonds(self):
        return self.network['bonds']

    @property
    def vlans(self):
        return self.network['vlans']

    @property
    def renderer(self):
        return self.network['renderer']

    def parse(self, data=None):
        """
        Parse all our config files to return an object that describes the
        system's entire configuration, so that it can later be interrogated.
        Returns a dict that contains the entire, collated and merged YAML.
        """
        self.config['network'] = {
            'ethernets': {},
            'wifis': {},
            'bridges': {},
            'bonds': {},
            'vlans': {},
            'renderer': None
        }

        if data is None:
            # /run/netplan shadows /etc/netplan/, which shadows /lib/netplan
            names_to_paths = {}
            for yaml_dir in ['lib', 'etc', 'run']:
                for yaml_file in glob.glob(os.path.join(
                        self.prefix, yaml_dir, 'netplan', '*.yaml')):
                    names_to_paths[os.path.basename(yaml_file)] = yaml_file

            files = [names_to_paths[name]
                     for name in sorted(names_to_paths.keys())]

            for yaml_file in files:
                with open(yaml_file) as f:
                    self._merge_yaml_config(f)
        else:
            with io.StringIO(data) as f:
                self._merge_yaml_config(f)

    def _merge_interface_config(self, orig, new):
        new_interfaces = set()
        changed_ifaces = list(new.keys())

        for ifname in changed_ifaces:
            iface = new.pop(ifname)
            if ifname in orig:
                logging.debug("{} exists in {}".format(ifname, orig))
                orig[ifname].update(iface)
            else:
                logging.debug("{} not found in {}".format(ifname, orig))
                orig[ifname] = iface
                new_interfaces.add(ifname)

        return new_interfaces

    def _merge_yaml_config(self, yaml_stream):
        new_interfaces = set()

        try:
            yaml_data = yaml.load(yaml_stream, Loader=yaml.CSafeLoader)
            network = None
            if yaml_data is not None:
                network = yaml_data.get('network')
            if network:
                if 'ethernets' in network:
                    new = self._merge_interface_config(
                        self.ethernets, network.get('ethernets'))
                    new_interfaces |= new
                if 'wifis' in network:
                    new = self._merge_interface_config(
                        self.wifis, network.get('wifis'))
                    new_interfaces |= new
                if 'bridges' in network:
                    new = self._merge_interface_config(
                        self.bridges, network.get('bridges'))
                    new_interfaces |= new
                if 'bonds' in network:
                    new = self._merge_interface_config(
                        self.bonds, network.get('bonds'))
                    new_interfaces |= new
                if 'vlans' in network:
                    new = self._merge_interface_config(
                        self.vlans, network.get('vlans'))
                    new_interfaces |= new
                if 'renderer' in network:
                    self.config['network']['renderer'] = network.get(
                        'renderer')
            return new_interfaces
        except (IOError, yaml.YAMLError):
            logging.error('Error while loading yaml')
            self.config = {}
