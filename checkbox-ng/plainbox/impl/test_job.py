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
from plainbox.impl.rfc822 import RFC822Record
from plainbox.impl.rfc822 import Origin


class TestJobDefinition(TestCase):

    def setUp(self):
        self._full_record = RFC822Record({
            'plugin': 'plugin',
            'name': 'name',
            'requires': 'requires',
            'command': 'command',
            'description': 'description'
        }, Origin('file.txt', 1, 5))
        self._full_gettext_record = RFC822Record({
            '_plugin': 'plugin',
            '_name': 'name',
            '_requires': 'requires',
            '_command': 'command',
            '_description': 'description'
        }, Origin('file.txt.in', 1, 5))
        self._min_record = RFC822Record({
            'plugin': 'plugin',
            'name': 'name',
        }, Origin('file.txt', 1, 2))

    def test_smoke_full_record(self):
        job = JobDefinition(self._full_record.data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.name, "name")
        self.assertEqual(job.requires, "requires")
        self.assertEqual(job.command, "command")
        self.assertEqual(job.description, "description")

    def test_smoke_full_gettext_record(self):
        job = JobDefinition(self._full_gettext_record.data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.name, "name")
        self.assertEqual(job.requires, "requires")
        self.assertEqual(job.command, "command")
        self.assertEqual(job.description, "description")

    def test_smoke_min_record(self):
        job = JobDefinition(self._min_record.data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.name, "name")
        self.assertEqual(job.requires, None)
        self.assertEqual(job.command, None)
        self.assertEqual(job.description, None)

    def test_from_rfc822_record_full_record(self):
        job = JobDefinition.from_rfc822_record(self._full_record)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.name, "name")
        self.assertEqual(job.requires, "requires")
        self.assertEqual(job.command, "command")
        self.assertEqual(job.description, "description")

    def test_from_rfc822_record_min_record(self):
        job = JobDefinition.from_rfc822_record(self._min_record)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.name, "name")
        self.assertEqual(job.requires, None)
        self.assertEqual(job.command, None)
        self.assertEqual(job.description, None)

    def test_from_rfc822_record_missing_name(self):
        self.assertRaises(ValueError,
                          JobDefinition.from_rfc822_record,
                          RFC822Record({'plugin': 'plugin'}, None))

    def test_from_rfc822_record_missing_plugin(self):
        self.assertRaises(ValueError,
                          JobDefinition.from_rfc822_record,
                          RFC822Record({'name': 'name'}, None))

    def test_str(self):
        job = JobDefinition(self._min_record.data)
        self.assertEqual(str(job), "name")

    def test_repr(self):
        job = JobDefinition(self._min_record.data)
        expected = "<JobDefinition name:'name' plugin:'plugin'>"
        observed = repr(job)
        self.assertEqual(expected, observed)

    def test_depedency_parsing_empty(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin'})
        expected = set()
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)

    def test_depedency_parsing_single_word(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'depends': 'word'})
        expected = set(['word'])
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

    def test_encode(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'requires': "foo.bar == bar"})
        job_enc = job.__getstate__()
        self.assertEqual(job_enc['data']['plugin'], job.plugin)
        self.assertEqual(job_enc['data']['name'], job.name)
        with self.assertRaises(KeyError):
            job_enc['requires']
        with self.assertRaises(KeyError):
            job_enc['depends']
        with self.assertRaises(KeyError):
            job_enc['description']
        with self.assertRaises(KeyError):
            job_enc['command']
        with self.assertRaises(KeyError):
            job_enc['origin']
