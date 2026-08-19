#!/usr/bin/env python3
#
# Copyright 2026 Canonical Ltd.
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
Compare the VA-API profiles and entrypoints advertised by the driver
(vainfo) with the features declared in the DUT manifest.
"""

import argparse
import re
import sys
from collections import defaultdict
from subprocess import check_output, STDOUT

from checkbox_support.manifest import get_manifest

NAMESPACE = "com.canonical.certification"

DECODER_ENTRYPOINTS = (
    "VAEntrypointVLD",
    "VAEntrypointIZZ",
    "VAEntrypointIDCT",
    "VAEntrypointMoComp",
    "VAEntrypointDeblocking",
)

ENCODER_ENTRYPOINTS = (
    "VAEntrypointEncSlice",
    "VAEntrypointEncSliceLP",
    "VAEntrypointEncPicture",
    "VAEntrypointFEI",
)


def parse_vainfo_output(output):
    """Parse the 'Supported profile and entrypoints' section of vainfo."""
    profiles = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("VAProfile"):
            continue
        try:
            profile, entrypoint = line.split(":")
        except ValueError:
            continue
        profiles.append((profile.strip(), entrypoint.strip()))
    return profiles


def profile_to_feature_id(profile):
    """Turn 'VAProfileHEVCMain10' into 'hevc_main10'."""
    name = profile[len("VAProfile") :]
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    name = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", name)
    return name.lower()


def entrypoint_to_direction(entrypoint):
    """Return 'decoder', 'encoder' or None for non-codec entrypoints."""
    if entrypoint in DECODER_ENTRYPOINTS:
        return "decoder"
    if entrypoint in ENCODER_ENTRYPOINTS:
        return "encoder"
    return None


def get_supported_features(output):
    """
    Return one entry per (profile, direction) pair, mapping the manifest
    feature name to the list of entrypoints that advertise it.
    """
    features = defaultdict(lambda: {"entrypoints": []})
    for profile, entrypoint in parse_vainfo_output(output):
        direction = entrypoint_to_direction(entrypoint)
        if direction is None:
            continue
        feature = "has_{}_{}".format(profile_to_feature_id(profile), direction)
        entry = features[feature]
        entry["profile"] = profile_to_feature_id(profile)
        entry["profile_name"] = profile
        entry["direction"] = direction
        entry["entrypoints"].append(entrypoint)
    return features


def run_vainfo():
    return check_output(["vainfo"], universal_newlines=True, stderr=STDOUT)


def get_manifest_key(feature):
    return "{}::{}".format(NAMESPACE, feature)


def feature_declared(feature):
    manifest = get_manifest()
    return manifest.get(get_manifest_key(feature), False)


def cmd_resource():
    features = get_supported_features(run_vainfo())
    for feature, entry in sorted(features.items()):
        print("profile: {}".format(entry["profile"]))
        print("profile_name: {}".format(entry["profile_name"]))
        print(
            "entrypoints: {}".format(", ".join(sorted(entry["entrypoints"])))
        )
        print("direction: {}".format(entry["direction"]))
        print("feature: {}".format(feature))
        print()
    return 0


def cmd_forward(feature):
    if feature_declared(feature):
        print("OK: {} is declared as supported on this device".format(feature))
        return 0
    print(
        "ERROR: the VA driver advertises {} but this feature is not "
        "declared in the DUT manifest".format(feature)
    )
    return 1


def cmd_reverse():
    features = get_supported_features(run_vainfo())
    missing = []
    for key, value in sorted(get_manifest().items()):
        if not key.startswith(NAMESPACE + "::has_"):
            continue
        if not (key.endswith("_decoder") or key.endswith("_encoder")):
            continue
        if not value:
            continue
        feature = key.split("::", 1)[1]
        if feature not in features:
            missing.append(feature)
    if missing:
        print(
            "ERROR: the following features are declared in the DUT manifest "
            "but not supported by the VA driver:"
        )
        for feature in missing:
            print("  {}".format(feature))
        return 1
    print("OK: all manifest-declared features are supported by the VA driver")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Compare VA-API profiles advertised by vainfo with the features "
            "declared in the DUT manifest"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "resource", help="emit one resource record per (profile, direction)"
    )
    forward_parser = subparsers.add_parser(
        "forward", help="check that a feature is declared in the DUT manifest"
    )
    forward_parser.add_argument("feature")
    subparsers.add_parser(
        "reverse",
        help="check that all manifest-declared features are advertised",
    )
    args = parser.parse_args(argv)
    if args.command == "resource":
        return cmd_resource()
    if args.command == "forward":
        return cmd_forward(args.feature)
    if args.command == "reverse":
        return cmd_reverse()
    return 2


if __name__ == "__main__":
    sys.exit(main())
