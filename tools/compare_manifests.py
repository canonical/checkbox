#!/usr/bin/env python3

import argparse
import json
import sys


def open_json(json_file: str) -> list[str]:
    json_data = []
    with open(json_file) as fp:
        json_data = json.load(fp)
    return json_data


def diff_manifests(manifest1: list[dict], manifest2: list[dict]) -> list[str]:
    """
    Return a list of hidden manifests that are present in manifest2 but not in
    manifest1.
    """
    return [
        k["name"]
        for k in manifest2
        if k not in manifest1
        if "::_" in k["name"]
    ]


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest1", help="Path to first manifest json file.")
    parser.add_argument("manifest2", help="Path to second manifest json file.")
    args = parser.parse_args(args)
    manifest1 = open_json(args.manifest1)
    manifest2 = open_json(args.manifest2)
    print(" ".join(diff_manifests(manifest1, manifest2)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
