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
import warnings
from pathlib import Path

from loguru._logger import Core
from metabox.core.runner import Runner


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Mute all ws4py ConnectionResetError
        return


def main():
    """Entry point to Metabox."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'config', metavar='CONFIG', type=Path,
        help='Metabox configuration file'
    )
    parser.add_argument(
        '--tag', action='append', dest='tags',
        help='Run only scenario with the specified tag. '
             'Can be used multiple times.',
    )
    parser.add_argument(
        '--exclude-tag', action='append', dest='exclude_tags',
        help='Do not run scenario with the specified tag. '
             'Can be used multiple times.',
    )
    parser.add_argument(
        "--log", dest="scenario_log_level", choices=Core().levels.keys(),
        default='SUCCESS',
        help="Set the scenario logging level",
    )
    parser.add_argument(
        '--do-not-dispose', action='store_true',
        help="Do not delete LXD containers after the run")
    parser.add_argument(
        '--hold-on-fail', action='store_true',
        help="Pause testing when a scenario fails")
    parser.add_argument(
        '--debug-machine-setup', action='store_true',
        help="Turn on verbosity during machine setup. "
             "Only works with --log TRACE")
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    # Ignore warnings issued by pylxd/models/operation.py
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        runner = Runner(parser.parse_args())
        runner.collect()
        runner.setup()
        runner.run()
        raise SystemExit(not runner.wasSuccessful())


if __name__ == '__main__':
    main()
