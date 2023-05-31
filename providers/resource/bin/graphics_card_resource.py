#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2015-2017 Canonical Ltd.
#    Authors: Daniel Manrique <daniel.manrique@canonical.com>
#    Authors: Maciej Kisielewski <maciej.kisielewski@canonical.com>
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

import argparse
import collections
import subprocess
import shlex
import string
import re


def get_ubuntu_version():
    """Get Ubuntu release version for checking."""
    try:
        import distro
        return distro.version()
    except (ImportError, subprocess.CalledProcessError):
        try:
            with open('/etc/lsb-release', 'r') as lsb:
                for line in lsb.readlines():
                    (key, value) = line.split('=', 1)
                    if key == 'DISTRIB_RELEASE':
                        return re.sub('["\n]', '', value)
        except OSError:
            # Missing file or permissions? Return the default lsb_release
            pass
    return 0


def compare_ubuntu_release_version(_version):
    """
    Compare ubuntu release version.
    If host version is higher or equal provided, it will return True.
    """
    os_version = get_ubuntu_version()
    try:
        from packaging import version
        return version.parse(os_version) >= version.parse(_version)
    except (ImportError, subprocess.CalledProcessError):
        return os_version >= _version


def slugify(_string):
    """Transform any string to one that can be used in job IDs."""
    valid_chars = frozenset(
        "-_.{}{}".format(string.ascii_letters, string.digits))
    return ''.join(c if c in valid_chars else '_' for c in _string)


def subprocess_lines_generator(command):
    """
    Generator that opens a subprocess and spits out lines
    from the process's stdout.
    Current assumptions:
    - Process spits out text (universal_newlines)
    - output contains suitable newlines
    """
    com_pipe = subprocess.Popen(command,
                                stdout=subprocess.PIPE,
                                universal_newlines=True)
    for ln in com_pipe.stdout:
        yield ln
    # Final communicate to wait for process to die.
    com_pipe.communicate()


def udev_devices(lines):
    """
    Generator that reads the given "lines" iterable (ideally containing
    text lines) and spits out "records" expressed as dictionaries.
    A record contains groups of lines delimited by a blank line (BOF/EOF count
    as delimiters). Each line is split at the first colon (for a key: value
    syntax) to build the dict. Lines look like:
    bus: pci
    index: 2
    product_id: 26880
    """
    record = {}

    for line in lines:
        line = line.strip()
        if line == "":
            if record:
                yield record
            record = {}
        else:
            try:
                key, value = line.split(":", 1)
                key = key.strip()
                record[key] = value.strip()
            except ValueError:
                # If a line has no colon it's suspicious, maybe a
                # bogus input file. Let's discard it.
                pass
    # No more lines to read, so process the remainder
    if record:
        yield record


def parse_args():
    parser = argparse.ArgumentParser(description="Resource to filter and "
                                                 "enumerate graphics cards.")
    parser.add_argument("-c", "--command",
                        default='udev_resource.py',
                        help="""udev_resource command to run. Defaults
                        to %(default)s.""")
    return parser.parse_args()


def bus_ordering(record):
    if record.get('bus') == "pci":
        # We are looking for this ---------------v
        # /devices/pci0000:00/0000:00:02.1/0000:01:00.0
        return int(record.get('path').split(':')[-2], 16)
    return 0


def main():
    """
    graphics_card_resource.py was done as a script to be able to reuse it in
    graphics tests that need to be generated per-card.
    It does two things in addition to what filtering the resources by
    category=VIDEO would achieve:
    1- It enumerates them and adds an index attribute
    2- If the device has no product/vendor attributes, "fake" them with the
       PCI ID (so we can visually distinguish them even if they have no name
       because they are too new or not on the pci.ids database)
    """

    options = parse_args()
    udev_command = shlex.split(options.command)

    udev_output = subprocess_lines_generator(udev_command)

    # udev_devices generates one dict per device, the list shown
    # below filters that to only VIDEO ones
    video_devices = list(
        r for r in udev_devices(udev_output) if r.get(
            "category", "") == 'VIDEO')
    video_devices.sort(key=lambda r: bus_ordering(r))

    # commands needed to switch to and from particular GPU,
    # keyed by the driver name. Defaults to 'false'/'false' commands.
    switch_cmds = collections.defaultdict(lambda: ('false', 'false'))
    switch_cmds['nvidia'] = ('prime-select nvidia', 'prime-select intel')
    # nvidia uses 'pcieport' driver when the dGPU is disabled
    switch_cmds['pcieport'] = ('prime-select nvidia', 'prime-select intel')

    switch_cmds['amdgpu-pro'] = (
        '/opt/amdgpu-pro/bin/amdgpu-pro-px --mode performance',
        '/opt/amdgpu-pro/bin/amdgpu-pro-px --mode powersaving')

    # Lazily add index to each video device
    try:
        for index, record in enumerate(video_devices, 1):
            record['index'] = index
            record['gpu_count'] = len(video_devices)
            if record.get('vendor_id', '') == '4098':  # vendor == amd/ati
                if subprocess.call(
                        ['dpkg-query', '-W', 'vulkan-amdgpu-pro'],
                        stderr=subprocess.STDOUT,
                        stdout=subprocess.DEVNULL) == 0:
                    # dpkg-query did not report error, so
                    # vulkan-amdgpu-pro is installed
                    record['driver'] = 'amdgpu-pro'
            if 'product' not in record:
                # Fake a product name with the product_id
                try:
                    product_id = int(record.get('product_id', 0))
                    fake_product = "PCI ID 0x{:x}".format(product_id)
                except ValueError:
                    fake_product = "PCI ID unknown"
                record['product'] = fake_product
                record['product_slug'] = slugify(fake_product)
            if 'vendor' not in record:
                # Fake a vendor name with the vendor_id
                try:
                    vendor_id = int(record.get('vendor_id', 0))
                    fake_vendor = "PCI ID 0x{:x}".format(vendor_id)
                except ValueError:
                    fake_vendor = "PCI ID unknown"
                record['vendor'] = fake_vendor
                record['vendor_slug'] = slugify(fake_vendor)
            if 'driver' not in record:
                record['driver'] = 'unknown'
            # lp:1636060 – If discrete GPU is using amdgpu driver,
            # we set the prime_gpu_offload flag to 'On'
            if index == 2:
                if record['driver'] == 'amdgpu':
                    record['prime_gpu_offload'] = 'On'
                # NVIDIA driver supports PRIME render offload since version
                # 435.17, and Ubuntu doesn't support Intel mode after 22.04.
                elif (record['driver'] in ('nvidia', 'pcieport')
                        and compare_ubuntu_release_version('22.04')):
                    record['prime_gpu_offload'] = 'On'
            else:
                record['prime_gpu_offload'] = 'Off'
            record['switch_to_cmd'] = switch_cmds[record['driver']][0]
            if index == 2 and len(video_devices) == 2:
                # we're at GPU number 2 and there are two, so here we assume
                # that video_devices[0] is the built-in one
                video_devices[0]['switch_to_cmd'] = (
                    switch_cmds[record['driver']][1])
        # Finally, print the records
        for record in video_devices:
            items = ["{key}: {value}".format(key=k, value=record[k])
                     for k in sorted(record.keys())]
            print("\n".join(items))
            print("")
    except OSError as err:
        raise SystemExit(err)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
