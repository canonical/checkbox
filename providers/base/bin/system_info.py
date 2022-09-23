#!/usr/bin/env python3
# encoding: UTF-8
# Copyright (c) 2018 Canonical Ltd.
#
# Authors:
#     Sylvain Pineau <sylvain.pineau@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from collections import OrderedDict
import json
import re
import subprocess
import sys


def _run_cmd(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, universal_newlines=True)
    except subprocess.CalledProcessError as e:
        print(e.output, file=sys.stderr)
        return None


class INXI:
    """
    INXI JSON wrapper
    """

    def __init__(self, inxi_output):
        self._inxi = {}
        if inxi_output:
            self._inxi = inxi_output
        self._system_info = OrderedDict()

    def _find_section(self, key):
        for k, v in self._inxi.items():
            if key in k:
                return self._inxi[k]
        else:
            return []

    def _find_records(self, section, key):
        records = []
        for record in section:
            for k in record.keys():
                if key in k:
                    records.append(OrderedDict(sorted(record.items())))
        return records

    def _prepare_system_info(self):
        system_data = []
        system = self._find_section('System')
        system_info = self._find_records(system, '#Kernel')
        system_details = ''
        for i in system_info:
            for k, v in i.items():
                if '#Kernel' in k:
                    system_details += '{}: {}\n'.format(
                        re.sub('.*#', '', k), v)
                elif '#Distro' in k:
                    system_details += '{}: {}'.format(re.sub('.*#', '', k), v)
        if system_details:
            system_data = system_details.splitlines()
        if system_data:
            self._system_info['System'] = system_data

    def _prepare_machine_info(self):
        machine_data = []
        machine = self._find_section('Machine')
        machine_info = self._find_records(machine, '#Type')
        machine_details = ''
        for i in machine_info:
            for k, v in i.items():
                if '#serial' in k:
                    break
                elif '#product' in k:
                    machine_details += '\n'
                machine_details += '{}: {} '.format(re.sub('.*#', '', k), v)
        if machine_details:
            machine_data = machine_details.splitlines()
        machine_info = self._find_records(machine, '#UEFI')
        machine_UEFI = ''
        for i in machine_info:
            keep = False
            for k, v in i.items():
                if '#UEFI' in k:
                    keep = True
                if not keep:
                    continue
                machine_UEFI += '{}: {} '.format(re.sub('.*#', '', k), v)
        if machine_UEFI:
            machine_data.append(machine_UEFI)
        if machine_data:
            self._system_info['Machine'] = machine_data

    def _prepare_cpu_info(self):
        cpu_data = []
        cpu = self._find_section('CPU')
        cpu_info = self._find_records(cpu, '#Topology')
        cpu_details = ''
        for i in cpu_info:
            for k, v in i.items():
                if '#bits' in k or '#type' in k:
                    continue
                elif '#model' in k:
                    cpu_details += '\nModel: {} '.format(v)
                else:
                    cpu_details += '{}: {} '.format(re.sub('.*#', '', k), v)
                if '#arch' in k:
                    break
        if cpu_details:
            cpu_data = cpu_details.splitlines()
        if cpu_data:
            self._system_info['CPU'] = cpu_data

    def _prepare_memory_info(self):
        memory_data = []
        memory = self._find_section('Memory')
        memory_info = self._find_records(memory, '#total')
        memory_details = ''
        for i in memory_info:
            for k, v in i.items():
                if '#total' in k:
                    memory_details += v
                    break
        if memory_details:
            memory_data.append(memory_details)
        if memory_data:
            self._system_info['Memory'] = memory_data

    def _prepare_generic_info(self, section_name, key):
        generic_data = []
        generic = self._find_section(section_name)
        generic_info = self._find_records(generic, key)
        for i in generic_info:
            generic_details = ''
            ignore = False
            device_mode = False
            for k, v in i.items():
                # Ignore USB/removable devices (except Network)
                if '#type' in k and section_name != 'Network':
                    ignore = True
                if key in k and '#ID' not in k:
                    generic_details += v
                    device_mode = True
                if (
                    not device_mode and
                    ('#vendor' in k or '#model' in k or '#size' in k)
                ):
                    generic_details += '{} '.format(v)
                if '#chip ID' in k:
                    generic_details += ' [{}]'.format(v)
            if generic_details and not ignore:
                generic_data.append(generic_details)
        if generic_data:
            self._system_info[section_name] = generic_data

    def _prepare_raid_info(self):
        raid_data = []
        raid = self._find_section('RAID')
        raid_info = self._find_records(raid, '#Hardware')
        for i in raid_info:
            raid_details = ''
            for k, v in i.items():
                if '#Hardware' in k:
                    raid_details += v
                if '#chip ID' in k:
                    raid_details += ' [{}]'.format(v)
            if raid_details:
                raid_data.append(raid_details)
        if raid_data:
            self._system_info['RAID'] = raid_data
        raid_info = self._find_records(raid, '#Device')
        for i in raid_info:
            raid_details = ''
            for k, v in i.items():
                if '#Device' in k:
                    raid_details += v
                if '#type' in k:
                    raid_details += ' {}: {} '.format(re.sub('.*#', '', k), v)
            if raid_details:
                raid_data.append(raid_details)
        if raid_data:
            self._system_info['RAID'] = raid_data

    def get_sys_info(self):
        self._prepare_system_info()
        self._prepare_machine_info()
        self._prepare_cpu_info()
        self._prepare_memory_info()
        self._prepare_generic_info('Audio', '#Device')
        self._prepare_generic_info('Graphics', '#Device')
        self._prepare_generic_info('Network', '#Device')
        self._prepare_generic_info('Drives', '#ID')
        self._prepare_raid_info()
        return self._system_info


def main():
    inxi_output = _run_cmd(
        "inxi_snapshot --usb-sys -A -G -C -M -m -N -D -S -R -xx "
        "--output json --output-file print")
    if not inxi_output:
        inxi_output = '{}'
    inxi = INXI(json.loads(inxi_output))
    sys_info = inxi.get_sys_info()
    extra_sections = {
        'Bluetooth': 'BLUETOOTH',
        'Touchscreen': 'TOUCHSCREEN',
        'Webcam': 'CAPTURE',
        'Touchpad': 'TOUCHPAD'
    }
    for section, udev_category in extra_sections.items():
        section_info = _run_cmd(
            'udev_resource.py -l {} -s'.format(udev_category))
        if section_info:
            sys_info[section] = section_info.splitlines()
    print(json.dumps(sys_info, indent=4))


if __name__ == '__main__':
    raise SystemExit(main())
