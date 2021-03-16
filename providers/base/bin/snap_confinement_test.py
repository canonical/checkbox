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

import json
import logging
import sys
from checkbox_support.snap_utils.snapd import Snapd

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


def main():

    data = Snapd().get_system_info()

    confinement = data["confinement"]
    if confinement == "strict":
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
        logging.error("Cannot find '{}' in apparmor".format(missing_features))

    categories_to_check = ["mount", "udev"]
    for category in categories_to_check:
        if category not in sandbox_features:
            logging.error(
                "Cannot find '{}' in sandbox-features".format(category)
            )
            break
        for feature in sandbox_features[category]:
            if "cgroup-v2" in feature:
                logging.error("cgroup({}) must NOT be v2".format(feature))

    return sandbox_features_output


if __name__ == "__main__":
    sys.exit(main())
