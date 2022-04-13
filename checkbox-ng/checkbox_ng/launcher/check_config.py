# This file is part of Checkbox.
#
# Copyright 2018-2021 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
"""This module contains the implementation of the `check-config` subcmd."""

from checkbox_ng.config import load_configs


class CheckConfig():
    """Implementation of the `check-config` sub-command."""
    @staticmethod
    def invoked(_):
        """Function that's run with `check-config` invocation."""
        config = load_configs()
        print("Configuration files:")
        for source in config.sources:
            print(" - {}".format(source))
        for sect_name, section in config.sections.items():
            print("   [{0}]".format(sect_name))
            for var_name in section.keys():
                value = config.get_value(sect_name, var_name)
                if isinstance(value, list):
                    value = ', '.join(value)
                origin = config.get_origin(sect_name, var_name)
                origin = "From {}".format(origin) if origin else "(Default)"
                key_val = "{}={}".format(var_name, value)
                print("     {0: <34} {1}".format(key_val, origin))
        problems = config.get_problems()
        if not problems:
            print("No problems with config(s) found!")
            return 0
        print('Problems:')
        for problem in problems:
            print('- ', problem)
        return 1

    def register_arguments(self, parser):
        """Register extra args for this subcmd. No extra args ATM."""
