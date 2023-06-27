#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Patrick Liu <patrick.liu@canonical.com>
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
import json
import logging
import sys
import time

from checkbox_support.snap_utils.snapd import Snapd


class KernelSnapTest:
    def __init__(self, info_path):
        self.snapd = Snapd()
        self.kernel_info = self.get_kernel_info()
        self.path = info_path

    def get_kernel_info(self):
        kernel_info = {}
        installed_snaps = self.snapd.list()
        for item in installed_snaps:
            if item["type"] == "kernel":
                kernel_info["name"] = item["name"]
                kernel_info["tracking_channel"] = item["tracking-channel"]
                kernel_info["installed_revision"] = item["revision"]
        tracking = kernel_info["tracking_channel"]
        prefix = (tracking.split("/")[0] + "/") if "/" in tracking else ""
        kernel_info["tracking_prefix"] = prefix

        snap_info = self.snapd.find(kernel_info["name"], exact=True)
        kernel_info["revisions"] = {}
        for item in snap_info:
            for channel, info in item["channels"].items():
                kernel_info["revisions"][channel] = info["revision"]
        return kernel_info

    def kernel_refresh(self):
        data = {}
        original_revision = self.kernel_info["installed_revision"]
        data["original_revision"] = original_revision
        channel = "{}stable".format(self.kernel_info["tracking_prefix"])
        stable_rev = self.kernel_info["revisions"].get(channel, "")
        logging.info(
            "Refreshing kernel snap to stable (from rev %s to rev %s)",
            original_revision,
            stable_rev,
        )
        r = self.snapd.refresh(
            self.kernel_info["name"], channel=channel, reboot=True
        )
        logging.info("Refreshing requested")
        with open(self.path, "w") as file:
            data["refresh_id"] = r["change"]
            json.dump(data, file)
        logging.info("Waiting for reboot...")

    def verify_refresh(self):
        with open(self.path, "r") as file:
            data = json.load(file)
        id = data["refresh_id"]

        logging.info("Checking kernel refresh status")
        start_time = time.time()
        timeout = 300  # 5 minutes timeout
        while True:
            result = self.snapd.change(str(id))
            if result == "Done":
                logging.info("Kernel refresh is complete")
                break

            if time.time() - start_time >= timeout:
                logging.error(
                    "Kernel refresh did not complete within 5 minutes"
                )
                return False
            logging.info(
                "Waiting for kernel refreshing to be done..."
                "trying again in 10 seconds"
            )
            time.sleep(10)

        current_rev = self.snapd.list(self.kernel_info["name"])["revision"]
        channel = "{}stable".format(self.kernel_info["tracking_prefix"])
        stable_rev = self.kernel_info["revisions"][channel]
        if current_rev != stable_rev:
            logging.error(
                "Current revision %s is NOT equal to stable revision %s",
                current_rev,
                stable_rev,
            )
            return False
        else:
            logging.info(
                "PASS: current revision matches the stable channel revision"
            )
        return True

    def kernel_revert(self):
        with open(self.path, "r") as file:
            data = json.load(file)
        original_rev = data["original_revision"]
        channel = "{}stable".format(self.kernel_info["tracking_prefix"])
        stable_rev = self.kernel_info["revisions"].get(channel, "")
        logging.info(
            "Reverting kernel snap (from rev %s to rev %s)",
            stable_rev,
            original_rev,
        )
        r = self.snapd.revert(self.kernel_info["name"], reboot=True)
        logging.info("Reverting requested")
        with open(self.path, "w") as file:
            data["revert_id"] = r["change"]
            json.dump(data, file)
        logging.info("Waiting for reboot...")

    def verify_revert(self):
        with open(self.path, "r") as file:
            data = json.load(file)
        id = data["revert_id"]
        original_rev = data["original_revision"]

        logging.info("Checking kernel revert status")
        start_time = time.time()
        timeout = 300  # 5 minutes timeout
        while True:
            result = self.snapd.change(str(id))
            if result == "Done":
                logging.info("Kernel revert is complete")
                break

            if time.time() - start_time >= timeout:
                logging.error(
                    "Kernel revert did not complete within 5 minutes"
                )
                return False
            logging.info(
                "Waiting for kernel reverting to be done..."
                "trying again in 10 seconds"
            )
            time.sleep(10)

        current_rev = self.snapd.list(self.kernel_info["name"])["revision"]
        if current_rev != original_rev:
            logging.error(
                "Current revision %s is NOT equal to original revision %s",
                current_rev,
                original_rev,
            )
            return False
        else:
            logging.info(
                "PASS: current revision matches the original revision"
            )
        return True

    def print_resource_info(self):
        info = self.get_kernel_info()
        tracking = info["tracking_channel"]

        prefix = self.kernel_info["tracking_prefix"]
        stable_rev = info["revisions"].get("{}stable".format(prefix), "")
        cand_rev = info["revisions"].get("{}candidate".format(prefix), "")
        beta_rev = info["revisions"].get("{}beta".format(prefix), "")
        edge_rev = info["revisions"].get("{}edge".format(prefix), "")
        installed_rev = info.get("installed_revision", "")

        print("kernel_name: {}".format(info["name"]))
        print("tracking: {}".format(tracking))
        print("stable_rev: {}".format(stable_rev))
        print("candidate_rev: {}".format(cand_rev))
        print("beta_rev: {}".format(beta_rev))
        print("edge_rev: {}".format(edge_rev))
        print("original_installed_rev: {}".format(installed_rev))


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resource",
        action="store_true",
        help="Refresh kernel snap",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh kernel snap",
    )
    parser.add_argument(
        "--verify-refresh",
        action="store_true",
        help="Verify revision after refreshing kernel",
    )
    parser.add_argument(
        "--revert",
        action="store_true",
        help="Revert kernel snap",
    )
    parser.add_argument(
        "--verify-revert",
        action="store_true",
        help="Verify revision after reverting kernel",
    )
    parser.add_argument(
        "--info-path",
        help="Path to the information file",
    )

    args = parser.parse_args()
    info_path = args.info_path
    test = KernelSnapTest(info_path)

    exit_code = 0
    if args.resource:
        test.print_resource_info()
    if args.refresh:
        if not test.kernel_refresh():
            exit_code = 1
    if args.verify_refresh:
        if not test.verify_refresh():
            exit_code = 1
    if args.revert:
        if not test.kernel_revert():
            exit_code = 1
    if args.verify_revert:
        if not test.verify_revert():
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
