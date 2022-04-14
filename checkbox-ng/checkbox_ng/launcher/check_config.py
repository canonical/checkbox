# This file is part of Checkbox.
#
# Copyright 2018-2019 Canonical Ltd.
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
from plainbox.impl.secure.config import ValidationError
from plainbox.i18n import gettext as _

from checkbox_ng.config import load_configs


class CheckConfig():
    def invoked(self, ctx):
        config = load_configs()
        print(_("Configuration files:"))
        for filename in config.filename_list:
            print(" - {}".format(filename))
        for variable in config.Meta.variable_list:
            print("   [{0}]".format(variable.section))
            print("   {0}={1}".format(
                variable.name,
                variable.__get__(config, config.__class__)))
        for section in config.Meta.section_list:
            print("   [{0}]".format(section.name))
            section_value = section.__get__(config, config.__class__)
            if section_value:
                for key, value in sorted(section_value.items()):
                    print("   {0}={1}".format(key, value))
        if config.problem_list:
            print(_("Problems:"))
            for problem in config.problem_list:
                if isinstance(problem, ValidationError):
                    print(_(" - variable {0}: {1}").format(
                        problem.variable.name, problem.message))
                else:
                    print(" - {0}".format(problem.message))
            return 1
        else:
            print(_("No validation problems found"))
            return 0

    def register_arguments(self, parser):
        pass
