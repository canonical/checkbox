# Copyright (C) 2020 Canonical Ltd.
#
# Authors:
#   Rod Smith <rod.smith@canonical.com>
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
"""
Support functions related to disk devices for Checkbox.
"""


from subprocess import (
    CalledProcessError,
    check_output
)
import logging
import os
import shlex
import stat
import sys
import uuid


def get_partition_data(file):
    """Get partition details (size & type) on /dev/{file} & return in
    dictionary."""

    part_data = {}
    part_data['name'] = file

    # Get size of device, in bytes....
    command = "blockdev --getsize64 /dev/{}".format(file)
    part_data['size'] = int(check_output(shlex.split(command)))

    # Get filesystem type....
    part_data['fs_type'] = ""
    command = "blkid /dev/{} -o export".format(file)
    try:
        local_results = check_output(shlex.split(command)).split()
    except CalledProcessError:
        local_results = []
    for result in local_results:
        result_str = result.decode(sys.stdout.encoding, errors="ignore")
        if "TYPE" in result_str:
            part_data['fs_type'] = result_str.split("=")[1]
    return part_data


def find_mount_point(file):
    """Find the mount point of /dev/{file}.
    Returns:
    * None if unmounted
    * The mount point (as a string) if it's mounted."""

    mount_point = None
    cmd = "df /dev/{} --output=target".format(file)
    output = check_output(shlex.split(cmd)).decode(encoding="utf-8").split()
    potential_mount_point = str(output[-1])
    # If df is fed a non-mounted-partition, it returns "/dev" as the
    # mount point, so ignore that....
    if potential_mount_point != "/dev":
        mount_point = potential_mount_point
    return mount_point


class Disk():
    """
    Interfaces to disk device
    """

    # 10GiB (smallest acceptable size for disk tests):
    MIN_SZ = 10 * 1024 * 1024 * 1024

    def __init__(self, device=""):
        self.device = device
        self.all_parts = []
        self.unsupported_fs = None
        self.test_dir = "/tmp"
        self.mount_point = ""
        lvm_detected = False
        # Find final element of device name; for instance "sda" for "/dev/sda"
        stripped_devname = self.device.split("/")[-1]

        # Do first pass to collect data on partitions & software RAID
        # devices (which we treat like partitions)....
        for file in os.listdir("/sys/class/block"):
            if stripped_devname in file:
                part_data = get_partition_data(file)
                part_data['part_type'] = "partition"
                if part_data['fs_type'] == "LVM2_member":
                    lvm_detected = True
                self.all_parts.append(part_data)

        # Do another pass to collect data on logical volumes, if any exist
        # on the target device....
        # NOTE: This code ignores where an LVM exists; it could span multiple
        # disks, or be on one other than the one being tested. Canonical
        # certification specifies use of partitions, not LVMs, so this code
        # exists mainly for software development using development systems,
        # not on servers actually being tested.
        if lvm_detected:
            for file in os.listdir("/sys/class/block/"):
                if "dm-" in file:
                    part_data = get_partition_data(file)
                    part_data['part_type'] = "lv"
                    self.all_parts.append(part_data)

    def get_mount_point(self):
        return self.mount_point

    def is_block_device(self):
        try:
            mode = os.stat(self.device).st_mode
            if not stat.S_ISBLK(mode):
                logging.error("{} is NOT a block device! Aborting!".
                              format(self.device))
                return False
        except FileNotFoundError:
            logging.error("{} does not exist! Aborting!".format(self.device))
            return False
        return True

    def find_largest_partition(self):
        """Find the largest partition that holds a supported filesystem on
        self.device. Sets:
        self.largest_part -- Dictionary containing information on largest
                             partition
        self.unsupported_fs -- Empty or contains information about largest
                               unsupported filesystem (of certain known types)
                               found on disk"""

        self.largest_part = {'name': "",
                             'size': 0,
                             'part_type': "lv",
                             'fs_type': ""}
        self.unsupported_fs = None

        # A filesystem can be supported for the test; unsupported but worth
        # noting in an error message; or unsupported and not worth noting.
        # The first two categories are enumerated in lists....
        supported_filesystems = ['ext2', 'ext3', 'ext4', 'xfs', 'jfs', 'btrfs']
        unsupported_filesystems = ['ntfs', 'vfat', 'hfs', 'LVM2_member']

        for part in self.all_parts:
            new_sz = int(part['size'])
            old_sz = int(self.largest_part['size'])
            new_lv = part['part_type'] == "lv"
            old_lv = self.largest_part['part_type'] == "lv"
            if (new_sz > 0 and old_sz == 0) or \
                    (new_sz > self.MIN_SZ and old_sz < self.MIN_SZ) or \
                    (new_sz > self.MIN_SZ and new_sz > old_sz and old_lv) or \
                    (new_sz > old_sz and not new_lv):
                if part['fs_type'] in supported_filesystems:
                    self.largest_part = part
                elif part['fs_type'] in unsupported_filesystems:
                    # Make note of it if it might be an old filesystem
                    # that was not properly re-allocated....
                    self.unsupported_fs = part
        return self.largest_part

    def mount_filesystem(self, simulate):
        logging.info("Disk device is {}".format(self.device))
        target_part = self.find_largest_partition()
        if not target_part['name']:
            if self.unsupported_fs is not None:
                logging.error("A filesystem of type {} was found, but is not "
                              "supported by this test.".
                              format(self.unsupported_fs['fs_type']))
                logging.error("A Linux-native filesystem (ext2/3/4fs, XFS, "
                              "JFS, or Btrfs) is required.")
            else:
                logging.error("No suitable partition found!")
            return False

        if target_part['size'] < self.MIN_SZ:
            logging.warning("Warning: {} is less than {:.0f} GiB in size!".
                            format(target_part['name'],
                                   self.MIN_SZ/1024/1024/1024))
            logging.error("Disk is too small to test. Aborting test!")
            return False

        full_device = "/dev/{}".format(target_part['name'])
        logging.info("Testing partition {}".format(full_device))
        self.mount_point = find_mount_point(target_part['name'])
        if simulate:
            logging.info("Run with --simulate, so not mounting filesystems.")
            logging.info("If run without --simulate, would mount {} to {}".
                         format(full_device, self.mount_point))
            logging.info("(if not already mounted).")
        else:
            if not self.mount_point:
                self.mount_point = "/mnt/{}".format(target_part['name'])
                logging.info("Trying to mount {} to {}...".
                             format(full_device, self.mount_point))
                os.makedirs(self.mount_point, exist_ok=True)
                command = "mount {} {}".format(full_device, self.mount_point)
                output = check_output(shlex.split(command)) \
                    .decode(encoding="utf-8")
                logging.info(output)
            else:
                logging.info("{} is already mounted at {}".
                             format(full_device, self.mount_point))
            self.test_dir = "{}/tmp/stress-ng-{}".format(self.mount_point,
                                                         uuid.uuid1())
            os.makedirs(self.test_dir, exist_ok=True)
        return True
