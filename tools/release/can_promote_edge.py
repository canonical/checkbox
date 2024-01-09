#!/usr/bin/env python3

"""
This script is meant to be the validation step to gate the promotion of
the edge channel in the store/ppa to beta. This only checks if the
preconditions are met for such an event.

Current pre-conditions:
- Latest succesful Daily Build matches origin/beta
"""

import json
import subprocess


def get_gh_daily_builds_array() -> list[dict]:
    """
    Query github for the latest 20 runs of the daily-builds.yml workflow
    returning a parsed array of dicts containing their headSha (hash the run
    was triggered on) and conclusion.
    """
    return json.loads(
        subprocess.check_output(
            [
                "gh",
                "run",
                "list",
                "--repo",
                "canonical/checkbox",
                "--workflow",
                ".github/workflows/daily-builds.yml",
                "--limit",
                "20",
                "--json",
                "headSha,conclusion",
            ],
            text=True,
        )
    )


def get_latest_ok_head(builds: list[dict]) -> str:
    """
    Returns the headSha of the most recent run of a build that was successful
    """
    try:
        return next(
            x["headSha"] for x in builds if x["conclusion"] == "success"
        )
    except StopIteration:
        raise SystemExit("Couldn't fetch any successful daily build")


def get_head_beta() -> str:
    """
    Returns the full hash of origin/beta's HEAD
    """
    return subprocess.check_output(
        [
            "git",
            "show",
            "origin/beta",
            "--pretty=format:%H",
            "--no-patch",
        ],
        text=True,
    )


def beta_matches_successful_daily() -> bool:
    """
    Returns true if the most recent daily build was run on the same commit
    that the head of beta points to, else false
    """
    builds = get_gh_daily_builds_array()
    last_daily_build_commit_hash = get_latest_ok_head(builds)
    last_beta_head = get_head_beta()
    print("Latest daily build commit hash:", last_daily_build_commit_hash)
    print("Latest beta validated head: ", last_beta_head)
    return last_daily_build_commit_hash == last_beta_head


def main():
    if not beta_matches_successful_daily():
        raise SystemExit(
            "Latest built version and validated version do not match"
        )


if __name__ == "__main__":
    main()
