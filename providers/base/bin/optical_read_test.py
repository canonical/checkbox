#!/usr/bin/env python3

import os
import sys
import posixpath
import filecmp
import shutil

from argparse import ArgumentParser
from subprocess import Popen, PIPE

DEFAULT_DIR = '/tmp/checkbox.optical'
DEFAULT_DEVICE_DIR = 'device'
DEFAULT_IMAGE_DIR = 'image'


CDROM_ID = '/lib/udev/cdrom_id'


def _command(command, shell=True):
    proc = Popen(command,
                   shell=shell,
                   stdout=PIPE,
                   stderr=PIPE
                   )
    return proc


def _command_out(command, shell=True):
    proc = _command(command, shell)
    return proc.communicate()[0].strip()


def compare_tree(source, target):
    for dirpath, dirnames, filenames in os.walk(source):
        #if both tree are empty return false
        if dirpath == source and dirnames == [] and filenames == []:
            return False
        for name in filenames:
            file1 = os.path.join(dirpath, name)
            file2 = file1.replace(source, target, 1)
            if os.path.isfile(file1) and not os.path.islink(file1):
                if filecmp.cmp(file1, file2):
                    continue
                else:
                    return False
            else:
                continue
    return True


def read_test(device):
    passed = False
    device_dir = os.path.join(DEFAULT_DIR, DEFAULT_DEVICE_DIR)
    image_dir = os.path.join(DEFAULT_DIR, DEFAULT_IMAGE_DIR)

    for dir in (device_dir, image_dir):
        if posixpath.exists(dir):
            shutil.rmtree(dir)
    os.makedirs(device_dir)

    try:
        _command("umount %s" % device).communicate()
        mount = _command("mount -o ro %s %s" % (device, device_dir))
        mount.communicate()
        if mount.returncode != 0:
            print("Unable to mount %s to %s" % 
                    (device, device_dir), file=sys.stderr)
            return False

        file_copy = _command("cp -dpR %s %s" % (device_dir, image_dir))
        file_copy.communicate()
        if file_copy.returncode != 0:
            print("Failed to copy files from %s to %s" % 
                    (device_dir, image_dir), file=sys.stderr)
            return False
        if compare_tree(device_dir, image_dir):
            passed = True
    except:
        print("File Comparison failed while testing %s" % device, 
                file=sys.stderr)
        passed = False
    finally:
        _command("umount %s" % device_dir).communicate(3)
        for dir in (device_dir, image_dir):
            if posixpath.exists(dir):
                shutil.rmtree(dir)

    if passed:
        print("File Comparison passed (%s)" % device)
    
    return passed


def get_capabilities(device):
    cmd = "%s %s" % (CDROM_ID, device)
    capabilities = _command_out(cmd)
    return capabilities


def main():
    tests = []
    return_values = []

    parser = ArgumentParser()
    parser.add_argument("device", nargs='+',
                        help=('Specify an optical device or list of devices '
                              'such as /dev/cdrom'))
    args = parser.parse_args()

    if os.geteuid() != 0:
        parser.error("ERROR: Must be root to run this script.")

    for device in args.device:

        capabilities = get_capabilities(device)
        if not capabilities:
            print("Unable to get capabilities of %s" % device, file=sys.stderr)
            return 1
        for capability in capabilities.decode().split('\n'):
            if capability[:3] == 'ID_':
                cap = capability[3:-2]
                if cap == 'CDROM' or cap == 'CDROM_DVD':
                    tests.append('read')

        for test in set(tests):
            print("Testing %s on %s ... " % (test, device), file=sys.stdout)
            tester = "%s_test" % test
            return_values.append(globals()[tester](device))
    
    return False in return_values

if __name__ == "__main__":
    sys.exit(main())
