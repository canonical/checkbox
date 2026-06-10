#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Checkbox Contributors
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
Run Fluster conformance tests filtered by decoder profile.

Downloads required test suites, selects only the test vectors that match
the declared profile, runs Fluster, parses the JUnit XML result, and
applies a pass-rate threshold to determine overall outcome.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

FLUSTER_COMMAND = "fluster"


def find_test_suite_json(test_suite, data_dir):
    """Locate the Fluster test suite JSON file."""
    candidate = os.path.join(data_dir, "{}.json".format(test_suite))
    if os.path.isfile(candidate):
        return candidate
    return None


def get_vectors_for_profile(test_suite_json_path, profile):
    """Return test vector names matching *profile* from the suite JSON."""
    with open(test_suite_json_path, "r") as fh:
        suite = json.load(fh)
    vectors = suite.get("test_vectors", [])
    matching = []
    for vec in vectors:
        vec_profile = vec.get("profile", "")
        if profile.lower() in vec_profile.lower():
            matching.append(vec.get("name", ""))
    return matching


def run_fluster(
    decoder,
    test_suite,
    vectors,
    timeout,
    jobs,
):
    """Execute fluster with the given parameters and return XML output."""
    fluster_cmd = shutil.which(FLUSTER_COMMAND)
    if not fluster_cmd:
        print("ERROR: fluster not found", file=sys.stderr)
        return None
    cmd = [
        "run",
        "-d",
        decoder,
        "-ts",
        test_suite,
        "-tv",
        ",".join(vectors),
        "-j",
        str(jobs),
        "--timeout",
        str(timeout),
        "--output-format",
        "junitxml",
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        print(
            "ERROR: fluster exited with code {}".format(result.returncode),
            file=sys.stderr,
        )
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return None
    return result.stdout


def parse_junit_xml(xml_text, threshold):
    """Parse JUnit XML and return pass rate vs threshold."""
    root = ET.fromstring(xml_text)
    suite = root.find("testsuite")
    if suite is None:
        print("ERROR: no testsuite element in XML", file=sys.stderr)
        return False
    total = int(suite.get("tests", "0"))
    failures = int(suite.get("failures", "0"))
    errors = int(suite.get("errors", "0"))
    passed = total - failures - errors
    if total == 0:
        print("WARNING: no test cases run", file=sys.stderr)
        return False
    pass_rate = passed / total
    print(
        "Results: {}/{} passed ({:.1%}), "
        "threshold {:.1%}".format(passed, total, pass_rate, threshold)
    )
    for testcase in suite.findall("testcase"):
        failure = testcase.find("failure")
        error = testcase.find("error")
        if failure is not None:
            print("  FAIL: {}".format(testcase.get("name", "unknown")))
        elif error is not None:
            print("  ERROR: {}".format(testcase.get("name", "unknown")))
    return pass_rate >= threshold


def main():
    parser = argparse.ArgumentParser(
        description="Run Fluster conformance tests"
    )
    parser.add_argument(
        "-d",
        "--decoder",
        required=True,
        help="Fluster decoder name",
    )
    parser.add_argument(
        "-ts",
        "--test-suite",
        required=True,
        help="Fluster test suite name",
    )
    parser.add_argument(
        "-p",
        "--profile",
        required=True,
        help="Profile to filter test vectors",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Per-vector timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=1,
        help="Number of parallel jobs (default: 1)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.9,
        help="Pass-rate threshold (default: 0.9)",
    )
    args = parser.parse_args()
    data_dir = os.environ.get("PLAINBOX_PROVIDER_DATA", "")
    suite_json = find_test_suite_json(args.test_suite, data_dir)
    if not suite_json:
        print(
            "WARNING: test suite JSON not found for {}; "
            "running all vectors".format(args.test_suite),
            file=sys.stderr,
        )
        vectors = []
    else:
        vectors = get_vectors_for_profile(suite_json, args.profile)
        if not vectors:
            print(
                "WARNING: no vectors match profile "
                "'{}'".format(args.profile),
                file=sys.stderr,
            )
    xml_output = run_fluster(
        args.decoder,
        args.test_suite,
        vectors,
        args.timeout,
        args.jobs,
    )
    if xml_output is None:
        return 1
    passed = parse_junit_xml(xml_output, args.threshold)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
