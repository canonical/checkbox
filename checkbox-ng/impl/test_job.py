# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.test_job
======================

Test definitions for plainbox.impl.job module
"""

from unittest import TestCase

from plainbox.impl.job import JobDefinition


class TestJobDefinition(TestCase):

    _full_data = {
        'plugin': 'plugin',
        'name': 'name',
        'requires': 'requires',
        'command': 'command',
        'description': 'description'
    }

    _full_gettext_data = {
        '_plugin': 'plugin',
        '_name': 'name',
        '_requires': 'requires',
        '_command': 'command',
        '_description': 'description'
    }

    _min_data = {
        'plugin': 'plugin',
        'name': 'name',
    }

    def test_smoke_full_data(self):
        job = JobDefinition(self._full_data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.name, "name")
        self.assertEqual(job.requires, "requires")
        self.assertEqual(job.command, "command")
        self.assertEqual(job.description, "description")

    def test_smoke_full_gettext_data(self):
        job = JobDefinition(self._full_gettext_data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.name, "name")
        self.assertEqual(job.requires, "requires")
        self.assertEqual(job.command, "command")
        self.assertEqual(job.description, "description")

    def test_smoke_min_data(self):
        job = JobDefinition(self._min_data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.name, "name")
        self.assertEqual(job.requires, None)
        self.assertEqual(job.command, None)
        self.assertEqual(job.description, None)

    def test_from_rfc822_record_full_data(self):
        job = JobDefinition.from_rfc822_record(self._full_data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.name, "name")
        self.assertEqual(job.requires, "requires")
        self.assertEqual(job.command, "command")
        self.assertEqual(job.description, "description")

    def test_from_rfc822_record_min_data(self):
        job = JobDefinition.from_rfc822_record(self._min_data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.name, "name")
        self.assertEqual(job.requires, None)
        self.assertEqual(job.command, None)
        self.assertEqual(job.description, None)

    def test_from_rfc822_record_missing_name(self):
        self.assertRaises(ValueError,
                          JobDefinition.from_rfc822_record,
                          {'plugin': 'plugin'})

    def test_from_rfc822_record_missing_plugin(self):
        self.assertRaises(ValueError,
                          JobDefinition.from_rfc822_record,
                          {'name': 'name'})

    def test_str(self):
        job = JobDefinition(self._min_data)
        self.assertEqual(str(job), self._min_data['name'])

    def test_repr(self):
        job = JobDefinition(self._min_data)
        self.assertEqual(repr(job), "<JobDefinition name:'name' plugin:'plugin'>")

    def test_depedency_parsing_empty(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin'})
        expected = set()
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)

    def test_depedency_parsing_commas(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'depends': 'foo,bar,froz'})
        expected = set({'foo', 'bar', 'froz'})
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)

    def test_depedency_parsing_spaces(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'depends': 'foo bar froz'})
        expected = set({'foo', 'bar', 'froz'})
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)

    def test_depedency_parsing_tabs(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'depends': 'foo\tbar\tfroz'})
        expected = set({'foo', 'bar', 'froz'})
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)

    def test_depedency_parsing_newlines(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'depends': 'foo\nbar\nfroz'})
        expected = set({'foo', 'bar', 'froz'})
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)

    def test_depedency_parsing_spaces_and_commas(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'depends': 'foo, bar, froz'})
        expected = set({'foo', 'bar', 'froz'})
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)

    def test_depedency_parsing_multiple_spaces(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'depends': 'foo   bar'})
        expected = set({'foo', 'bar'})
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)

    def test_depedency_parsing_multiple_commas(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'depends': 'foo,,,,bar'})
        expected = set({'foo', 'bar'})
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)

    def test_resource_parsing_empty(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin'})
        expected = set()
        observed = job.get_resource_dependencies()
        self.assertEqual(expected, observed)

    def test_resource_parsing_typical(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'requires': 'foo.bar == 10'})
        expected = set(['foo'])
        observed = job.get_resource_dependencies()
        self.assertEqual(expected, observed)

    def test_resource_parsing_many(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'requires': (
                "foo.bar == 10\n"
                "froz.bot == 10\n")})
        expected = set(['foo', 'froz'])
        observed = job.get_resource_dependencies()
        self.assertEqual(expected, observed)

    def test_resource_parsing_broken(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'requires': "foo.bar == bar"})
        self.assertRaises(Exception, job.get_resource_dependencies)
