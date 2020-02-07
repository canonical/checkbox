#!/usr/bin/env python3
# Copyright 2015-2020 Canonical Ltd.
# Written by:
#   Shawn Wang <shawn.wang@canonical.com>
#   Jonathan Cave <jonathan.cave@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Show the recovery partition information for the preinstalled OS."""

import os
import re
import subprocess
import sys
import tempfile

import xml.dom.minidom as minidom


RECOVERY_PACKAGES = ["dell-recovery", "ubuntu-recovery"]


def get_recovery_package():
    """
    Test with RECOVERY_PACKAGES.

    to check recovery application is installed or not

    :return:
        string of package_version or None
    """
    for pkg in RECOVERY_PACKAGES:
        output = subprocess.check_output(["apt-cache", "policy", pkg],
                                         universal_newlines=True)
        for line in output.split("\n"):
            if line.startswith("  Installed:"):
                ver = line.split(": ")[1]
                return "{}_{}".format(pkg, ver.strip())
    return None


RECOVERY_LABELS = {"HP_TOOLS": "HP",
                   "PQSERVICE": "UBUNTU",
                   "BACKUP": "TEST",
                   "INSTALL": "DELL",
                   "OS": "DELL",
                   "RECOVERY": "DELL"}


_escape_pattern = re.compile(r'\\x([0-9a-fA-F][0-9a-fA-F])')


def lsblk_unescape(label):
    """Un-escape text escaping done by lsblk(8)."""
    return _escape_pattern.sub(
        lambda match: chr(int(match.group(1), 16)), label)


def get_recovery_partition():
    """
    Get the type and location of the recovery partition.

    :return:
        (recovery_type, recovery_partition) or None

    Use lsblk(8) to inspect available block devices looking
    for a partition with FAT or NTFS and a well-known label.
    """
    cmd = ['lsblk', '-o', 'TYPE,FSTYPE,NAME,LABEL', '--raw']
    for line in subprocess.check_output(cmd).splitlines()[1:]:
        type, fstype, name, label = line.split(b' ', 3)
        # Skip everything but partitions
        if type != b'part':
            continue
        # Skip everything but FAT and NTFS
        if fstype != b'vfat' and fstype != b'ntfs':
            continue
        label = lsblk_unescape(label.decode('utf-8'))
        recovery_type = RECOVERY_LABELS.get(label)
        # Skip unknown labels
        if recovery_type is None:
            continue
        recovery_partition = '/dev/{}'.format(name.decode('utf-8'))
        return (recovery_type, recovery_partition)


class MountedPartition(object):

    """
    Mount Manager to mount partition on tempdir.

    e.g.
    with MountedPartition("/dev/sda1") as tmp:
        print("This is the mount point: {}".format(tmp))
        do_stuff()
    """

    def __init__(self, part):
        """
        Prepare the mntdir point.

        :param part: string of the partition device file, like /dev/sda2
        """
        self.part = part
        self.mntdir = tempfile.mkdtemp()

    def __enter__(self):
        """
        __enter__ method for python's with statement.

        Mount the partition device to the mntdir.
        """
        cmd = ["mount", self.part, self.mntdir]
        subprocess.check_output(cmd, universal_newlines=True)
        return self.mntdir

    def __exit__(self, type, value, traceback):
        """
        __exit__ method for python's with statement.

        Unmount and remove the mntdir.
        """
        subprocess.check_output(["umount", self.mntdir],
                                universal_newlines=True)
        os.rmdir(self.mntdir)


class RecoveryInfo():

    """
    Inspect the recovery partition.

    This command can be used to inspect the recovery partition. It has several
    sub-commands that do various tasks.  If the system has no recovery
    partition, the command exits with the error code 1.
    """

    def main(self):
        partition = get_recovery_partition()
        if len(sys.argv) == 1:
            # no subcommand == detect test
            if partition is None:
                raise SystemExit("FAIL: Recovery partition not found")
            else:
                print("Found recovery partiion")
                return

        (recovery_type, recovery_partition) = partition

        subcommand = sys.argv[1]
        sub_commands = ('version', 'file', 'checktype')
        if subcommand not in sub_commands:
            raise SystemExit("ERROR: unexpected subcommand")

        if subcommand == "checktype":
            if len(sys.argv) != 3:
                raise SystemExit(
                    "ERROR: recovery_info.py checktype EXPECTED_TYPE")
            expected_type = sys.argv[2]
            if recovery_type != expected_type:
                raise SystemExit("FAIL: expected {}, found {}".format(
                    expected_type, recovery_type))

        if subcommand == "file":
            if len(sys.argv) != 3:
                raise SystemExit(
                    "ERROR: recovery_info.py file FILE")
            file = sys.argv[2]
            with MountedPartition(recovery_partition) as mnt:
                return subprocess.call([
                    'cat', '--', os.path.join(mnt, file)])

        if subcommand == "version":
            if os.path.isfile("/etc/buildstamp"):
                with open('/etc/buildstamp', 'rt', encoding='UTF-8') as stream:
                    data = stream.readlines()
                    print("image_version: {}".format(data[1].strip()))

            with MountedPartition(recovery_partition) as mntdir:
                fname = "{}/bto.xml".format(mntdir)
                if os.path.isfile(fname):
                    o = minidom.parse("{}/bto.xml".format(mntdir))
                    bto_platform = o.getElementsByTagName("platform")
                    bto_revision = o.getElementsByTagName("revision")
                    if bto_platform and bto_revision:
                        bto_platform = bto_platform[0].firstChild.data
                        bto_revision = bto_revision[0].firstChild.data
                        bto_version = bto_platform + " " + bto_revision
                    else:
                        bto_iso = o.getElementsByTagName("iso")
                        bto_version = bto_iso[0].firstChild.data
                    print("bto_version: {}".format(bto_version))


if __name__ == '__main__':
    RecoveryInfo().main()
