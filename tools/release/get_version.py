#!/usr/bin/env python3
import sys
import logging
import argparse
import textwrap

from enum import Enum
from collections import namedtuple
from subprocess import check_output

logger = None


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
    period = f"{tag}..HEAD"
    # get all commit hash short descriptions in the period
    return check_output(
        ["git", "log", "--pretty=format:%s", period], cwd=repo_path, text=True
    ).splitlines()


def get_most_severe(
    trace_one: TraceabilityEnum, trace_other: TraceabilityEnum
) -> TraceabilityEnum:
    severity = [
        TraceabilityEnum.BREAKING,
        TraceabilityEnum.NEW,
        TraceabilityEnum.BUGFIX,
        TraceabilityEnum.INFRA,
    ]
    trace_one_severity = severity.index(trace_one)
    trace_other_severity = severity.index(trace_other)
    return severity[min(trace_one_severity, trace_other_severity)]


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
        needed_bump = get_most_severe(needed_bump, current_trace)

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
    return f"{version}-dev{history_len}"


def get_bumped_version(version: str, needed_bump: TraceabilityEnum) -> str:
    version_no_v = version.replace("v", "")
    major, minor, patch = (int(n) for n in version_no_v.split("."))
    if needed_bump == TraceabilityEnum.BREAKING:
        major += 1
        minor = 0
        patch = 0
    elif needed_bump == TraceabilityEnum.NEW:
        minor += 1
        patch = 0
    elif needed_bump == TraceabilityEnum.BUGFIX:
        patch += 1
    else:
        ...
    return f"v{major}.{minor}.{patch}"


def describe_bump(needed_bump: TraceabilityEnum) -> str:
    if needed_bump == TraceabilityEnum.BREAKING:
        return "major"
    elif needed_bump == TraceabilityEnum.NEW:
        return "minor"
    elif needed_bump == TraceabilityEnum.BUGFIX:
        return "patch"
    return "none"


def setup_logger(log_level: str):
    """
    Sets up the global logger to the provider log_level
    """
    global logger
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, log_level))


def get_cli_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log",
        choices=["ERROR", "WARNING", "INFO"],
        help="set the log level (default: %(default)s)",
        default="WARNING",
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


def get_version(repo_path: str, dev_suffix: bool, log_level: str):
    setup_logger(log_level)

    last_stable_release = get_last_stable_release(repo_path)
    logger.info("Last stable release:", last_stable_release)
    history = get_history_since(last_stable_release, repo_path)
    needed_bump = get_needed_bump(history)
    if needed_bump == TraceabilityEnum.INFRA:
        raise SystemExit("Could not detect any release worthy commit!")

    final_version = bumped_version = get_bumped_version(
        last_stable_release, needed_bump
    )
    if dev_suffix:
        final_version = add_dev_suffix(bumped_version, len(history))

    bump_reason = describe_bump(needed_bump)
    logger.info(f"Detected necessary bump: {bump_reason}")
    logger.info("Proposed new version:")

    return final_version


def main(argv):
    args = get_cli_args(argv)
    version = get_version(args.repo_path, args.dev_suffix, args.log)
    print(version)


if __name__ == "__main__":
    main(sys.argv[1:])
