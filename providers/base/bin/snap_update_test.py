#!/usr/bin/env python3
# Copyright 2023-2024 Canonical Ltd.
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
from pathlib import Path
import json
import os
import sys
import time

from checkbox_support.snap_utils.snapd import Snapd
from checkbox_support.snap_utils.snapd import AsyncException
from checkbox_support.snap_utils.snapd import SnapdRequestError


def guess_snaps() -> list:
    """
    Guess the names of the kernel, snapd and gadget snaps from installed snaps
    on the system.

    :return: a list of snap names that are either kernel, snapd or gadget snaps
    :rtype: list
    """
    snaps = [
        snap["name"]
        for snap in Snapd().list()
        if snap["type"] in ("kernel", "gadget", "snapd")
    ]
    return snaps


def get_snaps_base_rev() -> dict:
    """
    Retrieve the name and the base revision of each snap originally installed
    on the system.

    :return: a dict containing the snap names and their base revisions
    :rtype: dict
    """
    seed_snaps_dir = Path("/var/lib/snapd/seed/snaps/")
    base_snaps = seed_snaps_dir.glob("*.snap")
    base_rev_info = {}
    for snap_path in base_snaps:
        snap, rev = snap_path.stem.rsplit("_", maxsplit=1)
        base_rev_info[snap] = rev
    return base_rev_info


class SnapInfo:
    def __init__(self, name):
        snap = Snapd().list(name)
        self.name = snap["name"]
        self.type = snap["type"]
        self.tracking_channel = snap["tracking-channel"]
        self.installed_revision = snap["revision"]
        self.tracking_prefix = (
            (self.tracking_channel.split("/")[0] + "/")
            if "/" in self.tracking_channel
            else ""
        )
        self.base_revision = get_snaps_base_rev().get(name, "")

        revisions = {}
        for item in Snapd().find(name, exact=True):
            for channel, info in item["channels"].items():
                revisions[channel] = info["revision"]

        self.stable_revision = revisions.get(
            "{}stable".format(self.tracking_prefix), ""
        )
        self.candidate_revision = revisions.get(
            "{}candidate".format(self.tracking_prefix), ""
        )
        self.beta_revision = revisions.get(
            "{}beta".format(self.tracking_prefix), ""
        )
        self.edge_revision = revisions.get(
            "{}edge".format(self.tracking_prefix), ""
        )

    def print_as_resource(self):
        print("name: {}".format(self.name))
        print("type: {}".format(self.type))
        print("tracking: {}".format(self.tracking_channel))
        print("base_rev: {}".format(self.base_revision))
        print("stable_rev: {}".format(self.stable_revision))
        print("candidate_rev: {}".format(self.candidate_revision))
        print("beta_rev: {}".format(self.beta_revision))
        print("edge_rev: {}".format(self.edge_revision))
        print("original_installed_rev: {}".format(self.installed_revision))
        print()


def print_resource_info():
    for snap in guess_snaps():
        SnapInfo(snap).print_as_resource()


def save_change_info(path, data):
    with open(path, "w") as file:
        json.dump(data, file)


def load_change_info(path):
    try:
        with open(path, "r") as file:
            data = json.load(file)
    except FileNotFoundError:
        error_msg = "File not found: {}. Did the previous job run as expected?"
        raise SystemExit(error_msg.format(path))
    return data


class SnapRefreshRevert:
    def __init__(self, name, revision, info_path, timeout):
        self.timeout = timeout
        self.snapd = Snapd(task_timeout=self.timeout, verbose=True)
        self.snap_info = SnapInfo(name)
        self.path = info_path
        self.revision = revision
        self.name = name

    def snap_refresh(self):
        data = {}
        original_revision = self.snap_info.installed_revision
        if original_revision == self.revision:
            error_msg = "Trying to refresh to the same revision ({})!"
            raise SystemExit(error_msg.format(self.revision))
        data["name"] = self.name
        data["original_revision"] = original_revision
        data["destination_revision"] = self.revision
        print(
            "Refreshing snap {} from revision {} to {}".format(
                self.name, original_revision, self.revision
            )
        )
        try:
            response = self.snapd.refresh(
                self.name,
                channel=self.snap_info.tracking_channel,
                revision=self.revision,
            )
        except (SnapdRequestError, AsyncException) as exc:
            checkbox_session_dir = os.getenv("PLAINBOX_SESSION_SHARE")
            if checkbox_session_dir:
                result = {
                    "outcome": "fail",
                    "comments": "Marking the test as failed because it raised the following:"
                    + str(exc),
                }
                result_filename = os.path.join(
                    checkbox_session_dir, "__result"
                )
                with open(result_filename, "wt") as result_f:
                    json.dump(result, result_f)
            raise
        data["change_id"] = response["change"]
        print(
            "Snap operation finished. "
            "See `snap change {}` for more info".format(response["change"])
        )
        save_change_info(self.path, data)
        print("Waiting for reboot...")

    def snap_revert(self):
        data = load_change_info(self.path)
        original_rev = data["original_revision"]
        destination_rev = data["destination_revision"]
        print(
            "Reverting snap {} from revision {} to {}".format(
                self.name, destination_rev, original_rev
            )
        )
        try:
            response = self.snapd.revert(self.name)
        except (SnapdRequestError, AsyncException) as exc:
            checkbox_session_dir = os.getenv("PLAINBOX_SESSION_SHARE")
            if checkbox_session_dir:
                result = {
                    "outcome": "fail",
                    "comments": exc.message,
                }
                result_filename = os.path.join(
                    checkbox_session_dir, "__result"
                )
                with open(result_filename, "wt") as result_f:
                    json.dump(result, result_f)
            raise
        data["change_id"] = response["change"]
        print(
            "Snap operation finished. "
            "See `snap change {}` for more info".format(response["change"])
        )
        save_change_info(self.path, data)
        print("Waiting for reboot...")

    def wait_for_snap_change(self, change_id, type):
        start_time = time.time()
        while True:
            result = self.snapd.change(str(change_id))
            if result == "Done":
                print("{} snap {} complete".format(self.name, type))
                return
            elif result == "Error":
                tasks = self.snapd.tasks(str(change_id))
                for task in tasks:
                    print(
                        "{} | {} | {}".format(
                            task["id"], task["status"], task["summary"]
                        )
                    )
                    if task.get("log"):
                        for log in task["log"]:
                            print("\t {}".format(log))
                raise SystemExit(
                    "Error during snap {} {}.".format(self.name, type)
                )

            current_time = time.time()
            if current_time - start_time >= self.timeout:
                raise SystemExit(
                    "{} snap {} did not complete within {} seconds".format(
                        self.name, type, self.timeout
                    )
                )
            print(
                "Waiting for {} snap {} to be done...".format(self.name, type)
            )
            print("Trying again in 10 seconds...")
            time.sleep(10)

    def verify(self, type):
        print("Beginning verify...")
        if type not in ("refresh", "revert"):
            msg = (
                "'{}' verification unknown. Can be either 'refresh' "
                "or 'revert'."
            ).format(type)
            raise SystemExit(msg)
        data = load_change_info(self.path)
        id = data["change_id"]
        self.wait_for_snap_change(id, type)
        print("Checking {} status for snap {}...".format(type, self.name))

        current_rev = self.snapd.list(self.name)["revision"]
        if type == "refresh":
            tested_rev = data["destination_revision"]
        else:
            tested_rev = data["original_revision"]
        if current_rev != tested_rev:
            msg = (
                "Current revision ({}) is different from expected revision "
                "({})"
            ).format(current_rev, tested_rev)
            raise SystemExit(msg)
        else:
            print(
                "PASS: current revision ({}) matches the expected "
                "revision".format(current_rev)
            )


def main(args):
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
        "--revision",
        help="Revision to refresh to",
    )
    parser.add_argument(
        "--timeout",
        default=600,
        help="Timeout for each task, in seconds (default: %(default)s))",
    )

    args = parser.parse_args(args)

    if args.resource:
        print_resource_info()
    else:
        test = SnapRefreshRevert(
            name=args.name,
            info_path=args.info_path,
            revision=args.revision,
            timeout=args.timeout,
        )
        if args.refresh:
            test.snap_refresh()
        if args.verify_refresh:
            test.verify("refresh")
        if args.revert:
            test.snap_revert()
        if args.verify_revert:
            test.verify("revert")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
