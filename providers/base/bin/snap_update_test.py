#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Patrick Liu <patrick.liu@canonical.com>
#    Pierre Equoy <pierre.equoy@canonical.com>
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
from glob import glob
import json
import logging
import os.path
import sys
import time

from checkbox_support.snap_utils.snapd import Snapd


def guess_snaps() -> dict:
    """
    Guess the names of the kernel, snapd and gadget snaps from installed snaps
    on the system.

    :return: a dict with the snap names for each snap found
    :rtype: dict
    """
    snapd = Snapd()
    installed_snaps = snapd.list()
    snaps = {}
    for snap in installed_snaps:
        if snap["type"] == "kernel":
            snaps["kernel"] = snap["name"]
        elif snap["type"] == "gadget":
            snaps["gadget"] = snap["name"]
        elif snap["type"] == "snapd":
            snaps["snapd"] = snap["name"]
    return snaps


def get_snap_base_rev() -> dict:
    """
    Retrieve the name and the base revision of each snap originally installed
    on the system.

    :return: a dict containing the snap names and their base revisions
    :rtype: dict
    """
    base_snaps = glob("/var/lib/snapd/seed/snaps/*.snap")
    base_rev_info = {}
    for snap_path in base_snaps:
        snap_basename = os.path.basename(snap_path)
        snap_name = os.path.splitext(snap_basename)[0]
        snap, rev = snap_name.rsplit("_", maxsplit=1)
        base_rev_info[snap] = rev
    return base_rev_info


def get_snap_info(name) -> dict:
    """
    Retrieve information such as name, type, available revisions, etc. about
    a given snap.

    :return: a dict with the available information
    :rtype: dict
    """
    snapd = Snapd()
    snap_info = {}
    snap = snapd.list(name)
    base_revs = get_snap_base_rev()
    snap_info["name"] = snap["name"]
    snap_info["type"] = snap["type"]
    snap_info["tracking_channel"] = snap["tracking-channel"]
    snap_info["installed_revision"] = snap["revision"]
    snap_info["base_revision"] = base_revs.get(name, "")
    tracking = snap_info["tracking_channel"]
    prefix = (tracking.split("/")[0] + "/") if "/" in tracking else ""
    snap_info["tracking_prefix"] = prefix

    snap_additional_info = snapd.find(name, exact=True)
    snap_info["revisions"] = {}
    for item in snap_additional_info:
        for channel, info in item["channels"].items():
            snap_info["revisions"][channel] = info["revision"]
    return snap_info


def print_resource_info():
    snaps = guess_snaps().values()
    for snap in snaps:
        info = get_snap_info(snap)
        tracking = info["tracking_channel"]
        prefix = info["tracking_prefix"]
        base_rev = info.get("base_revision", "")
        stable_rev = info["revisions"].get("{}stable".format(prefix), "")
        cand_rev = info["revisions"].get("{}candidate".format(prefix), "")
        beta_rev = info["revisions"].get("{}beta".format(prefix), "")
        edge_rev = info["revisions"].get("{}edge".format(prefix), "")
        installed_rev = info.get("installed_revision", "")

        print("name: {}".format(info["name"]))
        print("type: {}".format(info["type"]))
        print("tracking: {}".format(tracking))
        print("base_rev: {}".format(base_rev))
        print("stable_rev: {}".format(stable_rev))
        print("candidate_rev: {}".format(cand_rev))
        print("beta_rev: {}".format(beta_rev))
        print("edge_rev: {}".format(edge_rev))
        print("original_installed_rev: {}".format(installed_rev))
        print()


class SnapRefreshRevert:
    def __init__(self, name, rev, info_path):
        self.snapd = Snapd()
        self.snap_info = get_snap_info(name)
        self.path = info_path
        self.rev = rev
        self.name = name

    def snap_refresh(self):
        data = {}
        original_revision = self.snap_info["installed_revision"]
        if original_revision == self.rev:
            logging.error(
                "Trying to refresh to the same revision (%s)!", self.rev
            )
            return 1
        data["name"] = self.name
        data["original_revision"] = original_revision
        data["destination_revision"] = self.rev
        logging.info(
            "Refreshing %s snap from rev %s to rev %s",
            self.name,
            original_revision,
            self.rev,
        )
        r = self.snapd.refresh(
            self.name,
            channel=self.snap_info["tracking_channel"],
            revision=self.rev,
            reboot=True,
        )
        logging.info(
            "Refreshing requested (channel %s, rev %s)",
            self.snap_info["tracking_channel"],
            self.rev,
        )
        with open(self.path, "w") as file:
            data["refresh_id"] = r["change"]
            json.dump(data, file)
        logging.info("Waiting for reboot...")
        return 0

    def verify_refresh(self):
        try:
            with open(self.path, "r") as file:
                data = json.load(file)
        except FileNotFoundError:
            logging.error("File not found: %s", self.path)
            logging.error("Did the previous job run as expected?")
            return 1
        id = data["refresh_id"]
        name = data["name"]

        logging.info("Checking refresh status for snap %s...", name)
        start_time = time.time()
        timeout = 300  # 5 minutes timeout
        while True:
            result = self.snapd.change(str(id))
            if result == "Done":
                logging.info("%s snap refresh complete", name)
                break

            if time.time() - start_time >= timeout:
                logging.error(
                    "%s snap refresh did not complete within 5 minutes", name
                )
                return False
            logging.info("Waiting for %s snap refreshing to be done...", name)
            logging.info("Trying again in 10 seconds...")
            time.sleep(10)

        current_rev = self.snapd.list(self.snap_info["name"])["revision"]
        destination_rev = data["destination_revision"]
        if current_rev != destination_rev:
            logging.error(
                "Current revision %s is NOT equal to expected revision %s",
                current_rev,
                destination_rev,
            )
            return 1
        else:
            logging.info(
                "PASS: current revision (%s) matches the expected revision",
                current_rev,
            )
        return 0

    def snap_revert(self):
        with open(self.path, "r") as file:
            data = json.load(file)
        original_rev = data["original_revision"]
        destination_rev = data["destination_revision"]
        logging.info(
            "Reverting %s snap (from rev %s to rev %s)",
            self.name,
            destination_rev,
            original_rev,
        )
        r = self.snapd.revert(self.snap_info["name"], reboot=True)
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

        logging.info("Checking %s snap revert status", self.name)
        start_time = time.time()
        timeout = 300  # 5 minutes timeout
        while True:
            result = self.snapd.change(str(id))
            if result == "Done":
                logging.info("%s snap revert complete", self.name)
                break

            if time.time() - start_time >= timeout:
                logging.error(
                    "%s snap revert did not complete within 5 minutes",
                    self.name,
                )
                return False
            logging.info(
                "Waiting for %s snap reverting to be done...", self.name
            )
            logging.info("Trying again in 10 seconds.")
            time.sleep(10)

        current_rev = self.snapd.list(self.snap_info["name"])["revision"]
        if current_rev != original_rev:
            logging.error(
                "Current revision (%s) is NOT equal to original revision (%s)",
                current_rev,
                original_rev,
            )
            return 1
        else:
            logging.info(
                "PASS: current revision (%s) matches the original revision",
                current_rev,
            )
        return 0


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "name", nargs="?", default="", help="Name of the snap to act upon"
    )
    parser.add_argument(
        "--resource",
        action="store_true",
        help="Gather information about kernel, snapd and gadget snaps",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh the given snap",
    )
    parser.add_argument(
        "--verify-refresh",
        action="store_true",
        help="Verify revision after refreshing the given snap",
    )
    parser.add_argument(
        "--revert",
        action="store_true",
        help="Revert the given snap",
    )
    parser.add_argument(
        "--verify-revert",
        action="store_true",
        help="Verify revision after reverting the given snap",
    )
    parser.add_argument(
        "--info-path",
        help="Path to the information file",
    )
    parser.add_argument(
        "--rev",
        help="Revision to refresh to",
    )

    args = parser.parse_args()

    if args.resource:
        print_resource_info()
    else:
        test = SnapRefreshRevert(
            name=args.name, info_path=args.info_path, rev=args.rev
        )
        if args.refresh:
            return test.snap_refresh()
        if args.verify_refresh:
            return test.verify_refresh()
        if args.revert:
            return test.snap_revert()
        if args.verify_revert:
            return test.verify_revert()


if __name__ == "__main__":
    sys.exit(main())
