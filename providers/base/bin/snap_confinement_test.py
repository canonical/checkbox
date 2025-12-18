#!/usr/bin/env python3
# Copyright 2021 - 2024 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Patrick Liu <patrick.liu@canonical.com>
#    Patrick Chang <patrick.chang@canonical.com>
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
import os
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
        print('System confinement is "strict"')
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
        logging.error("Cannot find '%s' in apparmor", missing_features)

    categories_to_check = ["mount", "udev"]
    for category in categories_to_check:
        if category not in sandbox_features:
            logging.error("Cannot find '%s' in sandbox-features", category)
            break
        for feature in sandbox_features[category]:
            if "cgroup-v2" in feature:
                logging.error("cgroup(%s) must NOT be v2", feature)

    return sandbox_features_output


class SnapsConfinementVerifier:
    """
    Test the confinement status of all installed snaps.

    A snap's confinement should be 'strict', devmode should be False,
    and it should not have a sideloaded revision that starts with 'x'.

    Attributes:
        _official_allowlist (list): A list of regex patterns exempted from
            the confinement check. Snaps matching these patterns will be
            excluded from the test. Customize this list to define specific
            snaps that should be ignored based on their names or patterns.

        _allowlist_from_config_var (list): A list of snap names
            from the SNAP_CONFINEMENT_ALLOWLIST environment variable.
            Snaps matching these patterns will be excluded from the test.

        _desired_attributes (list): A list of attributes of a snap that
            are of interest for testing. The attributes include "name",
            "confinement", "devmode", and "revision".

    Methods:
        _is_snap_in_allow_list(snap_name: str) -> bool:
            Check if a snap is in the allowlist.

        _is_snap_confinement_not_strict(snap_confinement: str) -> bool:
            Check if a snap's confinement is not 'strict'.

        _is_snap_devmode(snap_devmode: bool) -> bool:
            Check if a snap is in devmode.

        _is_snap_sideloaded_revision(snap_revision: str) -> bool:
            Check if a snap has a sideloaded revision starting with 'x'.

        _extract_attributes_from_snap(target_snap: dict) -> (bool, dict):
            Extract desired attributes from a snap's information.

        verify_snap() -> int:
            Perform the snap verification test on all installed snaps.
            Returns the exit code: 0 if the test passes for all snaps,
            otherwise 1.
    """

    def __init__(self) -> None:
        self._official_allowlist = [
            r"^bugit$",
            r"checkbox.*",
            r"^mir-test-tools$",
            r"^graphics-test-tools$",
        ]
        self._allowlist_from_config_var = [
            element.strip()
            for element in os.environ.get(
                "SNAP_CONFINEMENT_ALLOWLIST", ""
            ).split(",")
        ]
        # Define the attributes of snap we are interested in.
        self._desired_attributes = [
            "name",
            "confinement",
            "devmode",
            "revision",
        ]

    def _is_snap_in_allow_list(self, snap_name: str) -> bool:
        if snap_name in self._allowlist_from_config_var:
            logging.warning(
                "This snap is included in the SNAP_CONFINEMENT_ALLOWLIST"
                " environment variable, a tester defined checkbox config_var."
            )
            logging.info("Result: Skip")
            return True
        elif any(
            re.match(pattern, snap_name)
            for pattern in self._official_allowlist
        ):
            logging.warning("This snap is officially defined in the allowlist")
            logging.info("Result: Skip")
            return True
        return False

    def _is_snap_confinement_not_strict(self, snap_confinement: str) -> bool:
        if snap_confinement != "strict":
            logging.error(
                "confinement is expected to be 'strict' but got '{}'".format(
                    snap_confinement
                )
            )
            return True
        return False

    def _is_snap_devmode(self, snap_devmode: bool) -> bool:
        if snap_devmode:
            logging.error("devmode is expected to be 'False' but got 'True'")
            return True
        return False

    def _is_snap_sideloaded_revision(self, snap_revision: str) -> bool:
        if snap_revision and snap_revision.startswith("x"):
            logging.error(
                "sideloaded revision is '{}', which is not allowed".format(
                    snap_revision
                )
            )
            return True
        return False

    def _extract_attributes_from_snap(self, target_snap: dict) -> (bool, dict):
        return_dict = {}
        has_error = False
        for attr in self._desired_attributes:
            value = target_snap.get(attr)
            if value is None:
                has_error = True
                logging.error(
                    "Snap '{}' not found in the snap data.".format(attr)
                )
                continue
            return_dict.update({attr: value})
        return has_error, return_dict

    def verify_snap(self) -> bool:
        exit_code = 0
        snaps_information = Snapd().list()
        for snap_info in snaps_information:
            tmp_exit_code = 0
            has_error, snap_dict = self._extract_attributes_from_snap(
                target_snap=snap_info
            )
            if has_error:
                # Mark as fail and skip current snap's checking
                # if any desired attribute is missing
                exit_code = 1
                continue

            logging.info(
                "=== Checking Snap: {} ===".format(snap_dict.get("name"))
            )

            # Skip if target snap in allow list
            if self._is_snap_in_allow_list(snap_dict.get("name")):
                continue

            tmp_exit_code |= self._is_snap_confinement_not_strict(
                snap_dict.get("confinement")
            )
            tmp_exit_code |= self._is_snap_devmode(snap_dict.get("devmode"))
            tmp_exit_code |= self._is_snap_sideloaded_revision(
                snap_dict.get("revision")
            )

            logging.info(
                "Result: {}".format("Fail" if tmp_exit_code else "Pass")
            )

            exit_code |= tmp_exit_code
        return exit_code


def main():
    logging.basicConfig(
        format="%(levelname)s: %(message)s", level=logging.INFO
    )
    sub_commands = {
        "system": test_system_confinement,
        "snaps": SnapsConfinementVerifier().verify_snap,
    }
    parser = argparse.ArgumentParser()
    parser.add_argument("subcommand", type=str, choices=sub_commands)
    args = parser.parse_args()
    return sub_commands[args.subcommand]()


if __name__ == "__main__":
    sys.exit(main())
