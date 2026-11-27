#!/usr/bin/env python3
"""
Explain the result of each canary platform in the workflow run.

Canary jobs are named "<platform> on <queue>", with " (retry)" appended for
the retries. A platform passes if any of its jobs passed.

- check: output the platforms where no job passed, so they are retried
- result: fail unless at least one job passed on each platform
"""

import argparse
import json
import os
import re
import subprocess

JOB_NAME = re.compile(r"^(\S+) on (\S+)")


def get_jobs():
    """Return the name and conclusion of every job in the current run"""
    output = subprocess.check_output(
        [
            "gh",
            "api",
            "--paginate",
            "repos/{}/actions/runs/{}/jobs".format(
                os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_RUN_ID"]
            ),
            "--jq",
            ".jobs[] | {name, conclusion}",
        ],
        text=True,
    )
    return [json.loads(line) for line in output.splitlines()]


def get_platforms(jobs):
    """Group the canary jobs by platform"""
    platforms = {}
    for job in jobs:
        match = JOB_NAME.match(job["name"])
        if not match:
            continue
        platform, queue = match.groups()
        result = platforms.setdefault(platform, {"queues": [], "passed": []})
        if queue not in result["queues"]:
            result["queues"].append(queue)
        if job["conclusion"] == "success":
            result["passed"].append(job["name"])
    return platforms


def explain(stage, queues, passed):
    """Return the annotation level and the outcome of a platform"""
    if passed:
        verdict = "No retry needed" if stage == "check" else "Accepted"
        return "notice", "{}, at least one job passed: {}".format(
            verdict, ", ".join(passed)
        )
    if stage == "check":
        return "warning", "No job passed, retrying {} in 30 minutes".format(
            " and ".join(queues)
        )
    return "error", "Rejected, no job passed in either attempt"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["check", "result"])
    args = parser.parse_args(argv)

    summary = ["| Platform | Outcome |", "| --- | --- |"]
    failed = []
    for platform, result in sorted(get_platforms(get_jobs()).items()):
        level, outcome = explain(args.stage, **result)
        print("::{} title={}::{}".format(level, platform, outcome))
        summary.append("| {} | {} |".format(platform, outcome))
        if not result["passed"]:
            failed.append(platform)

    if args.stage == "result" and not failed:
        print(
            "::notice::Canary accepted: "
            "at least one job passed on each platform"
        )
        summary.append(
            "\n**Canary accepted: "
            "at least one job passed on each platform.**"
        )
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
        f.write("\n".join(summary) + "\n")
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write("retry={}\n".format(json.dumps(failed)))

    if args.stage == "result" and failed:
        print(
            "::error::Canary rejected: no job passed on {}".format(
                ", ".join(failed)
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
