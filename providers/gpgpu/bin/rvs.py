#!/usr/bin/env python3
"""ROCm Validation Suite wrapper.

Copyright (C) 2024 Canonical Ltd.

Authors
  Pedro Avalos Jimenez <pedro.avalosjimenez@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

The purpose of this script is to simply wrap the ROCm Validation Suite
executable, adding an appropriate failure exit code when a test fails.
"""

import argparse
import logging
import os
import re
import subprocess
from pathlib import Path

RVS_BIN = Path("/opt/rocm/bin/rvs")
"""Default location for ROCm Validation Suite binary."""

PLAINBOX_PROVIDER_DATA = Path(os.getenv("PLAINBOX_PROVIDER_DATA", "."))
"""Location of the RVS module configurations."""


def which_rvs() -> Path:
    """Finds the location of the ROCm Validation Suite binary."""
    proc = subprocess.run(
        ["which", "rvs"],
        check=False,
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )
    return Path(proc.stdout.strip()) if proc.returncode == 0 else RVS_BIN


class ModuleRunner:
    """This class represents the base module runner."""

    def __init__(self, rvs: Path, config: Path) -> None:
        """Initializes the module runner."""
        self.rvs = rvs
        self.config = config

    def run(self, module: str):
        """Runs and validates the RVS module.

        Returns: 0 on success, nonzero on failure.
        Raises: RuntimeError if process failed execution.
        """
        logging.debug("%s: RUNNING", module)
        proc = self._run(module)
        if proc.stdout:
            logging.info(proc.stdout)

        self._validate_output(proc, module)

        if proc.stderr:
            logging.debug(proc.stderr)
        logging.debug("%s: SUCCESS", module)

    def _run(self, module: str) -> subprocess.CompletedProcess:
        """Runs the RVS module."""
        proc = subprocess.run(
            [self.rvs, "-c", self.config],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        return proc

    def _validate_output(self, proc: subprocess.CompletedProcess, module: str):
        """Validates the output of the module.

        Raises: SystemExit if process failed execution.
        """
        if proc.returncode != 0:
            if proc.stderr:
                logging.error(proc.stderr)
            logging.error("%s: FAILURE", module)
            raise SystemExit(proc.returncode)


class PassFailModuleRunner(ModuleRunner):
    """This class represents a module runner that passes or fails."""

    def _validate_output(self, proc: subprocess.CompletedProcess, module: str):
        super()._validate_output(proc, module)

        # Find any of the common success messages in stdout
        if not any(
            re.search(pass_str, proc.stdout)
            for pass_str in [
                r"%s true" % re.escape(module),
                r"pass: TRUE",
                r"GFLOPS \d+ Target GFLOPS: \d+ met: TRUE",
            ]
        ):
            if proc.stderr:
                logging.error(proc.stderr)
            logging.error("%s: FAILURE", module)
            raise SystemExit(1)


class MemModuleRunner(ModuleRunner):
    """This class represents the memory test module runner."""

    def _validate_output(self, proc: subprocess.CompletedProcess, module: str):
        super()._validate_output(proc, module)

        # Check that every memory test passed
        if not all(
            "mem Test %s : PASS" % i in proc.stdout for i in range(1, 12)
        ):
            if proc.stderr:
                logging.error(proc.stderr)
            logging.error("%s: FAILURE", module)
            raise SystemExit(1)


RVS_MODULES = {
    "gpup": ModuleRunner,
    "peqt": PassFailModuleRunner,
    "pebb": ModuleRunner,
    "pbqt": ModuleRunner,
    "iet": PassFailModuleRunner,
    "babel": ModuleRunner,
    "mem": MemModuleRunner,
    "gst": PassFailModuleRunner,
}
"""Mapping of module to corresponding runner to use for it."""


def parse_args():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="ROCm Validation Suite wrapper"
    )
    parser.add_argument(
        "module",
        metavar="MOD",
        nargs="?",
        type=str,
        choices=RVS_MODULES.keys(),
        help="RVS module to run [{}]".format(", ".join(RVS_MODULES.keys())),
    )
    parser.add_argument(
        "-l",
        "--list-modules",
        action="store_true",
        help="List supported RVS modules",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="log_level",
        action="store_const",
        const=logging.DEBUG,
        default=logging.INFO,
        help="Increase logging verbosity",
    )
    parser.add_argument(
        "--rvs",
        metavar="EXE",
        type=Path,
        default=which_rvs(),
        help="Path to RVS binary",
    )
    parser.add_argument(
        "-c",
        "--config",
        metavar="PATH",
        type=Path,
        default=None,
        help="Path to RVS module configuration",
    )

    args = parser.parse_args()

    if args.list_modules:
        parser.exit(
            message="Modules supported: {}\n".format(" ".join(RVS_MODULES))
        )
    elif not args.module:
        parser.error("--list-modules or module required")

    # Add default configuration if none is provided
    if args.config is None:
        args.config = PLAINBOX_PROVIDER_DATA / "rvs-{}.conf".format(
            args.module
        )

    return args


def main():
    """Main entrypoint of the program."""
    args = parse_args()
    logging.basicConfig(level=args.log_level)

    logging.debug("Module to run: %s", args.module)
    runner = RVS_MODULES[args.module](args.rvs, args.config_dir)
    runner.run(args.module)

    logging.info("Result: PASS")


if __name__ == "__main__":
    main()
