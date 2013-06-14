# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
:mod:`plainbox.impl.commands.logtest` -- logtest sub-command
============================================================
"""

import logging

from plainbox.impl.commands import PlainBoxCommand


logger = logging.getLogger("plainbox.commands.logtest")


class LogTestInvocation:

    def __init__(self, ns):
        pass

    def run(self):
        logger.debug("a debug message")
        logger.info("a info message")
        logger.warning("a warning message")
        logger.error("an error message")
        logger.critical("a critical message")
        return 0


class LogTestCommand(PlainBoxCommand):
    """
    Implementation of ``$ plainbox dev crash``
    """

    def invoked(self, ns):
        return LogTestInvocation(ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "logtest", help="log messages at various levels")
        parser.set_defaults(command=self)
