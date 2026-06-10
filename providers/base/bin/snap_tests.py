#!/usr/bin/env python3
# Copyright 2015-2026 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Jonathan Cave <jonathan.cave@canonical.com>

import argparse
import logging
import os
import sys
from functools import wraps, partial

from checkbox_support.snap_utils.snapd import Snapd, AsyncException

# Requirements for the test snap:
#  - the snap must be strictly confined (no classic or devmode flags)
#  - there must be different revisions on the stable & edge channels
try:
    TEST_SNAP = os.environ["TEST_SNAP"]
except KeyError:
    runtime = os.getenv("CHECKBOX_RUNTIME", "/snap/checkbox/current")
    if "checkbox18" in runtime:
        TEST_SNAP = "test-snapd-tools-core18"
    elif "checkbox20" in runtime:
        TEST_SNAP = "test-snapd-tools-core20"
    elif "checkbox22" in runtime:
        TEST_SNAP = "test-snapd-tools-core22"
    elif "checkbox24" in runtime:
        TEST_SNAP = "test-snapd-tools-core24"
    # Uncomment once test-snapd-tools-core26 will have a stable version.
    # elif "checkbox26" in runtime:
    #     TEST_SNAP = "test-snapd-tools-core26"
    else:
        TEST_SNAP = "test-snapd-tools"
SNAPD_TASK_TIMEOUT = int(os.getenv("SNAPD_TASK_TIMEOUT", 30))
SNAPD_POLL_INTERVAL = int(os.getenv("SNAPD_POLL_INTERVAL", 1))

print = partial(print, flush=True)


def pretty_exit_async_exception(f):
    """
    Snapd functions raise AsyncException on failure. Users may assume that a
    traceback is a test issue. This gets rid of the traceback.
    """

    @wraps(f)
    def _f(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except AsyncException as e:
            raise SystemExit(str(e))

    return _f


def remove_if_present(snapd, snap_name):
    if snapd.list(TEST_SNAP):
        print(
            "Test snap '{}' is already installed. Removing it...".format(
                snap_name
            )
        )
        snapd.remove(TEST_SNAP)


def get_snapd_client():
    logger = logging.getLogger("snapd")
    logger.handlers.clear()
    # here we are printing to sys.stdout so that progress flushes the correct
    # stream
    handler = logging.StreamHandler(sys.stdout)
    # double space makes it easier to tell what is test progress and what is
    # logs
    handler.setFormatter(logging.Formatter("  (snapd) %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    return Snapd(SNAPD_TASK_TIMEOUT, SNAPD_POLL_INTERVAL, logger=logger)


class SnapList:
    """snap list sub-command."""

    def invoked(self):
        """snap list should show the core package is installed."""
        data = get_snapd_client().list()
        for snap in data:
            if snap["name"] in (
                "core",
                "core16",
                "core18",
                "core20",
                "core22",
                "core24",
            ):
                print("Found a core snap")
                print(snap["name"], snap["version"], snap["revision"])
                return 0
        return 1


class SnapSearch:
    """snap search sub-command."""

    def invoked(self):
        """snap search for TEST_SNAP."""
        data = get_snapd_client().find(
            TEST_SNAP,
        )
        for snap in data:
            print("ID:", snap["id"])
            print("Name:", snap["name"])
            print("Developer:", snap["developer"])
            return 0
        return 1


class SnapInstall:
    """snap install sub-command."""

    def invoked(self):
        """Test install of test-snapd-tools snap."""
        parser = argparse.ArgumentParser()
        parser.add_argument("channel", help="channel to install from")
        args = parser.parse_args(sys.argv[2:])
        s = get_snapd_client()
        remove_if_present(s, TEST_SNAP)
        print("Installing '{}'...".format(TEST_SNAP))
        s.install(TEST_SNAP, args.channel)
        print("Confirming '{}' is in the snap list...".format(TEST_SNAP))
        data = s.list()
        for snap in data:
            if snap["name"] == TEST_SNAP:
                print("Pass: Test snap is in the snap list")
                return 0
        print("Fail: '{}' is not in the snap list".format(TEST_SNAP))
        return 1


class SnapRefresh:
    """snap refresh sub-command."""

    def invoked(self):
        """Test refresh of test-snapd-tools snap."""
        s = get_snapd_client()
        remove_if_present(s, TEST_SNAP)
        print("Installing stable revision...")
        s.install(TEST_SNAP, "stable")
        start_rev = s.list(TEST_SNAP)["revision"]
        print("Stable revision is:", start_rev)
        print("Refreshing to edge...")
        s.refresh(TEST_SNAP, "edge")
        new_rev = s.list(TEST_SNAP)["revision"]
        print("New revision is:", new_rev)
        if new_rev == start_rev:
            print("Fail: Snap revision didn't change")
            return 1
        print("Pass: Snap revision changed")
        return 0


class SnapRevert:
    """snap revert sub-command."""

    def invoked(self):
        """Test revert of test-snapd-tools snap."""
        s = get_snapd_client()
        remove_if_present(s, TEST_SNAP)
        print("Installing stable revision...")
        s.install(TEST_SNAP)
        print("Refreshing to edge...")
        s.refresh(TEST_SNAP, "edge")
        print("Get stable channel revision from store...")
        r = s.info(TEST_SNAP)
        stable_rev = r["channels"]["latest/stable"]["revision"]
        r = s.list(TEST_SNAP)
        installed_rev = r["revision"]  # should be edge revision
        print("Reverting test snap '{}'...".format(TEST_SNAP))
        s.revert(TEST_SNAP)
        r = s.list(TEST_SNAP)
        rev = r["revision"]
        if rev != stable_rev:
            print(
                "Fail: Failed to revert to stable revision ({}), "
                "got: {}".format(stable_rev, rev)
            )
            return 1
        if rev == installed_rev:
            print("Fail: Failed to revert, revisions match ({})".format(rev))
            return 1
        print("Pass: Snap refreshed and reverted correctly")
        return 0


class SnapReupdate:
    """snap reupdate sub-command."""

    def invoked(self):
        """Test re-update of test-snapd-tools snap."""
        s = get_snapd_client()
        remove_if_present(s, TEST_SNAP)
        print("Get edge channel revision from store...")
        s.install(TEST_SNAP)
        s.refresh(TEST_SNAP, "edge")
        s.revert(TEST_SNAP)
        r = s.info(TEST_SNAP)
        edge_rev = r["channels"]["latest/edge"]["revision"]
        print("Removing edge revision...")
        s.remove(TEST_SNAP, edge_rev)
        print("Refreshing to edge channel...")
        s.refresh(TEST_SNAP, "edge")
        print("Getting new installed revision...")
        r = s.list(TEST_SNAP)
        rev = r["revision"]
        if rev != edge_rev:
            print(
                "Fail: Failed to refresh to edge, expected revision: {}"
                ", got {}".format(edge_rev, rev)
            )
            return 1
        print("Pass: Snap re-updated correctly")


class SnapRemove:
    """snap remove sub-command."""

    def invoked(self):
        """Test remove of test-snapd-tools snap."""
        s = get_snapd_client()
        if not s.list(TEST_SNAP):
            print("Test snap '{}' not found. Installing".format(TEST_SNAP))
            s.install(TEST_SNAP)
        print("Removing '{}'...".format(TEST_SNAP))
        s.remove(TEST_SNAP)
        data = s.list()
        for snap in data:
            if snap["name"] == TEST_SNAP:
                print("Fail: Snap '{}' found in snap list".format(TEST_SNAP))
                return 1
        print("Pass: Snap '{}' succesfully removed".format(TEST_SNAP))
        return 0


class Snap:
    """Fake snap like command."""

    @pretty_exit_async_exception
    def main(self):
        sub_commands = {
            "list": SnapList,
            "search": SnapSearch,
            "install": SnapInstall,
            "refresh": SnapRefresh,
            "revert": SnapRevert,
            "reupdate": SnapReupdate,
            "remove": SnapRemove,
        }
        parser = argparse.ArgumentParser()
        parser.add_argument("subcommand", type=str, choices=sub_commands)
        args = parser.parse_args(sys.argv[1:2])
        return sub_commands[args.subcommand]().invoked()


if __name__ == "__main__":
    sys.exit(Snap().main())
