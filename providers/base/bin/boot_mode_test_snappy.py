#!/usr/bin/env python3
# Copyright 2018-2019 Canonical Ltd.
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>

import io
import os
import re
import shutil
import sys
import subprocess as sp
import tempfile

import yaml

from checkbox_support.snap_utils.system import get_lk_bootimg_path


def fitdumpimage(filename):
    cmd = 'dumpimage -l {}'.format(filename)
    try:
        out = sp.check_output(cmd, shell=True).decode(sys.stdout.encoding)
    except Exception:
        raise SystemExit(1)
    buf = io.StringIO(out)

    # first line should identify FIT file
    if not buf.readline().startswith('FIT description'):
        raise SystemExit('ERROR: expected FIT image description')

    # second line contains some metadata, skip it
    buf.readline()

    # from then on should get blocks of text describing the objects that were
    # combined in to the FIT image e.g. kernel, ramdisk, device tree
    image_config_re = re.compile(
        r'(?:^\ Image|Configuration)\ \d+\ \((\S+)\)$')
    configuration_re = re.compile(r'^\ Default Configuration')
    objects = {}
    name = ''
    while True:
        line = buf.readline()
        # stop at end
        if line == '':
            break
        # interested in storing image information
        match = image_config_re.search(line)
        if match:
            name = match.group(1)
            objects[name] = {}
            continue
        # not interested in the default configuration
        if configuration_re.search(line):
            name = ''
            continue
        # while in an image/config section store the info
        if name != '':
            entries = [s.strip() for s in line.split(':', 1)]
            objects[name][entries[0]] = entries[1]
    return objects


def main():
    if len(sys.argv) != 3:
        raise SystemExit('ERROR: please supply gadget & kernel name')
    gadget = sys.argv[1]
    kernel = sys.argv[2]

    gadget_yaml = os.path.join('/snap', gadget, 'current/meta/gadget.yaml')

    if not os.path.exists(gadget_yaml):
        raise SystemExit(
            'ERROR: failed to find gadget.yaml at {}'.format(gadget_yaml))

    with open(gadget_yaml) as f:
        data = yaml.load(f, Loader=yaml.SafeLoader)
        for k in data['volumes'].keys():
            if 'bootloader' not in data['volumes'][k]:
                continue
            bootloader = data['volumes'][k]['bootloader']
    if not bootloader:
        raise SystemExit('ERROR: could not find name of bootloader')

    if bootloader not in ('u-boot', 'grub', 'lk'):
        raise SystemExit(
            'ERROR: Unexpected bootloader name {}'.format(bootloader))
    print('Bootloader is {}\n'.format(bootloader))

    if bootloader == 'u-boot':
        print('Parsing FIT image information...\n')

        kernel_rev = os.path.basename(
            os.path.realpath('/snap/{}/current'.format(kernel)))
        boot_kernel = '/boot/uboot/{}_{}.snap/kernel.img'.format(
            kernel, kernel_rev)
        boot_objects = fitdumpimage(boot_kernel)

        for obj, attrs in boot_objects.items():
            if obj == 'conf':
                continue
            print('Checking object {}'.format(obj))
            if 'Sign value' not in attrs:
                raise SystemExit('ERROR: no sign value found for object')
            print('Found "Sign value"')
            if len(attrs['Sign value']) != 512:
                raise SystemExit('ERROR: unexpected sign value size')
            if all(s in attrs['Sign algo'] for s in ['sha256', 'rsa2048']):
                print('Found expected signing algorithms')
            else:
                raise SystemExit(
                    'ERROR: unexpected signing algorithms {}'.format(
                        attrs['Sign algo']))
            print()

        # check that all parts of the fit image have
        snap_kernel = '/snap/{}/current/kernel.img'.format(kernel)
        snap_objects = fitdumpimage(snap_kernel)
        if snap_objects != boot_objects:
            raise SystemExit(
                'ERROR: boot kernel and current snap kernel do not match')
        print('Kernel images in current snap and u-boot match\n')

        print('Secure Boot appears to be enabled on this system')

    if bootloader == 'lk':
        bootimg_path = get_lk_bootimg_path()
        if bootimg_path == 'unknown':
            raise SystemExit('ERROR: lk-boot-env not found')

        # XXX: Assuming FIT format
        bootimg = os.path.basename(bootimg_path)
        print('Parsing FIT image information ({})...\n'.format(bootimg))

        with tempfile.TemporaryDirectory() as tmpdirname:
            shutil.copy2(bootimg_path, tmpdirname)
            boot_kernel = os.path.join(tmpdirname, bootimg)
            boot_objects = fitdumpimage(boot_kernel)

        for obj, attrs in boot_objects.items():
            if obj != 'conf':
                continue
            print('Checking object {}'.format(obj))
            if 'Sign value' not in attrs:
                raise SystemExit('ERROR: no sign value found for object')
            print('Found "Sign value"')
            if len(attrs['Sign value']) != 512:
                raise SystemExit('ERROR: unexpected sign value size')
            if all(s in attrs['Sign algo'] for s in ['sha256', 'rsa2048']):
                print('Found expected signing algorithms')
            else:
                raise SystemExit(
                    'ERROR: unexpected signing algorithms {}'.format(
                        attrs['Sign algo']))
            print()

        # check that all parts of the fit image have
        snap_kernel = '/snap/{}/current/boot.img'.format(kernel)
        snap_objects = fitdumpimage(snap_kernel)
        if snap_objects != boot_objects:
            raise SystemExit(
                'ERROR: boot kernel and current snap kernel do not match')
        print('Kernel images in current snap and lk snapbootsel match\n')

        print('Secure Boot appears to be enabled on this system')

    if bootloader == 'grub':
        cmd = 'mokutil --sb-state'
        print('+', cmd, flush=True)
        try:
            out = sp.check_output(cmd, shell=True).decode(sys.stdout.encoding)
        except Exception:
            raise SystemExit(1)
        print(out, flush=True)
        if out != 'SecureBoot enabled\n':
            raise SystemExit('ERROR: mokutil reports Secure Boot not in use')

        print('Secure Boot appears to be enabled on this system')


if __name__ == '__main__':
    main()
