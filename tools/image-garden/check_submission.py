#!/usr/bin/env python3
"""Compare a Checkbox submission.json against a golden results file.

The golden file is a JSON list of expected job records, for example:

    [
      {"id": "smoke-automated-normal-pass", "outcome": "pass",
       "output_contains": "SMOKE_NORMAL_PASS"},
      {"id": "smoke-automated-normal-crash", "outcome": "crash"}
    ]

Each entry's "id" is matched against the "id" field of a job result in
submission.json. "outcome" must match that result's "outcome" exactly
(e.g. "pass", "fail", "crash"). "output_contains" is optional; when
given, the job's "io_log" must contain it as a substring.

This is used to verify both that Checkbox records the expected result
for every job, and that it doesn't lose any of their output.
"""

import argparse
import json
import sys


def check_submission(golden, submission):
    results = {result["id"]: result for result in submission["results"]}

    failures = []
    for expected in golden:
        # Check that all the expected jobs are present
        job_id = expected["id"]
        result = results.get(job_id)
        if result is None:
            failures.append(f"{job_id}: missing from submission")
            continue

        # Check that the job's outcome matches the expected outcome
        expected_outcome = expected["outcome"]
        actual_outcome = result["outcome"]
        if actual_outcome != expected_outcome:
            failures.append(
                f"{job_id}: expected outcome {expected_outcome!r}, "
                f"got {actual_outcome!r}"
            )

        # Optionally check that the job's output contains the expected string
        output_contains = expected.get("output_contains")
        if output_contains is not None:
            io_log = result.get("io_log", "")
            if output_contains not in io_log:
                failures.append(
                    f"{job_id}: expected output to contain "
                    f"{output_contains!r}, got {io_log!r}"
                )
    return failures


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("submission", help="Path to submission.json")
    parser.add_argument("golden", help="Path to the golden results JSON")
    return parser


def main(args=None):
    parsed = build_parser().parse_args(args)
    with open(parsed.golden) as f:
        golden = json.load(f)
    with open(parsed.submission) as f:
        submission = json.load(f)

    failures = check_submission(golden, submission)
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    if failures:
        return 1

    print(f"OK: {len(golden)} jobs matched their expected results")
    return 0


if __name__ == "__main__":
    sys.exit(main())
