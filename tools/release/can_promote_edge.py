#!/usr/bin/env python

"""
This script is ment to be the validation step to gate the promotion of
the edge channel in the store/ppa to beta. This only checks if the
preconditions are met for such an event.

Current pre-conditions:
- Latest succesful Daily Build matches origin/beta_validation
"""

import json
import subprocess


def get_gh_daily_builds_array() -> list[dict]:
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
    try:
        return next(
            x["headSha"] for x in builds if x["conclusion"] == "success"
        )
    except StopIteration:
        raise SystemExit("Couldn't fetch any successful daily build")


def get_head_beta_validated() -> str:
    return subprocess.check_output(
        ["git", "show", "origin/beta_validation", "--pretty=format:%H", "--no-patch"],
        text=True,
    )


def beta_validation_matches_successful_daily():
    builds = get_gh_daily_builds_array()
    last_daily_build_commit_hash = get_latest_ok_head(builds)
    last_beta_validated_head = get_head_beta_validated()
    print("Latest daily build commit hash:", last_daily_build_commit_hash)
    print("Latest beta validated head: ", last_beta_validated_head)
    return last_daily_build_commit_hash == last_beta_validated_head


def main():
    if not beta_validation_matches_successful_daily():
        raise SystemExit(
            "Latest built version and validated version do not match"
        )


if __name__ == "__main__":
    main()
