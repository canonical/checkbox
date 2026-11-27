#!/usr/bin/env python3
"""
Explain the result of each canary platform in the workflow run.

Canary jobs are named "<platform> on <queue>" and retries
"<platform> (retry) (<queue>)". A platform passes if any of its jobs passed.

Usage: canary_results.py check|result
- check: output the platforms where no job passed, so they are retried
- result: fail unless at least one job passed on each platform
"""

import json
import os
import subprocess
import sys


def get_jobs():
    """Return the name and conclusion of every job in the current run"""
    url = "repos/{GITHUB_REPOSITORY}/actions/runs/{GITHUB_RUN_ID}/jobs"
    output = subprocess.check_output(
        [
            "gh",
            "api",
            "--paginate",
            url.format(**os.environ),
            "--jq",
            ".jobs[] | {name, conclusion}",
        ],
        text=True,
    )
    return [json.loads(line) for line in output.splitlines()]


def main(stage):
    queues = {}
    passed = {}
    for job in get_jobs():
        words = job["name"].split()
        if len(words) < 2 or words[1] not in ("on", "(retry)"):
            continue
        platform = words[0]
        queues.setdefault(platform, set())
        passed.setdefault(platform, [])
        if words[1] == "on":
            queues[platform].add(words[2])
        if job["conclusion"] == "success":
            passed[platform].append(job["name"])

    failed = [platform for platform in sorted(passed) if not passed[platform]]
    summary = ["| Platform | Outcome |", "| --- | --- |"]
    for platform in sorted(passed):
        if passed[platform]:
            level = "notice"
            outcome = "{}, at least one job passed: {}".format(
                "No retry needed" if stage == "check" else "Accepted",
                ", ".join(passed[platform]),
            )
        elif stage == "check":
            level = "warning"
            outcome = "No job passed, retrying {} in 30 minutes".format(
                " and ".join(sorted(queues[platform]))
            )
        else:
            level = "error"
            outcome = "Rejected, no job passed in either attempt"
        print("::{} title={}::{}".format(level, platform, outcome))
        summary.append("| {} | {} |".format(platform, outcome))

    if stage == "result":
        if failed:
            message = "Canary rejected: no job passed on " + ", ".join(failed)
        else:
            message = (
                "Canary accepted: at least one job passed on each platform"
            )
        print("::{}::{}".format("error" if failed else "notice", message))
        summary.append("\n**{}.**".format(message))

    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
        f.write("\n".join(summary) + "\n")
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write("retry={}\n".format(json.dumps(failed)))
    return 1 if stage == "result" and failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
