# This file is part of Checkbox.
#
# Copyright 2018-2025 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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

from argparse import ArgumentParser
from plainbox.impl.config import CONFIG_SPEC, DynamicSection, ParametricSection
from checkbox_ng.config import load_configs


class Config:
    @staticmethod
    def invoked(context):
        actions = {"check": CheckConfig.invoked, "defaults": Defaults.invoked}
        return actions[context.args.action](context)

    def register_arguments(self, parser: ArgumentParser):
        subparsers = parser.add_subparsers(
            dest="action", title="action", description="action to be done on"
        )
        parser = subparsers.add_parser(
            "check", description=CheckConfig.__doc__
        )
        CheckConfig.register_arguments(parser)
        parser = subparsers.add_parser(
            "defaults", description=Defaults.__doc__
        )
        Defaults.register_arguments(parser)


class Defaults:
    """
    Prints a documented default launcher
    """

    @staticmethod
    def invoked(context):
        print(
            "# This is every possible section with the default value assigned"
        )
        for section_name, section_spec in CONFIG_SPEC:
            printer = print
            if isinstance(section_spec, ParametricSection):
                # lets comment out parametric sections because they don't make
                # sense if not instantiated to non-default values
                def printer(*args, **kwargs):
                    print("#", end="")
                    print(*args, **kwargs)

                printer(f"# [{section_name}:{section_name}_name]")

            else:
                printer(f"[{section_name}]")

            for key, value in section_spec.items():
                if not context.args.no_help:
                    printer(f"# {value.help}")
                if not context.args.no_type_hints:
                    printer(f"# type: {value.kind.__name__}")
                printer(f"{key} = {value.default}")
            # also provide an example for dynamic sections assignment
            if isinstance(section_spec, DynamicSection):
                printer(f"# {section_name}_example = example_value")

    @staticmethod
    def register_arguments(parser):
        parser.add_argument(
            "--no-type-hints",
            action="store_true",
            help="don't emit type hints",
        )
        parser.add_argument(
            "--no-help",
            action="store_true",
            help="don't document each value",
        )


class CheckConfig:
    """Implementation of the `check-config` sub-command."""

    @staticmethod
    def invoked(context):
        """Function that's run with `check-config` invocation."""
        config = load_configs(context.args.launcher)
        print("Configuration files:")
        for source in config.sources:
            print(f" - {source}")
        for sect_name, section in config.sections.items():
            print(f"   [{sect_name}]")
            for var_name in section.keys():
                value = config.get_value(sect_name, var_name)
                if isinstance(value, list):
                    value = ", ".join(value)
                origin = config.get_origin(sect_name, var_name)
                origin = f"From {origin}" if origin else "(Default)"
                key_val = f"{var_name}={value}"
                print(f"     {key_val: <34} {origin}")
        problems = config.get_problems()
        if not problems:
            print("No problems with config(s) found!")
            return 0
        print("Problems:")
        for problem in problems:
            print("- ", problem)
        return 1

    @staticmethod
    def register_arguments(parser):
        parser.add_argument(
            "launcher", nargs="?", help="launcher definition file to use"
        )
