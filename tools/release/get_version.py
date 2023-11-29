#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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
"""
This module calculates the next version based on the current state of a
repository.It analyzes the commit history since the last tag, categorizes
commits into breaking changes, new features, bug fixes, or infrastructure
changes, and determines the appropriate version bump. The calculated version
can be optionally suffixed with a development suffix indicating the count of
commits since the latest tag.

Note: The commit messages are expected to follow the format:
        "Message that ends with (Traceability) (#PR)".
      Any deviation may result in a warning, and the script may not
      categorize the commit correctly.
"""

import sys
import logging
import argparse
import textwrap

from enum import Enum
from collections import namedtuple
from subprocess import check_output

logger = logging.getLogger(__name__)


class TraceabilityEnum(Enum):
    BREAKING = "breaking"
    NEW = "new"
    BUGFIX = "bugfix"
    INFRA = "infra"

    @classmethod
    def parse(cls, trace):
        # traceability text is in the form (trace). To be robust and
        # not too pedantic, the string is case insensitive
        return cls(trace.replace("(", "").replace(")", "").lower())

    def describe(self) -> str:
        description = "none"
        if self == TraceabilityEnum.BREAKING:
            description = "major"
        elif self == TraceabilityEnum.NEW:
            description = "minor"
        elif self == TraceabilityEnum.BUGFIX:
            description = "patch"
        return description

    def __lt__(self, trace_other: 'Self') -> bool:
        severity = [
            TraceabilityEnum.INFRA,
            TraceabilityEnum.BUGFIX,
            TraceabilityEnum.NEW,
            TraceabilityEnum.BREAKING,
        ]
        trace_one_severity = severity.index(self)
        trace_other_severity = severity.index(trace_other)
        return trace_one_severity < trace_other_severity


FailedCategory = namedtuple("FailedCategory", ["commit", "pr"])


def get_last_stable_release(repo_path: str) -> str:
    """
    Returns the last stable release (vM.m.p)

    The naming convention postfixes every channel promotion with the channel
    name and validation status except stable, we don't have any other tag in
    the repo so to fetch the last stable release version we can get the latest
    tag that ends with a number
    """
    return check_output(
        [
            "git",
            "describe",
            "--tags",
            "--match",
            "*[0123456789]",
            "--abbrev=0",
            "origin/main",
        ],
        cwd=repo_path,
        text=True,
    ).strip()


def get_history_since(tag: str, repo_path: str) -> list[str]:
    """
    Returns the list of commits messages since the input tag
    """
    period = f"{tag}..HEAD"
    # get all commit hash short descriptions in the period
    return check_output(
        ["git", "log", "--pretty=format:%s", period], cwd=repo_path, text=True
    ).splitlines()


def get_needed_bump(history: list[str]) -> TraceabilityEnum:
    """
    Get what version number should be bumped using traceability postfixes

    Breaking -> Major bump
    New -> Minor bump
    BugFix -> Patch bump
    Infra -> No bump

    Note: This yields a warning for commit messages are not in the format
        Message (Traceability) (#PR)
    """

    needed_bump = TraceabilityEnum.INFRA
    failed_category = []

    # categorize all commits in the history
    for commit_message in history:
        *_, trace_str, pr = commit_message.rsplit(" ", 2)
        try:
            current_trace = TraceabilityEnum.parse(trace_str)
        except ValueError:
            # clean up the pr so that we can use it in the warning
            pr = pr.replace("(", "").replace(")", "").replace("#", "")
            failed_category.append(
                FailedCategory(commit=commit_message, pr=pr)
            )
            continue
        needed_bump = max(needed_bump, current_trace)

    # report commits that were not automatically categorized
    if failed_category:
        logger.warning("Failed to categorize:")
    for failure in failed_category:
        warning_failure_text = textwrap.dedent(
            f"""
            {failure.commit}
            Check: https://github.com/canonical/checkbox/pull/{failure.pr}
            """
        ).strip()
        logger.warning(warning_failure_text)

    return needed_bump


def add_dev_suffix(version: str, history_len: int):
    """
    Adds the dev suffix to a version string
    """
    return f"{version}-dev{history_len}"


def bump_version(version: str, needed_bump: TraceabilityEnum) -> str:
    """
    Increases to the correct version part given the traceability
    """
    version_no_v = version.replace("v", "")
    major, minor, patch = (int(n) for n in version_no_v.split("."))
    match needed_bump:
        case TraceabilityEnum.BREAKING:
            major += 1
            minor = 0
            patch = 0
        case TraceabilityEnum.NEW:
            minor += 1
            patch = 0
        case TraceabilityEnum.BUGFIX:
            patch += 1
        case TraceabilityEnum.INFRA:
            pass
        case _:
            raise ValueError(f"Unknown traceability marker {needed_bump}")
    return f"v{major}.{minor}.{patch}"


def setup_logger(verbose: bool):
    """
    Sets up the global logger to the provider log_level
    """
    if verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)


def get_cli_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        help="increase verbosity, describing each step",
        action="store_true",
    )
    parser.add_argument(
        "--dev-suffix",
        action="store_true",
        help=(
            "add a -devXX suffix to the version where XX is the count "
            "of commits since the latest tag"
        ),
    )
    parser.add_argument(
        "repo_path", nargs="?", help="location of the repo (default: cwd)"
    )
    return parser.parse_args(argv)


def get_version(
    dev_suffix: bool, verbose: bool = False, repo_path: str = None
) -> str:
    """
    Gets the next version string after calculting the current using tags.
    When dev_suffix is true, this new version string will also include a
    suffix that indicates the number of commits since the latest tag.
    """
    setup_logger(verbose)

    last_stable_release = get_last_stable_release(repo_path)
    logger.info(f"Last stable release: {last_stable_release}")
    history = get_history_since(last_stable_release, repo_path)
    needed_bump = get_needed_bump(history)
    if needed_bump == TraceabilityEnum.INFRA:
        raise SystemExit("Could not detect any release worthy commit!")

    final_version = bumped_version = bump_version(
        last_stable_release, needed_bump
    )
    if dev_suffix:
        final_version = add_dev_suffix(bumped_version, len(history))

    bump_reason = needed_bump.describe()
    logger.info(f"Detected necessary bump: {bump_reason}")
    logger.info("Proposed new version:")

    return final_version


def main(argv):
    args = get_cli_args(argv)
    version = get_version(args.dev_suffix, args.v, args.repo_path)
    print(version)


if __name__ == "__main__":
    main(sys.argv[1:])
