# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
plainbox.impl.secure.test_job
=============================

Test definitions for plainbox.impl.secure.job module
"""

from unittest import TestCase

from plainbox.impl.secure.job import BaseJob
from plainbox.testing_utils.testcases import TestCaseWithParameters


class TestJobDefinition(TestCase):

    def test_get_raw_record_value(self):
        """
        Ensure that get_raw_record_value() works okay
        """
        job1 = BaseJob({'key': 'value'}, {'key': 'raw-value'})
        job2 = BaseJob({'_key': 'value'}, {'_key': 'raw-value'})
        self.assertEqual(job1.get_raw_record_value('key'), 'raw-value')
        self.assertEqual(job2.get_raw_record_value('key'), 'raw-value')

    def test_get_record_value(self):
        """
        Ensure that get_record_value() works okay
        """
        job1 = BaseJob({'key': 'value'}, {'key': 'raw-value'})
        job2 = BaseJob({'_key': 'value'}, {'_key': 'raw-value'})
        self.assertEqual(job1.get_record_value('key'), 'value')
        self.assertEqual(job2.get_record_value('key'), 'value')

    def test_properties(self):
        """
        Ensure that properties are looked up in the non-raw copy of the data
        """
        job = BaseJob({
            'plugin': 'plugin-value',
            'command': 'command-value',
            'environ': 'environ-value',
            'user': 'user-value',
        }, {
            'plugin': 'plugin-raw',
            'command': 'command-raw',
            'environ': 'environ-raw',
            'user': 'user-raw',
        })
        self.assertEqual(job.plugin, "plugin-value")
        self.assertEqual(job.command, "command-value")
        self.assertEqual(job.environ, "environ-value")
        self.assertEqual(job.user, "user-value")

    def test_properties_default_values(self):
        """
        Ensure that all properties default to None
        """
        job = BaseJob({})
        self.assertEqual(job.plugin, None)
        self.assertEqual(job.command, None)
        self.assertEqual(job.environ, None)
        self.assertEqual(job.user, None)

    def test_checksum_smoke(self):
        job1 = BaseJob({'plugin': 'plugin', 'user': 'root'})
        identical_to_job1 = BaseJob({'plugin': 'plugin', 'user': 'root'})
        # Two distinct but identical jobs have the same checksum
        self.assertEqual(job1.checksum, identical_to_job1.checksum)
        job2 = BaseJob({'plugin': 'plugin', 'user': 'anonymous'})
        # Two jobs with different definitions have different checksum
        self.assertNotEqual(job1.checksum, job2.checksum)
        # The checksum is stable and does not change over time
        self.assertEqual(
            job1.checksum,
            "c47cc3719061e4df0010d061e6f20d3d046071fd467d02d093a03068d2f33400")

    def test_get_environ_settings(self):
        job1 = BaseJob({})
        self.assertEqual(job1.get_environ_settings(), set())
        job2 = BaseJob({'environ': 'a b c'})
        self.assertEqual(job2.get_environ_settings(), set(['a', 'b', 'c']))
        job3 = BaseJob({'environ': 'a,b,c'})
        self.assertEqual(job3.get_environ_settings(), set(['a', 'b', 'c']))


class ParsingTests(TestCaseWithParameters):

    parameter_names = ('glue',)
    parameter_values = (
        ('commas',),
        ('spaces',),
        ('tabs',),
        ('newlines',),
        ('spaces_and_commas',),
        ('multiple_spaces',),
        ('multiple_commas',)
    )
    parameters_keymap = {
        'commas': ',',
        'spaces': ' ',
        'tabs': '\t',
        'newlines': '\n',
        'spaces_and_commas': ', ',
        'multiple_spaces': '   ',
        'multiple_commas': ',,,,'
    }

    def test_environ_parsing_with_various_separators(self):
        job = BaseJob({
            'id': 'id',
            'plugin': 'plugin',
            'environ': self.parameters_keymap[
                self.parameters.glue].join(['foo', 'bar', 'froz'])})
        expected = set({'foo', 'bar', 'froz'})
        observed = job.get_environ_settings()
        self.assertEqual(expected, observed)

    def test_environ_parsing_empty(self):
        job = BaseJob({'plugin': 'plugin'})
        expected = set()
        observed = job.get_environ_settings()
        self.assertEqual(expected, observed)
