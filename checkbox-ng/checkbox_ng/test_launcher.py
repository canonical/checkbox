# This file is part of Checkbox.
#
# Copyright 2016 Canonical Ltd.
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
checkbox_ng.test_launcher
=========================

Test definitions for checkbox_ng.launcher module
"""

from unittest import TestCase
from textwrap import dedent

from plainbox.impl.secure.config import Unset

from launcher import LauncherDefinition
from launcher import LauncherDefinitionLegacy
from launcher import LauncherDefinition1


class LauncherDefinitionTests(TestCase):
    launcher_version_legacy = dedent("""
    [launcher]
    """)
    launcher_version_1 = dedent("""
    [launcher]
    launcher_version = 1
    """)
    launcher_version_future = dedent("""
    [launcher]
    launcher_version = 2
    """)

    def test_get_concrete_launcher_legacy(self):
        l = LauncherDefinition()
        l.read_string(self.launcher_version_legacy)
        cls = l.get_concrete_launcher().__class__
        self.assertIs(cls, LauncherDefinitionLegacy)

    def test_get_concrete_launcher_launcher1(self):
        l = LauncherDefinition()
        l.read_string(self.launcher_version_1)
        cls = l.get_concrete_launcher().__class__
        self.assertIs(cls, LauncherDefinition1)

    def test_get_concrete_launcher_future_raises(self):
        l = LauncherDefinition()
        l.read_string(self.launcher_version_future)
        with self.assertRaises(KeyError):
            l.get_concrete_launcher()


class LauncherDefinitionLegacyTests(TestCase):
    def test_defaults(self):
        empty_launcher = ''
        l = LauncherDefinitionLegacy()
        l.read_string(empty_launcher)
        self.assertEqual(l.title, Unset)
        self.assertEqual(l.api_flags, [])
        self.assertEqual(l.api_version, '0.99')
        self.assertEqual(l.text, Unset)
        self.assertEqual(l.whitelist_filter, Unset)
        self.assertEqual(l.whitelist_selection, Unset)
        self.assertEqual(l.skip_whitelist_selection, False)
        self.assertEqual(l.skip_test_selection, False)
        self.assertEqual(l.input_type, Unset)
        self.assertEqual(l.ok_btn_text, Unset)
        self.assertEqual(l.submit_to_hexr, Unset)
        self.assertEqual(l.submit_to, Unset)
        self.assertEqual(l.submit_url, Unset)
        self.assertEqual(l.secure_id, Unset)
        self.assertEqual(l.exporter, Unset)


class LauncherDefinition1Tests(TestCase):

    def test_defaults(self):
        empty_launcher = dedent("""
        [launcher]
        launcher_version = 1
        """)
        l = LauncherDefinition1()
        l.read_string(empty_launcher)
        self.assertEqual(l.api_version, '0.99')
        self.assertEqual(l.app_id, 'checkbox-cli')
        self.assertEqual(l.api_flags, [])
        self.assertEqual(l.providers, ['*'])
        self.assertEqual(l.test_plan_filters, ['*'])
        self.assertEqual(l.test_plan_default_selection, Unset)
        self.assertEqual(l.test_plan_forced, False)
        self.assertEqual(l.test_selection_forced, False)
        self.assertEqual(l.ui_type, 'interactive')
        self.assertEqual(l.restart_strategy, Unset)

    def test_smoke(self):
        definition = dedent("""
        [launcher]
        launcher_version = 1
        api_version = 0.99
        api_flags = restartable
        app_id = FOOBAR
        [providers]
        use = foo* bar*, baz
        [test plan]
        unit = 2000.the.chosen.one
        filter = 2000*, 3000* tp_foo*
        forced = yes
        [test selection]
        forced = yes
        [ui]
        type = silent
        [restart]
        strategy = magic
        [report:foo_report]
        exporter = bar_exporter
        transport = file
        [exporter:bar_exporter]
        unit = bar_exporter_unit
        [transport:file]
        path = /tmp/path
        """)
        l = LauncherDefinition1()
        l.read_string(definition)
        self.assertEqual(l.api_version, '0.99')
        self.assertEqual(l.app_id, 'FOOBAR')
        self.assertEqual(l.api_flags, ['restartable'])
        self.assertEqual(l.providers, ['foo*', 'bar*', 'baz'])
        self.assertEqual(l.test_plan_filters, ['2000*', '3000*', 'tp_foo*'])
        self.assertEqual(l.test_plan_default_selection, '2000.the.chosen.one')
        self.assertEqual(l.test_plan_forced, True)
        self.assertEqual(l.test_selection_forced, True)
        self.assertEqual(l.ui_type, 'silent')
        self.assertEqual(l.restart_strategy, 'magic')
        self.assertEqual(l.reports, {
            'foo_report': {'exporter': 'bar_exporter', 'transport': 'file'}})
        self.assertEqual(l.exporters, {
            'bar_exporter': {'unit': 'bar_exporter_unit'}})
        self.assertEqual(l.transports, {
            'file': {'path': '/tmp/path'}})
