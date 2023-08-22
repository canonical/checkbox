#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
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
import re
import sys
from checkbox_support.snap_utils.snapd import Snapd


def test_system_confinement():
    """
    Test the system's confinement and sandbox features.

    This test checks if the system's confinement is 'strict'. If it
    is 'strict', the test passes; otherwise, it checks the presence
    of required features and prints out errors for any missing ones.

    Variables:
        features_should_include (list): A list of sandbox features that
            must be present in the 'apparmor' category.
    Returns:
        str: A detailed output of the system's confinement and
             sandbox features in JSON format.
    """
    features_should_include = [
        "kernel:caps",
        "kernel:dbus",
        "kernel:domain",
        "kernel:file",
        "kernel:mount",
        "kernel:namespaces",
        "kernel:network",
        "kernel:ptrace",
        "kernel:signal",
        "parser:unsafe",
    ]

    data = Snapd().get_system_info()

    confinement = data["confinement"]
    if confinement == "strict":
        print("System confinement is \"strict\"")
        print("Test PASS")
        return 0

    sandbox_features = data["sandbox-features"]
    sandbox_features_output = (
        "\nOUTPUT: confinement: {}\nOUTPUT: sandbox-features:\n{}".format(
            confinement, json.dumps(sandbox_features, indent=2)
        )
    )

    missing_features = []
    if "apparmor" not in sandbox_features:
        logging.error("Cannot find 'apparmor' in sandbox-features")
    else:
        for feature in features_should_include:
            if feature not in sandbox_features["apparmor"]:
                missing_features.append(feature)

    if missing_features:
        logging.error(
            "Cannot find '%s' in apparmor", missing_features
        )

    categories_to_check = ["mount", "udev"]
    for category in categories_to_check:
        if category not in sandbox_features:
            logging.error(
                "Cannot find '%s' in sandbox-features", category
            )
            break
        for feature in sandbox_features[category]:
            if "cgroup-v2" in feature:
                logging.error("cgroup(%s) must NOT be v2", feature)

    return sandbox_features_output


def test_snaps_confinement():
    """
    Test the confinement status of all installed snaps.

    A snap confinement should be 'strict', devmode should be False,
    and should not have a sideloaded revision starts with 'x'.

    Variables:
        allowlist_snaps (list): A list of snap names or regex patterns
            that are exempted from the confinement check. To match the
            entire snap name, use the pattern "^<snap_name>$". For
            example, "bugit" matches only "bugit". To match multiple
            snaps with similar names, use ".*" suffixes. For instance,
            "checkbox.*" matches all snap names starting with "checkbox".
            Customize this list to exclude specific snaps from the
            confinement checks based on their names or patterns.
    Returns:
            int: Exit code. 0 if the test passes for all snaps,
                 otherwise 1.
    """
    allowlist_snaps = [
        r"^bugit$",
        r"checkbox.*",
        r"^mir-test-tools$",
        r"^graphics-test-tools$",
    ]

    data = Snapd().list()
    exit_code = 0
    for snap in data:
        snap_name = snap.get("name")
        snap_confinement = snap.get("confinement")
        snap_devmode = snap.get("devmode")
        snap_revision = snap.get("revision")

        if snap_name is None:
            logging.error("Snap 'name' not found in the snap data.")
            exit_code = 1
            continue  # Skipping following checks if snap_name not found

        if any(
            re.match(pattern, snap_name)
            for pattern in allowlist_snaps
        ):
            print("Skipping whitelisted snap: {}".format(snap_name))
            continue

        if snap_confinement != "strict":
            exit_code = 1
            logging.error(
                "Snap '%s' confinement is expected to be 'strict' "
                "but got '%s'", snap_name, snap_confinement,
            )

        if snap_devmode is not False:
            exit_code = 1
            logging.error(
                "Snap '%s' devmode is expected to be False but "
                "got '%s'", snap_name, snap_devmode,
            )

        if snap_revision and snap_revision.startswith("x"):
            exit_code = 1
            logging.error(
                "Snap '%s' has sideloaded revision '%s', which "
                "is not allowed", snap_name, snap_revision,
            )
        elif snap_revision is None:
            exit_code = 1
            logging.error(
                "'revision' not found in snap '%s'", snap_name,
            )
    return exit_code


def main():
    logging.basicConfig(format='%(levelname)s: %(message)s')
    sub_commands = {
        "system": test_system_confinement,
        "snaps": test_snaps_confinement,
    }
    parser = argparse.ArgumentParser()
    parser.add_argument("subcommand", type=str, choices=sub_commands)
    args = parser.parse_args()
    return sub_commands[args.subcommand]()


if __name__ == "__main__":
    sys.exit(main())
