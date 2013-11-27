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
from plainbox.vendor.mock import patch


class TestJobDefinition(TestCase):

    def setUp(self):
        self._full_record = {
            'plugin': 'plugin',
            'command': 'command',
            'environ': 'environ',
            'user': 'user'
        }
        self._min_record = {
            'plugin': 'plugin',
            'name': 'name',
        }

    def test_smoke_full_record(self):
        job = BaseJob(self._full_record)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.command, "command")
        self.assertEqual(job.environ, "environ")
        self.assertEqual(job.user, "user")

    def test_smoke_min_record(self):
        job = BaseJob(self._min_record)
        self.assertEqual(job.plugin, "plugin")
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
            'name': 'name',
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


class JobEnvTests(TestCase):

    def setUp(self):
        self.job = BaseJob({'plugin': 'plugin', 'environ': 'foo'})

    def test_checkbox_env(self):
        base_env = {"PATH": "", 'foo': 'bar', 'baz': 'qux'}
        path = '/usr/share/checkbox-lambda'
        with patch.dict('os.environ', {}):
            env = self.job.modify_execution_environment(base_env, [path])
            self.assertEqual(env['CHECKBOX_LAMBDA_SHARE'], path)
            self.assertEqual(env['foo'], 'bar')
            self.assertNotIn('bar', env)

    def test_checkbox_env_with_data_dir(self):
        base_env = {"PATH": "", "CHECKBOX_DATA": "DEADBEEF"}
        path = '/usr/share/checkbox-lambda'
        with patch.dict('os.environ', {"CHECKBOX_DATA": "DEADBEEF"}):
            env = self.job.modify_execution_environment(base_env, [path])
            self.assertEqual(env['CHECKBOX_LAMBDA_SHARE'], path)
            self.assertEqual(env['CHECKBOX_DATA'], "DEADBEEF")
