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

import os
from unittest import TestCase

from plainbox.impl.applogic import PlainBoxConfig
from plainbox.impl.job import CheckBoxJobValidator
from plainbox.impl.job import JobDefinition
from plainbox.impl.job import JobOutputTextSource
from plainbox.impl.job import Problem
from plainbox.impl.job import ValidationError
from plainbox.impl.rfc822 import FileTextSource
from plainbox.impl.rfc822 import Origin
from plainbox.impl.rfc822 import RFC822Record
from plainbox.testing_utils.testcases import TestCaseWithParameters
from plainbox.vendor.mock import Mock


class CheckBoxJobValidatorTests(TestCase):

    def test_validate_checks_for_missing_name(self):
        """
        verify that validate() checks if jobs have a value for the 'name'
        field.
        """
        job = JobDefinition({})
        with self.assertRaises(ValidationError) as boom:
            CheckBoxJobValidator.validate(job)
        self.assertEqual(boom.exception.field, JobDefinition.fields.name)
        self.assertEqual(boom.exception.problem, Problem.missing)

    def test_validate_checks_for_missing_plugin(self):
        """
        verify that validate() checks if jobs have a value for the 'plugin'
        field.
        """
        job = JobDefinition({
            'name': 'name'
        })
        with self.assertRaises(ValidationError) as boom:
            CheckBoxJobValidator.validate(job)
        self.assertEqual(boom.exception.field, JobDefinition.fields.plugin)
        self.assertEqual(boom.exception.problem, Problem.missing)

    def test_validate_checks_for_unknown_plugins(self):
        """
        verify that validate() checks if jobs have a known value for the
        'plugin' field.
        """
        job = JobDefinition({
            'name': 'name',
            'plugin': 'dummy'
        })
        with self.assertRaises(ValidationError) as boom:
            CheckBoxJobValidator.validate(job)
        self.assertEqual(boom.exception.field, JobDefinition.fields.plugin)
        self.assertEqual(boom.exception.problem, Problem.wrong)

    def test_validate_checks_for_uselss_user(self):
        """
        verify that validate() checks for jobs that have the 'user' field but
        don't have the 'command' field.
        """
        job = JobDefinition({
            'name': 'name',
            'plugin': 'shell',
            'user': 'root'
        })
        with self.assertRaises(ValidationError) as boom:
            CheckBoxJobValidator.validate(job)
        self.assertEqual(boom.exception.field, JobDefinition.fields.user)
        self.assertEqual(boom.exception.problem, Problem.useless)

    def test_validate_checks_for_uselss_environ(self):
        """
        verify that validate() checks for jobs that have the 'environ' field
        but don't have the 'command' field.
        """
        job = JobDefinition({
            'name': 'name',
            'plugin': 'shell',
            'environ': 'VAR_NAME'
        })
        with self.assertRaises(ValidationError) as boom:
            CheckBoxJobValidator.validate(job)
        self.assertEqual(boom.exception.field, JobDefinition.fields.environ)
        self.assertEqual(boom.exception.problem, Problem.useless)

    def test_validate_checks_for_description_on_manual_jobs(self):
        """
        verify that validate() checks for manual jobs that don't have a value
        for the 'description' field.
        """
        job = JobDefinition({
            'name': 'name',
            'plugin': 'manual',
        })
        with self.assertRaises(ValidationError) as boom:
            CheckBoxJobValidator.validate(job)
        self.assertEqual(boom.exception.field,
                         JobDefinition.fields.description)
        self.assertEqual(boom.exception.problem, Problem.missing)

    def test_validate_checks_for_command_on_manual_jobs(self):
        """
        verify that validate() checks for manual jobs that have a value for the
        'command' field.
        """
        job = JobDefinition({
            'name': 'name',
            'plugin': 'manual',
            'description': 'Runs some test',
            'command': 'run_some_test'
        })
        with self.assertRaises(ValidationError) as boom:
            CheckBoxJobValidator.validate(job)
        self.assertEqual(boom.exception.field, JobDefinition.fields.command)
        self.assertEqual(boom.exception.problem, Problem.useless)


class CheckBoxJobValidatorTests2(TestCaseWithParameters):
    """
    Continuation of unit tests for CheckBoxJobValidator.

    Moved to a separate class because of limitations of TestCaseWithParameters
    which operates on the whole class.
    """

    parameter_names = ('plugin',)
    parameter_values = (
        ('shell',), ('local',), ('resource',), ('attachment',),
        ('user-verify',), ('user-interact',),)

    def test_validate_checks_for_missing_command(self):
        """
        verify that validate() checks if jobs have a value for the 'command'
        field.
        """
        job = JobDefinition({
            'name': 'name',
            'plugin': self.parameters.plugin
        })
        with self.assertRaises(ValidationError) as boom:
            CheckBoxJobValidator.validate(job)
        self.assertEqual(boom.exception.field, JobDefinition.fields.command)
        self.assertEqual(boom.exception.problem, Problem.missing)

    def test_validate_checks_for_wrong_user(self):
        """
        verify that validate() checks if jobs have a wrong value for the 'user'
        field.

        This field has been limited to either not defined or 'root' for sanity.
        While other choices _may_ be possible having just the two makes our job
        easier.
        """
        job = JobDefinition({
            'name': 'name',
            'plugin': self.parameters.plugin,
            'command': 'true',
            'user': 'fred',
        })
        with self.assertRaises(ValidationError) as boom:
            CheckBoxJobValidator.validate(job)
        self.assertEqual(boom.exception.field, JobDefinition.fields.user)
        self.assertEqual(boom.exception.problem, Problem.wrong)


class TestJobDefinition(TestCase):

    def setUp(self):
        self._full_record = RFC822Record({
            'plugin': 'plugin',
            'name': 'name',
            'requires': 'requires',
            'command': 'command',
            'description': 'description'
        }, Origin(FileTextSource('file.txt'), 1, 5))
        self._full_gettext_record = RFC822Record({
            '_plugin': 'plugin',
            '_name': 'name',
            '_requires': 'requires',
            '_command': 'command',
            '_description': 'description'
        }, Origin(FileTextSource('file.txt.in'), 1, 5))
        self._min_record = RFC822Record({
            'plugin': 'plugin',
            'name': 'name',
        }, Origin(FileTextSource('file.txt'), 1, 2))

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
        record = RFC822Record({'plugin': 'plugin'})
        with self.assertRaises(ValueError):
            JobDefinition.from_rfc822_record(record)

    def test_str(self):
        job = JobDefinition(self._min_record.data)
        self.assertEqual(str(job), "name")

    def test_repr(self):
        job = JobDefinition(self._min_record.data)
        expected = "<JobDefinition name:'name' plugin:'plugin'>"
        observed = repr(job)
        self.assertEqual(expected, observed)

    def test_dependency_parsing_empty(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin'})
        expected = set()
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)

    def test_dependency_parsing_single_word(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'depends': 'word'})
        expected = set(['word'])
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)

    def test_environ_parsing_empty(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin'})
        expected = set()
        observed = job.get_environ_settings()
        self.assertEqual(expected, observed)

    def test_environ_parsing_single_word(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'environ': 'word'})
        expected = set(['word'])
        observed = job.get_environ_settings()
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

    def test_checksum_smoke(self):
        job1 = JobDefinition({
            'name': 'name',
            'plugin': 'plugin'
        })
        identical_to_job1 = JobDefinition({
            'name': 'name',
            'plugin': 'plugin'
        })
        # Two distinct but identical jobs have the same checksum
        self.assertEqual(job1.get_checksum(), identical_to_job1.get_checksum())
        job2 = JobDefinition({
            'name': 'other name',
            'plugin': 'plugin'
        })
        # Two jobs with different definitions have different checksum
        self.assertNotEqual(job1.get_checksum(), job2.get_checksum())
        # The checksum is stable and does not change over time
        self.assertEqual(
            job1.get_checksum(),
            "ad137ba3654827cb07a254a55c5e2a8daa4de6af604e84ccdbe9b7f221014362")

    def test_via_does_not_change_checksum(self):
        """
        verify that the 'via' attribute in no way influences job checksum
        """
        # Create a 'parent' job
        parent = JobDefinition({'name': 'parent', 'plugin': 'local'})
        # Create a 'child' job, using create_child_job_from_record() should
        # time the two so that child.via should be parent.checksum.
        #
        # The elaborate record that gets passed has all the meta-data that
        # traces back to the 'parent' job (as well as some imaginary line_start
        # and line_end values for the purpose of the test).
        child = parent.create_child_job_from_record(
            RFC822Record(
                data={'name': 'test', 'plugin': 'shell'},
                origin=Origin(
                    source=JobOutputTextSource(parent),
                    line_start=1,
                    line_end=1)))
        # Now 'child.via' should be the same as 'parent.checksum'
        self.assertEqual(child.via, parent.get_checksum())
        # Create an unrelated job 'helper' with the definition identical as
        # 'child' but without any ties to the 'parent' job
        helper = JobDefinition({'name': 'test', 'plugin': 'shell'})
        # And again, child.checksum should be the same as helper.checksum
        self.assertEqual(child.get_checksum(), helper.get_checksum())

    def test_estimated_duration(self):
        job1 = JobDefinition({})
        self.assertEqual(job1.estimated_duration, None)
        job2 = JobDefinition({'estimated_duration': 'foo'})
        self.assertEqual(job2.estimated_duration, None)
        job3 = JobDefinition({'estimated_duration': '123.5'})
        self.assertEqual(job3.estimated_duration, 123.5)


class TestJobDefinitionStartup(TestCaseWithParameters):
    """
    Continuation of unit tests for TestJobDefinition.

    Moved to a separate class because of limitations of TestCaseWithParameters
    which operates on the whole class.
    """

    parameter_names = ('plugin',)
    parameter_values = (
        ('shell',),
        ('attachment',),
        ('resource',),
        ('local',),
        ('manual',),
        ('user-interact',),
        ('user-verify',),
        ('user-interact-verify',)
    )
    parameters_keymap = {
        'shell': False,
        'attachment': False,
        'resource': False,
        'local': False,
        'manual': True,
        'user-interact': True,
        'user-verify': False,
        'user-interact-verify': True,
    }

    def test_startup_user_interaction_required(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': self.parameters.plugin})
        expected = self.parameters_keymap[self.parameters.plugin]
        observed = job.startup_user_interaction_required
        self.assertEqual(expected, observed)


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
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'environ': self.parameters_keymap[
                self.parameters.glue].join(['foo', 'bar', 'froz'])})
        expected = set({'foo', 'bar', 'froz'})
        observed = job.get_environ_settings()
        self.assertEqual(expected, observed)

    def test_dependency_parsing_with_various_separators(self):
        job = JobDefinition({
            'name': 'name',
            'plugin': 'plugin',
            'depends': self.parameters_keymap[
                self.parameters.glue].join(['foo', 'bar', 'froz'])})
        expected = set({'foo', 'bar', 'froz'})
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)


class JobEnvTests(TestCase):

    def setUp(self):
        self.job = JobDefinition({
            'name': 'name',
            'environ': 'foo bar froz'
        })
        self.job._provider = Mock()
        self.job._provider.extra_PYTHONPATH = None
        self.job._provider.extra_PATH = "value-of-extra-path"
        self.job._provider.CHECKBOX_SHARE = "checkbox-share-value"
        self.session_dir = "session-dir-value"
        self.checkbox_data_dir = os.path.join(
            self.session_dir, "CHECKBOX_DATA")

    def test_provider_env(self):
        env = {
            "PATH": ""
        }
        self.job.modify_execution_environment(
            env, self.session_dir, self.checkbox_data_dir)
        self.assertEqual(env['CHECKBOX_SHARE'], 'checkbox-share-value')
        self.assertEqual(env['CHECKBOX_DATA'],
                         os.path.join(self.session_dir, "CHECKBOX_DATA"))

    def test_without_config(self):
        env = {
            "PATH": "",
            # foo is not defined in the environment
            'bar': 'old-bar-value'
            # froz is not defined in the environment
        }
        # Ask the job to modify the environment
        self.job.modify_execution_environment(
            env, self.session_dir, self.checkbox_data_dir)
        # Check how foo bar and froz look like now
        self.assertNotIn('foo', env)
        self.assertEqual(env['bar'], 'old-bar-value')
        self.assertNotIn('froz', env)

    def test_with_config_and_environ_variables(self):
        env = {
            "PATH": "",
            # foo is not defined in the environment
            'bar': 'old-bar-value'
            # froz is not defined in the environment
        }
        # Setup a configuration object with values for foo and bar
        config = PlainBoxConfig()
        config.environment = {
            'foo': 'foo-value',
            'bar': 'bar-value'
        }
        # Ask the job to modify the environment
        self.job.modify_execution_environment(
            env, self.session_dir, self.checkbox_data_dir, config)
        # foo got copied from the config
        self.assertEqual(env['foo'], 'foo-value')
        # bar from the old environment
        self.assertEqual(env['bar'], 'old-bar-value')
        # froz is still empty
        self.assertNotIn('froz', env)

    def test_with_config_and_variables_not_in_environ(self):
        env = {
            'bar': 'old-bar-value'
        }
        # Setup a configuration object with values for baz.
        # Note that baz is *not* declared in the job's environ line.
        config = PlainBoxConfig()
        config.environment = {
            'baz': 'baz-value'
        }
        # Ask the job to modify the environment
        self.job.modify_execution_environment(
            env, self.session_dir, self.checkbox_data_dir, config)
        # bar from the old environment
        self.assertEqual(env['bar'], 'old-bar-value')
        # baz from the config environment
        self.assertEqual(env['baz'], 'baz-value')
