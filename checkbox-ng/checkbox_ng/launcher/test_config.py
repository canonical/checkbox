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

from unittest import TestCase, mock
from unittest.mock import MagicMock

from checkbox_ng.launcher.config import CheckConfig, Defaults
from plainbox.impl.config import Configuration


class DefaultsTests(TestCase):
    @mock.patch("builtins.print")
    def test_invoked_ok(self, mock_print):
        ctx_mock = MagicMock()
        ctx_mock.args.no_help = False
        ctx_mock.args.no_type_hints = False
        Defaults.invoked(ctx_mock)
        self.assertTrue(mock_print.called)

    @mock.patch("builtins.print")
    def test_invoked_ok_nohelp(self, mock_print):
        ctx_mock = MagicMock()
        ctx_mock.args.no_help = True
        ctx_mock.args.no_type_hints = False
        Defaults.invoked(ctx_mock)
        self.assertTrue(mock_print.called)

    @mock.patch("builtins.print")
    def test_invoked_ok_nohints(self, mock_print):
        ctx_mock = MagicMock()
        ctx_mock.args.no_help = False
        ctx_mock.args.no_type_hints = True
        Defaults.invoked(ctx_mock)
        self.assertTrue(mock_print.called)

    def test_register_arguments(self):
        parser_mock = MagicMock()
        Defaults.register_arguments(parser_mock)

        self.assertTrue(parser_mock.add_argument)


class CheckConfigTests(TestCase):
    @mock.patch("builtins.print")
    @mock.patch("checkbox_ng.launcher.config.load_configs")
    def test_invoked_ok(self, mock_load_configs, mock_print):
        args_mock = MagicMock()
        args_mock.args.launcher = None
        # this is the default configuration
        mock_load_configs.return_value = Configuration()

        ret_val = CheckConfig.invoked(args_mock)

        mock_print.assert_any_call("Configuration files:")
        mock_print.assert_any_call("No problems with config(s) found!")
        self.assertEqual(ret_val, 0)

    @mock.patch("builtins.print")
    @mock.patch("checkbox_ng.launcher.config.load_configs")
    def test_invoked_has_problems(self, mock_load_configs, mock_print):
        args_mock = MagicMock()
        args_mock.args.launcher = None
        # this is the default configuration
        conf = Configuration()
        conf.notice_problem("Test problem")
        mock_load_configs.return_value = conf

        ret_val = CheckConfig.invoked(args_mock)

        mock_print.assert_any_call("Configuration files:")
        mock_print.assert_any_call("Problems:")
        mock_print.assert_any_call("- ", "Test problem")
        self.assertEqual(ret_val, 1)

    def test_register_arguments(self):
        parser_mock = MagicMock()
        CheckConfig.register_arguments(parser_mock)

        self.assertTrue(parser_mock.add_argument.called)
