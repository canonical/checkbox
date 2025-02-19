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

from checkbox_ng.launcher.checkbox_cli import (
    main,
    handle_top_parser,
)


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


@mock.patch("checkbox_ng.launcher.checkbox_cli.logging", new=mock.MagicMock())
class TestHandleTopParser(TestCase):

    @mock.patch("sys.argv", ["--debug"])
    @mock.patch("checkbox_ng.launcher.checkbox_cli.set_all_loggers_level")
    def test_debug_flag(self, set_all_loggers_level_mock):
        ctx = mock.MagicMock()
        result = handle_top_parser(None, ctx)
        self.assertTrue(result.args.debug)
        self.assertTrue(set_all_loggers_level_mock.called)

    @mock.patch("sys.argv", ["--verbose"])
    @mock.patch("checkbox_ng.launcher.checkbox_cli.set_all_loggers_level")
    def test_verbose_flag(self, set_all_loggers_level_mock):
        ctx = mock.MagicMock()
        result = handle_top_parser(None, ctx)
        self.assertTrue(result.args.verbose)
        self.assertTrue(set_all_loggers_level_mock.called)

    @mock.patch("sys.argv", ["--clear-cache"])
    @mock.patch("checkbox_ng.launcher.checkbox_cli.ResourceJobCache")
    def test_clear_cache(self, mock_cache):
        ctx = mock.MagicMock()
        result = handle_top_parser(None, ctx)
        self.assertTrue(mock_cache().clear.called)
        self.assertTrue(result.args.clear_cache)

    @mock.patch("sys.argv", ["--clear-old-sessions"])
    def test_clear_old_sessions(self):
        ctx = mock.MagicMock()
        ctx.sa.get_old_sessions.return_value = [("session1",)]
        result = handle_top_parser(None, ctx)
        ctx.sa.delete_sessions.assert_called_with(["session1"])
        self.assertTrue(result.args.clear_old_sessions)

    @mock.patch("sys.argv", ["--version"])
    def test_version_flag(self):
        ctx = mock.MagicMock()
        with self.assertRaises(SystemExit) as cm:
            handle_top_parser(None, ctx)
        self.assertEqual(cm.exception.code, 0)
