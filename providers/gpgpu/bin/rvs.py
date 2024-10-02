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
import sys
from pathlib import Path
from typing import override

RVS_BIN = Path("/opt/rocm/bin/rvs")
"""Default location for ROCm Validation Suite binary."""

PLAINBOX_PROVIDER_DATA = Path(os.getenv("PLAINBOX_PROVIDER_DATA", "../data"))
"""Location of the RVS module configurations."""


def which_rvs() -> Path:
    """Finds the location of the ROCm Validation Suite binary."""
    proc = subprocess.run(
        ["which", "rvs"], check=False, capture_output=True, text=True
    )
    return Path(proc.stdout.strip()) if proc.returncode == 0 else RVS_BIN


class ModuleRunner:
    """This class represents the base module runner."""

    def __init__(self, rvs: Path) -> None:
        """Initializes the module runner."""
        self.rvs = rvs

    def run(self, module: str) -> int:
        """Runs and validates the RVS module.

        Returns: 0 on success, nonzero on failure.
        """
        logging.debug("%s: RUNNING", module)
        proc = self._run(module)
        if proc.stdout:
            logging.info(proc.stdout)
        if proc.stderr:
            logging.debug(proc.stderr)

        if proc.returncode != 0:
            logging.error("%s: FAILURE", module)
            return 1

        logging.debug("%s: SUCCESS", module)
        return 0

    def _run(self, module: str) -> subprocess.CompletedProcess:
        """Runs the RVS module."""
        proc = subprocess.run(
            [self.rvs, "-c", PLAINBOX_PROVIDER_DATA / f"rvs-{module}.conf"],
            check=False,
            capture_output=True,
            text=True,
        )
        return proc


class PassFailModuleRunner(ModuleRunner):
    """This class represents a module runner that passes or fails."""

    @override
    def _run(self, module: str) -> subprocess.CompletedProcess:
        proc = super()._run(module)
        if proc.returncode != 0:
            return proc

        # Find any of the common success messages in stdout
        if not any(
            re.search(pass_str, proc.stdout)
            for pass_str in [
                r"%s true" % re.escape(module),
                r"pass: TRUE",
                r"GFLOPS \d+ Target GFLOPS: \d+ met: TRUE",
            ]
        ):
            proc.returncode = 1

        return proc


class MemModuleRunner(ModuleRunner):
    """This class represents the memory test module runner."""

    @override
    def _run(self, module: str) -> subprocess.CompletedProcess:
        proc = super()._run(module)
        if proc.returncode != 0:
            return proc

        # Check that every memory test passed
        if not all(
            re.search(r"mem Test %s : PASS" % re.escape(str(i)), proc.stdout)
            for i in range(1, 12)
        ):
            proc.returncode = 1

        return proc


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
        "modules",
        metavar="MOD",
        nargs="*",
        type=str,
        choices=RVS_MODULES.keys(),
        help="RVS modules to run",
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

    args = parser.parse_args()

    if args.list_modules:
        parser.exit(message=f"Modules supported: {' '.join(RVS_MODULES)}\n")
    elif not args.modules:
        parser.error("--list-modules or modules required")
    return args


def main():
    """Main entrypoint of the program."""
    args = parse_args()
    logging.basicConfig(level=args.log_level)

    logging.debug("Modules to run: %s" % ", ".join(args.modules))
    for module in args.modules:
        runner = RVS_MODULES[module](args.rvs)
        ret = runner.run(module)
        if ret != 0:
            logging.error("Result: FAIL")
            return 1

    logging.info("Result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
