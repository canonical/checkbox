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

from checkbox_ng.launcher.check_config import CheckConfig
from plainbox.impl.config import Configuration


class CheckConfigTests(TestCase):
    @mock.patch("builtins.print")
    @mock.patch("checkbox_ng.launcher.check_config.load_configs")
    def test_invoked_ok(self, mock_load_configs, mock_print):
        # this is the default configuration
        mock_load_configs.return_value = Configuration()

        ret_val = CheckConfig.invoked(...)

        mock_print.assert_any_call("Configuration files:")
        mock_print.assert_any_call("No problems with config(s) found!")
        self.assertEqual(ret_val, 0)

    @mock.patch("builtins.print")
    @mock.patch("checkbox_ng.launcher.check_config.load_configs")
    def test_invoked_has_problems(self, mock_load_configs, mock_print):
        # this is the default configuration
        conf = Configuration()
        conf.notice_problem("Test problem")
        mock_load_configs.return_value = conf

        ret_val = CheckConfig.invoked(...)

        mock_print.assert_any_call("Configuration files:")
        mock_print.assert_any_call("Problems:")
        mock_print.assert_any_call("- ", "Test problem")
        self.assertEqual(ret_val, 1)

    def test_register_argument(self):
        self_mock = MagicMock()
        parser_mock = MagicMock()
        CheckConfig.register_argument(self_mock, parser_mock)

        self.assertTrue(parser_mock.add_argument.called)
