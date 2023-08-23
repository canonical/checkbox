# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
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

from collections import namedtuple
from unittest import TestCase, mock

from checkbox_ng.launcher.checkbox_cli import main


class CheckboxCliTests(TestCase):
    @mock.patch("sys.argv")
    @mock.patch("argparse.ArgumentParser")
    @mock.patch("checkbox_ng.launcher.checkbox_cli.Launcher")
    def test_launcher_ok(
        self,
        launcher_mock,
        parse_args_mock,
        sys_argv_mock,
    ):
        # Add here necessary fake args to provide
        ns_parse_args_type = namedtuple(
            "ParseArgsNamespace", ["subcommand", "debug", "verbose"]
        )
        parse_args_mock.return_value = parse_args_mock
        parse_args_mock.parse_args.return_value = ns_parse_args_type(
            subcommand="launcher", debug=False, verbose=False
        )
        # for simplicitys sake, launcher_mock returns itself when constructed
        launcher_mock.return_value = launcher_mock

        main()

        self.assertTrue(launcher_mock.called)
        self.assertTrue(launcher_mock.invoked.called)
