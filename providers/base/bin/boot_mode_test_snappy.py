#!/usr/bin/env python3
# Copyright 2018 Canonical Ltd.
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>

import io
import os
import re
import sys
import subprocess as sp

import yaml


def fitdumpimage(filename):
    cmd = 'dumpimage -l {}'.format(filename)
    out = sp.check_output(cmd, shell=True).decode(sys.stdout.encoding)
    buf = io.StringIO(out)

    # first line should identify FIT file
    if not buf.readline().startswith('FIT description'):
        raise SystemExit('ERROR: expected FIT image description')

    # second line contains some metadata, skip it
    buf.readline()

    # from then on should get blocks of text describing the objects that were
    # combined in to the FIT image e.g. kernel, ramdisk, device tree
    image_re = re.compile(r'(?:^\ Image)\ \d+\ \((\S+)\)$')
    config_re = re.compile(r'^\ Default Configuration|^\ Configuration')
    objects = {}
    name = ''
    while True:
        line = buf.readline()
        # stop at end
        if line == '':
            break
        # interested in storing image information
        match = image_re.search(line)
        if match:
            name = match.group(1)
            objects[name] = {}
            continue
        # not interested in configurations
        if config_re.search(line):
            name = ''
            continue
        # while in an image section store the info
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
        data = yaml.load(f)
        for k in data['volumes'].keys():
            bootloader = data['volumes'][k]['bootloader']
    if not bootloader:
        raise SystemExit('ERROR: could not find name of bootloader')

    if bootloader not in ('u-boot', 'grub'):
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

    if bootloader == 'grub':
        cmd = 'mokutil --sb-state'
        print('+', cmd, flush=True)
        out = sp.check_output(cmd, shell=True).decode(sys.stdout.encoding)
        print(out, flush=True)
        if out != 'SecureBoot enabled\n':
            raise SystemExit('ERROR: mokutil reports Secure Boot not in use')

        print('Secure Boot appears to be enabled on this system')


if __name__ == '__main__':
    main()
