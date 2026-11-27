#!/usr/bin/env python3
"""
Explain the result of each canary target in the workflow run.

Canary jobs are named "<target> on <queue>" and retries
"<target> (retry) (<queue>)". The targets are the ones of the first jobs, and
a target passes if any of its jobs passed.

Usage: canary_results.py check|result
- check: output the targets where no job passed, so they are retried
- result: fail unless at least one job passed on each target
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

    # Collect each target's devices and successful jobs
    for job in get_jobs():
        words = job["name"].split()
        if len(words) < 2 or words[1] not in ("on", "(retry)"):
            continue
        target = words[0]
        queues.setdefault(target, set())
        passed.setdefault(target, [])
        if words[1] == "on":
            queues[target].add(words[2])
        if job["conclusion"] == "success":
            passed[target].append(job["name"])

    # Explain which targets passed and which need a retry
    failed = [target for target in sorted(passed) if not passed[target]]
    summary = ["| Target | Outcome |", "| --- | --- |"]
    for target in sorted(passed):
        if passed[target]:
            level = "notice"
            outcome = "{}, at least one job passed: {}".format(
                "No retry needed" if stage == "check" else "Accepted",
                ", ".join(passed[target]),
            )
        elif stage == "check":
            level = "warning"
            outcome = "No job passed, retrying {} in 30 minutes".format(
                " and ".join(sorted(queues[target]))
            )
        else:
            level = "error"
            outcome = "Rejected, no job passed in either attempt"
        print("::{} title={}::{}".format(level, target, outcome))
        summary.append("| {} | {} |".format(target, outcome))

    # Accept only if there are targets and each one has a passing job
    rejected = stage == "result" and (failed or not passed)
    if stage == "result":
        if not passed:
            message = "Canary rejected: no canary job was found"
        elif failed:
            message = "Canary rejected: no job passed on " + ", ".join(failed)
        else:
            message = "Canary accepted: at least one job passed on each target"
        print("::{}::{}".format("error" if rejected else "notice", message))
        summary.append("\n**{}.**".format(message))

    # Publish the summary and the list of targets to retry
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
        f.write("\n".join(summary) + "\n")
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write("retry={}\n".format(json.dumps(failed)))
    return 1 if rejected else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
