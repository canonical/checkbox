# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
:mod:`plainbox.impl.commands.logtest` -- logtest sub-command
============================================================
"""

import logging

from plainbox.impl.commands import PlainBoxCommand
from plainbox.i18n import gettext as _


logger = logging.getLogger("plainbox.commands.logtest")


class LogTestInvocation:

    def __init__(self, ns):
        pass

    def run(self):
        logger.debug(_("a debug message"))
        logger.info(_("a info message"))
        logger.warning(_("a warning message"))
        logger.error(_("an error message"))
        logger.critical(_("a critical message"))
        return 0


class LogTestCommand(PlainBoxCommand):
    """
    Implementation of ``$ plainbox dev crash``
    """

    def invoked(self, ns):
        return LogTestInvocation(ns).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "logtest", help=_("log messages at various levels"),
            prog="plainbox dev logtest")
        parser.set_defaults(command=self)
