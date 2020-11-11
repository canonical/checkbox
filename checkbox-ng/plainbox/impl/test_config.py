# This file is part of Checkbox.
#
# Copyright 2020 Canonical Ltd.
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
"""
This module contains tests for the new Checkbox Config module
"""
from contextlib import contextmanager
import logging
from unittest import TestCase
from unittest.mock import mock_open, patch

from plainbox.impl.config import Configuration


@contextmanager
def muted_logging():
    """Disable logging so the test that use this have no output."""
    saved_level = logging.root.getEffectiveLevel()
    logging.root.setLevel(logging.CRITICAL)
    yield
    logging.root.setLevel(saved_level)


class ConfigurationTests(TestCase):
    """Tests for the Configuration class."""

    def test_empty_file_yields_defaults(self):
        """A default configuration instance should have default values."""
        # let's check a few values from random sections
        cfg = Configuration()
        self.assertEqual(cfg.get_value('test plan', 'filter'), ['*'])
        self.assertTrue(cfg.get_value('launcher', 'local_submission'))
        self.assertEqual(cfg.get_value('daemon', 'normal_user'), '')

    @patch('os.path.isfile', return_value=True)
    def test_one_var_overwrites(self, _):
        """
        One variable properly shadows defaults.

        Having one (good) value in config should yield a config with
        defaults except the one var placed in the config file.
        """
        ini_data = """
        [launcher]
        stock_reports = text
        """
        with patch('builtins.open', mock_open(read_data=ini_data)):
            cfg = Configuration.from_path('unit test')
        self.assertEqual(cfg.get_value('test plan', 'filter'), ['*'])
        self.assertTrue(cfg.get_value('launcher', 'local_submission'))
        self.assertEqual(cfg.get_value('daemon', 'normal_user'), '')
        self.assertEqual(cfg.get_origin('daemon', 'normal_user'), '')
        self.assertEqual(cfg.get_value('launcher', 'stock_reports'), ['text'])
        self.assertEqual(
            cfg.get_origin('launcher', 'stock_reports'),
            'unit test')

    @patch('os.path.isfile', return_value=True)
    def test_string_list_distinction(self, _):
        """
        Parsing of lists and multi-word strings.

        Depending on the config spec the field can be considered a string
        (with spaces) or a list.
        """
        ini_data = """
        [launcher]
        launcher_version = 1
        stock_reports = submission_files, text
        session_title = A session title
        """
        with patch('builtins.open', mock_open(read_data=ini_data)):
            cfg = Configuration.from_path('unit test')
        self.assertEqual(
            cfg.get_value('launcher', 'stock_reports'),
            ['submission_files', 'text'])
        self.assertEqual(
            cfg.get_value('launcher', 'session_title'),
            'A session title')

    @patch('os.path.isfile', return_value=True)
    def test_unexpected_content(self, _):
        """
        Yield problems with extra data in configs.
        """
        ini_data = """
        [launcher]
        barfoo = 5
        [foobar]
        """
        with muted_logging():
            with patch('builtins.open', mock_open(read_data=ini_data)):
                cfg = Configuration.from_path('unit test')
            self.assertEqual(len(cfg.get_problems()), 2)

    def test_default_vars_are_not_supported(self):
        """
        Yield a problem when variable is defined in the [DEFAULT] section.
        """
        ini_data = """
        [DEFAULT]
        badvar = 4
        """
        with muted_logging():
            with patch('builtins.open', mock_open(read_data=ini_data)):
                cfg = Configuration.from_path('unit test')
            self.assertEqual(len(cfg.get_problems()), 1)

    @patch('os.path.isfile', return_value=False)
    def test_ini_not_found(self, _):
        """
        Yield a problem when an ini file cannot be opened.
        """
        with muted_logging():
            cfg = Configuration.from_path('invalid path')
        self.assertEqual(len(cfg.get_problems()), 1)
