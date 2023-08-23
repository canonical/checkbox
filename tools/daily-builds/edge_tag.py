#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Pierre Equoy <pierre.equoy@canonical.com>
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

import subprocess
import sys


def get_last_release_tag() -> str:
    """
    Use git to get the last release tag.

    A release tag is a tag that starts with a "v" and does not contain the
    word "edge".
    """
    last_release_tag_cmd = [
        "git",
        "describe",
        "--tags",
        "--match",
        "v*",
        "--exclude",
        "*edge*",
        "--abbrev=0",
    ]
    outcome = subprocess.run(
        last_release_tag_cmd, capture_output=True, universal_newlines=True
    )
    if outcome.stdout:
        last_release_tag = outcome.stdout.strip()
        return last_release_tag

    print(outcome.stderr)
    sys.exit("Failed to get last release tag")


def get_nb_commits(tag):
    """
    Use git to compute the number of commits since a given tag.
    """
    nb_commits_cmd = ["git", "rev-list", "--count", f"{tag}..HEAD"]

    outcome = subprocess.run(
        nb_commits_cmd, capture_output=True, universal_newlines=True
    )

    if outcome.stdout:
        nb_commits = outcome.stdout.strip()
        return int(nb_commits)

    print(outcome.stderr)
    sys.exit("Failed to count commits")


def guess_next_version(release_tag) -> str:
    """
    Increment the last number of a point release and return the updated
    release tag.

    >>> guess_next_version("v2.9.0")
    'v2.9.1'
    >>> guess_next_version("v2.9.9")
    'v2.9.10'
    >>> guess_next_version("wrong.version")
    Traceback (most recent call last):
        ...
    ValueError: invalid literal for int() with base 10: 'version'

    """
    release_list = release_tag.split(".")
    patch = release_list[-1]
    release_list[-1] = str(int(patch) + 1)
    next_version = ".".join(release_list)
    return next_version


def tag_head(tag):
    tag_cmd = ["git", "tag", "--force", tag]
    subprocess.run(tag_cmd)


def push_tags():
    push_cmd = ["git", "push", "--tags"]
    subprocess.run(push_cmd)


def main():
    last_release_tag = get_last_release_tag()
    nb_commits = get_nb_commits(last_release_tag)
    if nb_commits:
        next_version = guess_next_version(last_release_tag)
        edge_tag = f"{next_version}-edge+{nb_commits}"
        print(f"Tagging HEAD with '{edge_tag}'...")
        tag_head(edge_tag)
        print("Pushing tags...")
        push_tags()
    else:
        print("No new commits found")


if __name__ == "__main__":
    main()
