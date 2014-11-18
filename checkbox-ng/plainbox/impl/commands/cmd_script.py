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
:mod:`plainbox.impl.commands.cmd_script` -- script sub-command
==============================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from plainbox.i18n import gettext as _
from plainbox.impl.commands import PlainBoxCommand


class ScriptCommand(PlainBoxCommand):
    """
    Command for running the script embedded in a `command` of a job
    unconditionally.
    """

    def __init__(self, provider_loader, config_loader):
        self.provider_loader = provider_loader
        self.config_loader = config_loader

    def invoked(self, ns):
        from plainbox.impl.commands.inv_script import ScriptInvocation
        return ScriptInvocation(
            self.provider_loader, self.config_loader, ns.job_id
        ).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "script", help=_("run a command from a job"),
            prog="plainbox dev script")
        parser.set_defaults(command=self)
        parser.add_argument(
            'job_id', metavar=_('JOB-ID'),
            help=_("Id of the job to run"))
