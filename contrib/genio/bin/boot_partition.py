#!/usr/bin/env python3
# This script should be run as a super user

import subprocess
import pathlib
import json
from argparse import ArgumentParser


def runcmd(command):
    ret = subprocess.run(command,
                         shell=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         encoding="utf-8",
                         timeout=1)
    return ret


class TestPartedBootDevice():

    def __init__(self):
        self.path = None
        self.actual_result = None
        self.expected_result = None
        self.expected_result_UFS = {
            "logical-sector-size": 4096,
            "physical-sector-size": 4096,
            "partitions": [
                {
                    "number": 1,
                    "name": "bootloaders"
                }, {
                    "number": 2,
                    "name": "bootloaders_b"
                }, {
                    "number": 3,
                    "name": "firmware"
                }, {
                    "number": 4,
                    "name": "firmware_b"
                }, {
                    "number": 5,
                    "name": "dramk"
                }, {
                    "number": 6,
                    "name": "misc"
                }, {
                    "number": 7,
                    "name": "bootassets"
                }, {
                    "number": 8,
                    "name": "ubuntu-boot"
                }, {
                    "number": 9,
                    "name": "writable"
                }
            ]
        }
        self.expected_result_EMMC = {
            "logical-sector-size": 512,
            "physical-sector-size": 512,
            "partitions": [
                {
                    "number": 1,
                    "name": "bootloaders"
                }, {
                    "number": 2,
                    "name": "bootloaders_b"
                }, {
                    "number": 3,
                    "name": "firmware"
                }, {
                    "number": 4,
                    "name": "firmware_b"
                }, {
                    "number": 5,
                    "name": "dramk"
                }, {
                    "number": 6,
                    "name": "misc"
                }, {
                    "number": 7,
                    "name": "bootassets"
                }, {
                    "number": 8,
                    "name": "ubuntu-boot"
                }, {
                    "number": 9,
                    "name": "writable"
                }
            ]
        }

    def check_is_block_device(self):
        print("\nChecking if it is block device...")
        if pathlib.Path(self.path).is_block_device():
            print("PASS: {} is a block device!".format(self.path))
        else:
            raise SystemExit("FAIL: {} is not a block device!"
                             .format(self.path))

    def check_disk(self):
        print("\nChecking Parted...")
        self.check_sector_size()
        self.check_partitions()

    def get_disk_information(self):
        print("\nGetting disk information in json")
        ret = runcmd(["genio-test-tool.parted {} print -j".format(self.path)])
        self.actual_result = json.loads(ret.stdout)["disk"]
        if self.path == "/dev/sdc":
            self.expected_result = self.expected_result_UFS
        elif self.path == "/dev/mmcblk0":
            self.expected_result = self.expected_result_EMMC
        else:
            raise SystemExit("ERROR: Unrecognized device name!")

    def check_sector_size(self):
        print("\nChecking Logical Sector Size...")
        try:
            if self.actual_result["logical-sector-size"] ==  \
                    self.expected_result["logical-sector-size"]:
                print("logical sector size: {}"
                      .format(self.actual_result["logical-sector-size"]))
                print("PASS: Logical sector size is correct!")
            else:
                raise SystemExit("FAIL: Logical sector size is incorrect!")
        except KeyError:
            raise SystemExit("ERROR: logical-sector-size is not found")
        print("\nChecking Physical Sector Size...")
        try:
            if self.actual_result["physical-sector-size"] == \
                    self.expected_result["physical-sector-size"]:
                print("physical sector size: {}"
                      .format(self.actual_result["physical-sector-size"]))
                print("PASS: Physical sector size is correct!")
            else:
                raise SystemExit("FAIL: Physical sector size is incorrect!")
        except KeyError:
            raise SystemExit("ERROR: physical-sector-size is not found")

    def check_partitions(self):
        print("\nChecking partitions...")
        try:
            actual_partitions = self.actual_result["partitions"]
            expected_partitions = self.expected_result["partitions"]
            if len(actual_partitions) != len(expected_partitions):
                raise SystemExit("ERROR: Partitions count is incorrect!")
            for actual_partition, expected_partition in \
                    zip(actual_partitions, expected_partitions):
                if actual_partition["number"] != expected_partition["number"]:
                    raise SystemExit("ERROR: Partition number is incorrect!")
                if actual_partition["name"] != expected_partition["name"]:
                    raise SystemExit("ERROR: Partition name is incorrect")
        except KeyError:
            raise SystemExit("ERROR: Partitions not found!")
        print("PASS: Paritions are correct!")

    def check_device(self, exit_when_check_fail):
        ret = runcmd("lsblk")
        if "sdc" in ret.stdout:
            print("device: ufs")
            print("path: /dev/sdc")
            print()
        elif "mmc" in ret.stdout:
            print("device: emmc")
            print("path: /dev/mmcblk0")
            print()
        elif exit_when_check_fail:
            raise SystemExit("ERROR: Cannot find sdc or mmcblk0 in dev")

    def main(self):
        parser = ArgumentParser(description="Check if the disk information\
                                            is correct")
        parser.add_argument('--path',
                            help='the device path for checking')
        parser.add_argument("--check_device_name",
                            help="To check the device name",
                            action="store_true")
        parser.add_argument("--exit_when_check_fail",
                            help="Exit with error code when the device check \
                                  failed",
                            action="store_true")
        args = parser.parse_args()
        if args.check_device_name:
            self.check_device(args.exit_when_check_fail)
            return
        self.path = args.path
        self.check_is_block_device()
        self.get_disk_information()
        self.check_disk()


if __name__ == '__main__':
    TestPartedBootDevice().main()
