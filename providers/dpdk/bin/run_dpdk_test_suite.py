#!/usr/bin/env python3
"""Script to execute DPDK Tests Suites on remote DTS controller.

Copyright 2025 Canonical Ltd.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging
import os
import json
import argparse
import subprocess
from typing import Optional, Dict, Any
from pathlib import Path

DPDK_SNAP_BIN = "/snap/bin/dpdk-dts"
DEFAULT_TIMEOUT = 600
DEFAULT_OUTPUT_DIR = "dpdk_test_results"


class ConfigurationError(Exception):
    """Base Class Exception for configuration errors"""


class DTSRunner:
    """Class to execute snap-based DPDK Test Suite (DTS)"""

    def __init__(self, test_suite: str, config_file: Path):
        """Initialize class attributes."""
        self.test_suite = test_suite
        self.config_file = config_file

    def run_test_suite(
        self,
        verbose: bool,
    ) -> None:
        """Run specified test suite in DTS controller

        :param verbose: verbosity level on test suite execution
        """
        # Define verbosity level for DPDK Test Suite
        output_dir = Path(DEFAULT_OUTPUT_DIR) / self.test_suite
        output_dir.mkdir(parents=True, exist_ok=True)
        dts_command = (
            "{} --test-suite {} --config-file {} --output-dir {}".format(
                DPDK_SNAP_BIN, self.test_suite, self.config_file, output_dir
            )
        )
        if verbose:
            dts_command += " --verbose"

        logging.info(
            "Starting execution of %s",
            self.test_suite,
        )
        try:
            subprocess.run(
                dts_command,
                shell=True,
                check=True,
                timeout=DEFAULT_TIMEOUT,
            )
        except subprocess.CalledProcessError as exc:
            logging.error(
                "DPDK Test Suite execution failed with error: %s", exc
            )
            raise
        except subprocess.TimeoutExpired as exc:
            logging.error("DPDK Test Suite execution timed out: %s", exc)
            raise

        logging.info("DTS Test Suite Run completed")

    def get_results(self) -> Optional[Dict[str, Any]]:
        """Get the results from test suite execution.

        :return: Results in json format if any returned during test execution
        """

        logging.info("Getting test suite results")
        results_path = (
            Path(DEFAULT_OUTPUT_DIR) / self.test_suite / "results.json"
        )
        if not results_path.is_file():
            logging.warning("No results file found at %s", results_path)
            return None
        with results_path.open("r") as f:
            results = f.read()
        if results:
            try:
                return json.loads(results)
            except ValueError:
                logging.error("Unable to parse results file as JSON")

        return None

    def print_results(self) -> bool:
        """Print tests results from execution.

        :return: True if results were printed, False otherwise
        """

        test_results = self.get_results()
        if not test_results:
            return False

        # Print Test Suite Results and Summary
        print("\nDPDK Test Results")
        print("-" * 50)

        try:
            for test_run in test_results["test_runs"]:
                for test_suite in test_run["test_suites"]:
                    print(
                        "\nTest Suite: {}".format(
                            test_suite["test_suite_name"]
                        )
                    )
                    print("{:<30} {}".format("Test Case", "Result"))
                    print("-" * 40)

                    # Print test case details
                    for test_case in test_suite["test_cases"]:
                        print(
                            "{:<30} {}".format(
                                test_case["test_case_name"],
                                test_case["result"],
                            )
                        )

                    # Print summary
                    print("\nSummary:")
                    print("-" * 40)
                    for status, count in test_suite["summary"].items():
                        print("{}: {}".format(status, count))
        except KeyError:
            # If unable to pretty print, dump the test results
            print(json.dumps(test_results, indent=2))

        return True


def parse_args():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="DPDK Test Suite Execution")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Increase logging level in test suite execution",
    )
    parser.add_argument(
        "-T", "--test-suite", required=True, help="Specified Test Suite to run"
    )
    args = parser.parse_args()

    return args


def main():
    """Main entrypoint to the program."""
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    dts_config = os.getenv("DTS_CONFIG_FILE")

    # Print environment variables used for test suite run
    logging.info("DTS_CONFIG_FILE: %s", dts_config)

    if not dts_config or not Path(dts_config).is_file():
        raise SystemExit(
            "Missing environment variables to start test execution"
        )

    # Run snap-based DPDK Test Suite
    try:
        dts_runner = DTSRunner(
            test_suite=args.test_suite, config_file=Path(dts_config)
        )
        dts_runner.run_test_suite(args.verbose)
    except ConfigurationError as exc:
        raise SystemExit(
            "Unable to start Test Suite execution due to the following "
            "exception: {}".format(exc)
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Attempt to print test results before exit
        dts_runner.print_results()
        raise SystemExit("Test Suite execution failed")

    # Print test suite execution results
    if not dts_runner.print_results():
        raise SystemExit("No test results found")


if __name__ == "__main__":
    main()
