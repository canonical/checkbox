# This file is part of Checkbox.
#
#
# Copyright 2013 Canonical Ltd.
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
:mod:`plainbox.impl.commands.check_config` -- check-config sub-command
======================================================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""
import logging

from plainbox.impl.commands import PlainBoxCommand
from plainbox.impl.secure.config import ValidationError

from plainbox.i18n import gettext as _

logger = logging.getLogger("plainbox.commands.check_config")


class CheckConfigInvocation:
    """
    Helper class instantiated to perform a particular invocation of the sru
    command. Unlike the SRU command itself, this class is instantiated each
    time.
    """

    def __init__(self, config):
        self.config = config

    def run(self):
        print(_("Configuration files:"))
        for filename in self.config.Meta.filename_list:
            if filename in self.config.filename_list:
                print(" - {0}".format(filename))
            else:
                print(_(" - {0} (not present)").format(filename))
        print(_("Variables:"))
        for variable in self.config.Meta.variable_list:
            print("   {0}={1}".format(
                variable.name,
                variable.__get__(self.config, self.config.__class__)))
        print(_("Sections:"))
        for section in self.config.Meta.section_list:
            print("   {0}={1}".format(
                section.name,
                section.__get__(self.config, self.config.__class__)))
        if self.config.problem_list:
            print(_("Problems:"))
            for problem in self.config.problem_list:
                if isinstance(problem, ValidationError):
                    print(_(" - variable {0}: {1}").format(
                        problem.variable.name, problem.message))
                else:
                    print(" - {0}".format(problem.message))
        else:
            print(_("No validation problems found"))
        return 0 if len(self.config.problem_list) == 0 else 1


class CheckConfigCommand(PlainBoxCommand):
    """
    Command for checking and displaying plainbox configuration
    """

    def __init__(self, config):
        self.config = config

    def invoked(self, ns):
        return CheckConfigInvocation(self.config).run()

    def register_parser(self, subparsers):
        parser = subparsers.add_parser(
            "check-config", help=_("check and display plainbox configuration"))
        parser.set_defaults(command=self)
