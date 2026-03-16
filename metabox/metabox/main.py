#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2021 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
Entry point to the Metabox program.
"""

import argparse
import logging
import sys
import warnings
from datetime import datetime
from pathlib import Path

from loguru import logger
from loguru._logger import Core
from metabox.core.runner import Runner

default_log_file = Path("/var/tmp/metabox") / "metabox-{}.log".format(
    datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
)
help_log_file_message = default_log_file.parent / "metabox-<TIMESTAMP>.log"


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Mute all ws4py ConnectionResetError
        return


def configure_logger(args):
    def _formatter(record):
        if record["level"].no < 10:
            return "<level>{message}</level>\n"
        else:
            return (
                "{time:HH:mm:ss} | <level>{level: <8}</level> "
                "<level>{message}</level>\n"
            )

    logger.remove()
    logger.add(sys.stdout, format=_formatter, level=args.log_level)
    logger.level("TRACE", color="<w><dim>")
    logger.level("DEBUG", color="<w><dim>")
    logger.add(args.log_file, level=args.log_level)
    if args.log_file == default_log_file:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Logging to: {}", args.log_file)
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


def main():
    """Entry point to Metabox."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "config",
        metavar="CONFIG",
        type=Path,
        help="Metabox configuration file",
    )
    parser.add_argument(
        "--tag",
        action="append",
        dest="tags",
        help="Run only scenario with the specified tag. "
        "Can be used multiple times.",
    )
    parser.add_argument(
        "--exclude-tag",
        action="append",
        dest="exclude_tags",
        help="Do not run scenario with the specified tag. "
        "Can be used multiple times.",
    )
    parser.add_argument(
        "--log",
        dest="log_level",
        choices=Core().levels.keys(),
        default="INFO",
        help="Set the logging level",
    )
    parser.add_argument(
        "--dispose",
        action="store_true",
        help="Delete LXD containers after the run",
    )
    parser.add_argument(
        "--dont-reprovision-existing",
        action="store_true",
        help="Use existing containers as-is without updating the source inside them",
    )
    parser.add_argument(
        "--hold-on-fail",
        action="store_true",
        help="Pause testing when a scenario fails",
    )
    parser.add_argument(
        "--debug-machine-setup",
        action="store_true",
        help="Turn on verbosity during machine setup. "
        "Only works with --log TRACE",
    )
    parser.add_argument(
        "--log-file",
        dest="log_file",
        type=Path,
        default=default_log_file,
        help="Path to the log file (default: {})".format(
            help_log_file_message
        ),
    )
    args = parser.parse_args()

    configure_logger(args)

    # Ignore warnings issued by pylxd/models/operation.py
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        runner = Runner(args)
        runner.setup()
        runner.run_all()
        raise SystemExit(not runner.wasSuccessful())


if __name__ == "__main__":
    main()
