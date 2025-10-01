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
from pathlib import Path
from typing import Optional, Dict

CONTAINER_NAME = "dpdk-dts"
DEFAULT_SSH_TIMEOUT = 30
DTS_REMOTE_PATH = "~/dpdk/dts"
DPDK_VERSION_PATH = "~/dpdk/VERSION"
REMOTE_RESULTS_PATH = DTS_REMOTE_PATH + "/output/results.json"


class ConfigurationError(Exception):
    """Base Class Exception for configuration errors"""


class DTSRunner:
    """Class to execute DPDK Test Suite (DTS) on remote host."""

    def __init__(self, dts_user: str, dts_ip: str):
        """Initialize class attributes."""
        self.dts_user = dts_user
        self.dts_ip = dts_ip
        self._validate_setup()
        self._clear_old_results()

    def _validate_setup(self):
        """Validate minimum requirements on remote host are properly set.

        :raises: ConfigurationError if any failure during validation
        """
        # Validate if DTS directory is available in remote host
        # Directory should be set according to documentation
        logging.info("Validating remote DTS repository is configured.")
        try:
            self.run_ssh_command(
                cmd="test -d {}".format(DTS_REMOTE_PATH),
            )
        except subprocess.CalledProcessError:
            raise ConfigurationError("Remote DTS directory missing")
        logging.info("Remote directory is properly set.")

        # Validate if docker container exists before test execution
        logging.info("Validating if docker container is running.")
        try:
            self.run_ssh_command(
                cmd="docker ps --filter 'name={}' -q | grep -q .".format(
                    CONTAINER_NAME
                ),
            )
        except subprocess.CalledProcessError:
            raise ConfigurationError(
                "Required docker container is not running"
            )
        logging.info("Container %s running in remote host.", CONTAINER_NAME)

    def _clear_old_results(self):
        """Delete results from previous execution on remote host"""
        try:
            self.run_ssh_command(cmd="rm -f {}".format(REMOTE_RESULTS_PATH))
        except subprocess.CalledProcessError:
            # No test results found
            pass

    def run_ssh_command(
        self, cmd: str, timeout: Optional[int] = DEFAULT_SSH_TIMEOUT
    ):
        """Run specified SSH command in remote host.

        :cmd: Command to execute, if protocol is ssh
        :timeout: Timeout in seconds for command execution, defaults to 30
        """
        subprocess.run(
            [
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "LogLevel=ERROR",
                "{}@{}".format(self.dts_user, self.dts_ip),
                cmd,
            ],
            check=True,
            timeout=timeout,
        )

    def read_remote_file(
        self,
        remote_path: str,
        timeout: Optional[int] = DEFAULT_SSH_TIMEOUT,
    ) -> Optional[str]:
        """Read a remote file if exists

        :remote_path: Path where file should be located
        :timeout: Timeout in seconds for command execution, defaults to 30
        :returns: file content if exists, otherwise return None
        """
        # Define command for reading remote file only if exists
        cmd = "test -f {} && cat {}".format(remote_path, remote_path)
        try:
            output = subprocess.check_output(
                [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-o",
                    "LogLevel=ERROR",
                    "{}@{}".format(self.dts_user, self.dts_ip),
                    cmd,
                ],
                universal_newlines=True,
                timeout=timeout,
            )
        except subprocess.CalledProcessError:
            output = None

        return output

    def copy_config_file(self, config_file: str):
        """Copy configuration file to remote host.

        :param config_file: Path to configuration file
        :raises: ConfigurationError if any failure during remote copy
        """

        # Validate path exists before attempting to copy
        config_path = Path(config_file)
        if not config_path.exists():
            raise ConfigurationError("Unable to locate config file")

        logging.info("Copying file %s to remote host.", config_path)
        try:
            subprocess.run(
                [
                    "scp",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-o",
                    "LogLevel=ERROR",
                    config_path,
                    "{}@{}:{}/dts_conf.yaml".format(
                        self.dts_user, self.dts_ip, DTS_REMOTE_PATH
                    ),
                ],
                check=True,
                timeout=60,
            )
        except subprocess.CalledProcessError:
            raise ConfigurationError(
                "Unable to copy config file to remote host"
            )

        logging.info("Successfully copied configuration file to remote host.")

    def run_test_suite(
        self,
        test_suite: str,
        verbose: bool,
    ):
        """Run specified test suite in DTS controller

        :param test_suite: Test Suite to run on DTS controller
        :verbose: verbosity level on test suite execution
        """
        # Define verbosity level for DPDK Test Suite
        if verbose:
            dts_command = (
                "poetry run python3 main.py --test-suite {} "
                "--config-file dts_conf.yaml --verbose".format(test_suite)
            )
        else:
            dts_command = (
                "poetry run python3 main.py --test-suite {} "
                "--config-file dts_conf.yaml".format(test_suite)
            )

        # Retrieve DPDK version
        version = self.read_remote_file(DPDK_VERSION_PATH)
        logging.info(
            "Starting execution of %s with DPDK v%s on remote host: %s",
            test_suite,
            version.strip() if version else "Unknown",
            self.dts_ip,
        )
        self.run_ssh_command(
            cmd="docker exec {} bash -l -c '{}'".format(
                CONTAINER_NAME, dts_command
            ),
            timeout=300,
        )

        logging.info("DTS Test Suite Run completed")

    def get_results(self) -> Optional[Dict]:
        """Get the results from test suite execution.

        :return: Results in json format if any returned during test execution
        """

        logging.info(
            "Getting test suite results from remote host: %s", self.dts_ip
        )
        results = self.read_remote_file(REMOTE_RESULTS_PATH)
        if results:
            try:
                json_results = json.loads(results)
                return json_results
            except ValueError:
                return None

        return None

    def print_results(self):
        """Print tests results from execution."""

        test_results = self.get_results()
        if not test_results:
            return

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
                    for status, count in test_run["summary"].items():
                        print("{}: {}".format(status, count))
        except KeyError:
            # If unable to pretty print, dump the test results
            print(json.dumps(test_results, indent=2))


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
        "-d", "--driver", required=True, help="NIC driver with DPDK Support"
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
    dts_user = os.getenv("DTS_TARGET_USER")
    dts_ip = os.getenv("DTS_TARGET_IP")
    dts_config = os.getenv("DTS_CONFIG_FILE")

    # Print environment variables used for test suite run
    logging.info("DTS_TARGET_USER: %s", dts_user)
    logging.info("DTS_TARGET_IP: %s", dts_ip)
    logging.info("DTS_CONFIG_FILE: %s", dts_config)

    if not all([dts_user, dts_ip, dts_config]):
        raise SystemExit(
            "Missing environment variables to start test execution"
        )

    # Copy DTS configuration file to controller.
    try:
        dts_runner = DTSRunner(dts_user, dts_ip)
        dts_runner.copy_config_file(dts_config)
        dts_runner.run_test_suite(args.test_suite, args.verbose)
    except ConfigurationError as exc:
        raise SystemExit(
            "Unable to start Test Suite execution due to the following "
            "exception: {}".format(exc)
        )
    except subprocess.CalledProcessError:
        # Attempt to print test results before exit
        dts_runner.print_results()
        raise SystemExit("Test Suite execution failed")

    # Print test suite execution results
    dts_runner.print_results()


if __name__ == "__main__":
    main()
