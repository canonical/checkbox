# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
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

"""Unit tests for config module."""

import textwrap
from unittest import TestCase
from unittest.mock import MagicMock, patch

from plainbox.impl.config import Configuration

from checkbox_ng.config import (
    _search_configs_by_name,
    load_config,
    load_launcher_text,
    resolve_configs,
)


@patch("checkbox_ng.config.os.path.exists")
@patch("checkbox_ng.config.expand_all")
class SearchConfigsByNameTests(TestCase):

    @patch("os.path.isabs", return_value=True)
    def test_absolute_path_returns_as_is(
        self, isabs_mock, expand_mock, exists_mock
    ):
        expand_mock.return_value = "/absolute/path/to/config"

        result = _search_configs_by_name("/absolute/path/to/config", None)

        self.assertEqual(result, ["/absolute/path/to/config"])

    @patch("os.path.isabs", return_value=False)
    def test_provider_launcher_id_returns_as_is(
        self, isabs_mock, expand_mock, exists_mock
    ):
        expand_mock.return_value = "com.canonical.certification::launcher_id"
        session_assistant = MagicMock()
        session_assistant.is_provider_launcher_id.return_value = True

        result = _search_configs_by_name(
            "com.canonical.certification::launcher_id", session_assistant
        )

        self.assertEqual(result, ["com.canonical.certification::launcher_id"])

    @patch("os.path.isabs", return_value=False)
    def test_searches_all_dirs_returns_existing(
        self, isabs_mock, expand_mock, exists_mock
    ):
        session_assistant = MagicMock()
        session_assistant.is_provider_launcher_id.return_value = False

        expand_mock.side_effect = lambda x: x
        exists_mock.side_effect = lambda p: p in [
            "~/.config/config.conf",
        ]

        result = _search_configs_by_name("config.conf", session_assistant)

        self.assertEqual(
            result,
            ["~/.config/config.conf"],
        )

    @patch("os.path.isabs", return_value=False)
    def test_no_configs_found_returns_empty(
        self, isabs_mock, expand_mock, exists_mock
    ):
        session_assistant = MagicMock()
        session_assistant.is_provider_launcher_id.return_value = False
        expand_mock.side_effect = lambda p: p
        exists_mock.return_value = False

        result = _search_configs_by_name("nonexistent.conf", session_assistant)

        self.assertEqual(result, [])


@patch("checkbox_ng.config.Configuration")
class LoadConfigTests(TestCase):

    def test_load_from_provider_launcher(self, config_mock):
        session_assistant = MagicMock()
        session_assistant.get_provider_launcher_by_id.return_value = (
            "config_text"
        )
        config_mock.from_text.return_value = "config_object"

        result = load_config(
            "com.canonical.certification::config_id", session_assistant
        )

        session_assistant.get_provider_launcher_by_id.assert_called_once_with(
            "com.canonical.certification::config_id"
        )
        self.assertTrue(config_mock.from_text.called)
        self.assertEqual(result, "config_object")

    def test_load_from_path_when_provider_not_found(self, config_mock):
        session_assistant = MagicMock()
        session_assistant.get_provider_launcher_by_id.side_effect = (
            FileNotFoundError
        )
        config_mock.from_path.return_value = "config_from_path"

        result = load_config("/path/to/config", session_assistant)

        self.assertTrue(config_mock.from_path.called)
        self.assertEqual(result, "config_from_path")


@patch("checkbox_ng.config.load_config")
@patch("checkbox_ng.config._search_configs_by_name")
class ResolveConfigsTests(TestCase):

    def test_no_launcher_config_uses_default(self, search_mock, load_mock):
        session_assistant = MagicMock()
        search_mock.return_value = []

        result = resolve_configs(None, session_assistant)

        self.assertEqual(search_mock.call_count, 1)
        self.assertIsNotNone(result)

    def test_launcher_config_overrides_all(self, search_mock, load_mock):
        session_assistant = MagicMock()

        launcher_text = textwrap.dedent(
            """
            [config]
            config_filename=global.conf
            [environment]
            FROM_LAUNCHER = yes
            SHARED_VAR = launcher
            """
        ).strip()
        launcher_config = Configuration.from_text(
            launcher_text, "launcher_source"
        )

        global_text = textwrap.dedent(
            """
            [environment]
            FROM_GLOBAL = yes
            SHARED_VAR = global
            """
        ).strip()
        global_config = Configuration.from_text(
            global_text, "/etc/xdg/global.conf"
        )

        search_mock.return_value = ["/etc/xdg/global.conf"]
        load_mock.return_value = global_config

        result = resolve_configs(launcher_config, session_assistant)

        self.assertEqual(
            result.get_value("environment", "FROM_LAUNCHER"), "yes"
        )
        self.assertEqual(result.get_value("environment", "FROM_GLOBAL"), "yes")
        self.assertEqual(
            result.get_value("environment", "SHARED_VAR"), "launcher"
        )

    def test_config_chain_resolution(self, search_mock, load_mock):
        session_assistant = MagicMock()

        launcher_text = textwrap.dedent(
            """
            [config]
            config_filename = A
            [environment]
            FROM_LAUNCHER = yes
            SHARED_VAR = launcher
            """
        ).strip()
        launcher_config = Configuration.from_text(
            launcher_text, "launcher_source"
        )

        config_a_text = textwrap.dedent(
            """
            [config]
            config_filename = B
            [environment]
            FROM_A = yes
            SHARED_VAR = a
            # a should win this as it is in home and imports B
            A_PRIO_VARIABLE = a
            """
        ).strip()
        config_a = Configuration.from_text(
            config_a_text, "/home/user/.config/A"
        )

        config_b_text = textwrap.dedent(
            """
            [config]
            config_filename = C
            [environment]
            FROM_B = yes
            SHARED_VAR = b
            A_PRIO_VARIABLE = b
            # b should win this as it is in home and imports C
            B_PRIO_VARIABLE = b
            """
        ).strip()
        config_b = Configuration.from_text(
            config_b_text, "/home/user/.config/B"
        )

        config_c_text = textwrap.dedent(
            """
            [environment]
            FROM_C = yes
            SHARED_VAR = c
            A_PRIO_VARIABLE = c
            B_PRIO_VARIABLE = c
            """
        ).strip()
        config_c = Configuration.from_text(config_c_text, "/etc/xdg/C")

        def search_side_effect(name, sa):
            if name == "A":
                return ["/home/user/.config/A"]
            elif name == "B":
                return ["/home/user/.config/B"]
            elif name == "C":
                return ["/etc/xdg/C"]
            return []

        def load_side_effect(path, sa):
            if path == "/home/user/.config/A":
                return config_a
            elif path == "/home/user/.config/B":
                return config_b
            elif path == "/etc/xdg/C":
                return config_c
            return Configuration()

        search_mock.side_effect = search_side_effect
        load_mock.side_effect = load_side_effect

        result = resolve_configs(launcher_config, session_assistant)

        self.assertEqual(
            result.get_value("environment", "FROM_LAUNCHER"), "yes"
        )
        self.assertEqual(result.get_value("environment", "FROM_A"), "yes")
        self.assertEqual(result.get_value("environment", "FROM_B"), "yes")
        self.assertEqual(result.get_value("environment", "FROM_C"), "yes")
        self.assertEqual(
            result.get_value("environment", "SHARED_VAR"), "launcher"
        )
        self.assertEqual(
            result.get_value("environment", "A_PRIO_VARIABLE"), "a"
        )
        self.assertEqual(
            result.get_value("environment", "B_PRIO_VARIABLE"), "b"
        )

    def test_prevents_config_loops(self, search_mock, load_mock):
        session_assistant = MagicMock()

        launcher_text = textwrap.dedent(
            """
            [config]
            config_filename = A
            """
        ).strip()
        launcher_config = Configuration.from_text(
            launcher_text, "launcher_source"
        )

        config_a_text = textwrap.dedent(
            """
            [config]
            config_filename = B
            [environment]
            FROM_A = yes
            """
        ).strip()
        config_a = Configuration.from_text(config_a_text, "/config/A")

        config_b_text = textwrap.dedent(
            """
            [config]
            config_filename = A
            [environment]
            FROM_B = yes
            """
        ).strip()
        config_b = Configuration.from_text(config_b_text, "/config/B")

        def search_side_effect(name, sa):
            return ["/config/{}".format(name)]

        def load_side_effect(path, sa):
            if path == "/config/A":
                return config_a
            elif path == "/config/B":
                return config_b
            return Configuration()

        search_mock.side_effect = search_side_effect
        load_mock.side_effect = load_side_effect

        result = resolve_configs(launcher_config, session_assistant)

        self.assertEqual(result.get_value("environment", "FROM_A"), "yes")
        self.assertEqual(result.get_value("environment", "FROM_B"), "yes")
        self.assertEqual(load_mock.call_count, 2)

    def test_multiple_config_locations_priority(self, search_mock, load_mock):
        session_assistant = MagicMock()

        launcher_text = textwrap.dedent(
            """
            [config]
            config_filename = test.conf
            [environment]
            FROM_LAUNCHER = yes
            SHARED_VAR = launcher
            """
        ).strip()
        launcher_config = Configuration.from_text(
            launcher_text, "launcher_source"
        )

        config_home_text = textwrap.dedent(
            """
            [environment]
            FROM_HOME = yes
            SHARED_VAR = home
            """
        ).strip()
        config_home = Configuration.from_text(
            config_home_text, "/home/user/.config/test.conf"
        )

        config_etc_text = textwrap.dedent(
            """
            [environment]
            FROM_ETC = yes
            SHARED_VAR = etc
            """
        ).strip()
        config_etc = Configuration.from_text(
            config_etc_text, "/etc/xdg/test.conf"
        )

        search_mock.return_value = [
            "/home/user/.config/test.conf",
            "/etc/xdg/test.conf",
        ]

        def load_side_effect(path, sa):
            if path == "/home/user/.config/test.conf":
                return config_home
            elif path == "/etc/xdg/test.conf":
                return config_etc
            return Configuration()

        load_mock.side_effect = load_side_effect

        result = resolve_configs(launcher_config, session_assistant)

        self.assertEqual(
            result.get_value("environment", "FROM_LAUNCHER"), "yes"
        )
        self.assertEqual(result.get_value("environment", "FROM_HOME"), "yes")
        self.assertEqual(result.get_value("environment", "FROM_ETC"), "yes")
        self.assertEqual(
            result.get_value("environment", "SHARED_VAR"), "launcher"
        )


@patch("checkbox_ng.config.Path")
class LoadLauncherTextTests(TestCase):

    def test_launcher_text_None(self, _):
        self.assertEqual(load_launcher_text(None, None), "")

    def test_launcher_text_file(self, path_mock):
        path_mock().open().__enter__().read.return_value = "launcher_text"
        # tests that local files are read but also that they have precedence
        # over anything else. Clashing occasions are rare as launcher ids are
        # namespaced
        self.assertEqual(
            load_launcher_text("path_that_exists", None), "launcher_text"
        )

    def test_launcher_by_id(self, path_mock):
        path_mock().open.side_effect = FileNotFoundError
        session_assistant = MagicMock()
        session_assistant.get_provider_launcher_by_id.return_value = (
            "launcher_text"
        )
        self.assertEqual(
            load_launcher_text(
                "com.canonical.certification::launcher_id", session_assistant
            ),
            "launcher_text",
        )

    def test_launcher_doesnt_exist(self, path_mock):
        path_mock().open.side_effect = FileNotFoundError
        session_assistant = MagicMock()
        session_assistant.get_provider_launcher_by_id.side_effect = (
            FileNotFoundError
        )
        # This function is called in "presentation" code, so it should crash
        # the whole app if the provided launcher id/path doesn't exist
        with self.assertRaises(SystemExit):
            load_launcher_text("doesn't exist", session_assistant)
