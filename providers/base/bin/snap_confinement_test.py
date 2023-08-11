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


class SystemConfinement:
    """
    Check the confinement status and sandbox features of the system.

    Attributes:
        features_should_include (list): A list of sandbox features that
            must be present in the 'apparmor' category.
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

    def invoked(self):
        """
        Check the confinement and sandbox features of the system.

        This test checks if the system's confinement is 'strict'. If it
        is 'strict', the test passes; otherwise, it checks the presence
        of required features and prints out errors for any missing ones.

        Returns:
            str: A detailed output of the system's confinement and
                 sandbox features in JSON format.
        """
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
            for feature in self.features_should_include:
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


class SnapsConfinement:
    """
    Test the confinement status of all installed snaps.

    Attributes:
        whitelist_snaps (list): A list of snap names or regex patterns
            that are exempted from the confinement check.
    """

    whitelist_snaps = [
        "bugit",
        r"checkbox.*",
        "mir-test-tools",
        "graphics-test-tools",
    ]

    def invoked(self):
        """
        Check the confinement of all snaps installed in the system.

        A snap confinement should be 'strict', devmode should be False,
        and should not have a sideloded revision starts with 'x'.

        Returns:
            int: Exit code. 0 if the test passes for all snaps,
                 otherwise 1.
        """
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

            if any(
                re.match(pattern, snap_name)
                for pattern in self.whitelist_snaps
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
        "system": SystemConfinement,
        "snaps": SnapsConfinement,
    }
    parser = argparse.ArgumentParser()
    parser.add_argument("subcommand", type=str, choices=sub_commands)
    args = parser.parse_args(sys.argv[1:2])
    return sub_commands[args.subcommand]().invoked()


if __name__ == "__main__":
    sys.exit(main())
