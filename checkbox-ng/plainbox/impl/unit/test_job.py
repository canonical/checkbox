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
plainbox.impl.unit.test_job
===========================

Test definitions for plainbox.impl.unit.job module
"""

from unittest import TestCase

from plainbox.impl.secure.origin import FileTextSource
from plainbox.impl.secure.origin import JobOutputTextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.rfc822 import RFC822Record
from plainbox.impl.unit.job import JobDefinitionValidator
from plainbox.impl.unit.job import JobDefinition
from plainbox.impl.validation import Problem
from plainbox.impl.validation import ValidationError
from plainbox.testing_utils.testcases import TestCaseWithParameters
from plainbox.vendor import mock


class TestJobDefinitionDefinition(TestCase):

    def test_get_raw_record_value(self):
        """
        Ensure that get_raw_record_value() works okay
        """
        job1 = JobDefinition({'key': 'value'}, raw_data={'key': 'raw-value'})
        job2 = JobDefinition({'_key': 'value'}, raw_data={'_key': 'raw-value'})
        self.assertEqual(job1.get_raw_record_value('key'), 'raw-value')
        self.assertEqual(job2.get_raw_record_value('key'), 'raw-value')

    def test_get_record_value(self):
        """
        Ensure that get_record_value() works okay
        """
        job1 = JobDefinition({'key': 'value'}, raw_data={'key': 'raw-value'})
        job2 = JobDefinition({'_key': 'value'}, raw_data={'_key': 'raw-value'})
        self.assertEqual(job1.get_record_value('key'), 'value')
        self.assertEqual(job2.get_record_value('key'), 'value')

    def test_properties(self):
        """
        Ensure that properties are looked up in the non-raw copy of the data
        """
        job = JobDefinition({
            'plugin': 'plugin-value',
            'command': 'command-value',
            'environ': 'environ-value',
            'user': 'user-value',
            'shell': 'shell-value',
            'flags': 'flags-value',
        }, raw_data={
            'plugin': 'plugin-raw',
            'command': 'command-raw',
            'environ': 'environ-raw',
            'user': 'user-raw',
            'shell': 'shell-raw',
            'flags': 'flags-raw',
        })
        self.assertEqual(job.plugin, "plugin-value")
        self.assertEqual(job.command, "command-value")
        self.assertEqual(job.environ, "environ-value")
        self.assertEqual(job.user, "user-value")
        self.assertEqual(job.shell, "shell-value")
        self.assertEqual(job.flags, "flags-value")

    def test_properties_default_values(self):
        """
        Ensure that all properties default to None
        """
        job = JobDefinition({})
        self.assertEqual(job.plugin, None)
        self.assertEqual(job.command, None)
        self.assertEqual(job.environ, None)
        self.assertEqual(job.user, None)
        self.assertEqual(job.shell, 'bash')
        self.assertEqual(job.flags, None)

    def test_checksum_smoke(self):
        job1 = JobDefinition({'plugin': 'plugin', 'user': 'root'})
        identical_to_job1 = JobDefinition({'plugin': 'plugin', 'user': 'root'})
        # Two distinct but identical jobs have the same checksum
        self.assertEqual(job1.checksum, identical_to_job1.checksum)
        job2 = JobDefinition({'plugin': 'plugin', 'user': 'anonymous'})
        # Two jobs with different definitions have different checksum
        self.assertNotEqual(job1.checksum, job2.checksum)
        # The checksum is stable and does not change over time
        self.assertEqual(
            job1.checksum,
            "c47cc3719061e4df0010d061e6f20d3d046071fd467d02d093a03068d2f33400")

    def test_get_environ_settings(self):
        job1 = JobDefinition({})
        self.assertEqual(job1.get_environ_settings(), set())
        job2 = JobDefinition({'environ': 'a b c'})
        self.assertEqual(job2.get_environ_settings(), set(['a', 'b', 'c']))
        job3 = JobDefinition({'environ': 'a,b,c'})
        self.assertEqual(job3.get_environ_settings(), set(['a', 'b', 'c']))

    def test_get_flag_set(self):
        job1 = JobDefinition({})
        self.assertEqual(job1.get_flag_set(), set())
        job2 = JobDefinition({'flags': 'a b c'})
        self.assertEqual(job2.get_flag_set(), set(['a', 'b', 'c']))
        job3 = JobDefinition({'flags': 'a,b,c'})
        self.assertEqual(job3.get_flag_set(), set(['a', 'b', 'c']))


class JobDefinitionParsingTests(TestCaseWithParameters):

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
            'id': 'id',
            'plugin': 'plugin',
            'environ': self.parameters_keymap[
                self.parameters.glue].join(['foo', 'bar', 'froz'])})
        expected = set({'foo', 'bar', 'froz'})
        observed = job.get_environ_settings()
        self.assertEqual(expected, observed)

    def test_environ_parsing_empty(self):
        job = JobDefinition({'plugin': 'plugin'})
        expected = set()
        observed = job.get_environ_settings()
        self.assertEqual(expected, observed)


class JobDefinitionValidatorTests(TestCase):

    def test_validate_checks_for_deprecated_name(self):
        """
        verify that validate() checks if jobs have a value for the 'id'
        field.
        """
        job = JobDefinition({
            'name': 'name'
        })
        with self.assertRaises(ValidationError) as boom:
            JobDefinitionValidator.validate(job, deprecated=True)
        self.assertEqual(boom.exception.field, JobDefinition.fields.name)
        self.assertEqual(boom.exception.problem, Problem.deprecated)

    def test_validate_checks_for_missing_id(self):
        """
        verify that validate() checks if jobs have a value for the 'id'
        field.
        """
        job = JobDefinition({})
        with self.assertRaises(ValidationError) as boom:
            JobDefinitionValidator.validate(job)
        self.assertEqual(boom.exception.field, JobDefinition.fields.id)
        self.assertEqual(boom.exception.problem, Problem.missing)

    def test_validate_checks_for_missing_plugin(self):
        """
        verify that validate() checks if jobs have a value for the 'plugin'
        field.
        """
        job = JobDefinition({
            'id': 'id'
        })
        with self.assertRaises(ValidationError) as boom:
            JobDefinitionValidator.validate(job)
        self.assertEqual(boom.exception.field, JobDefinition.fields.plugin)
        self.assertEqual(boom.exception.problem, Problem.missing)

    def test_validate_checks_for_unknown_plugins(self):
        """
        verify that validate() checks if jobs have a known value for the
        'plugin' field.
        """
        job = JobDefinition({
            'id': 'id',
            'plugin': 'dummy'
        })
        with self.assertRaises(ValidationError) as boom:
            JobDefinitionValidator.validate(job)
        self.assertEqual(boom.exception.field, JobDefinition.fields.plugin)
        self.assertEqual(boom.exception.problem, Problem.wrong)

    def test_validate_checks_for_uselss_user(self):
        """
        verify that validate() checks for jobs that have the 'user' field but
        don't have the 'command' field.
        """
        job = JobDefinition({
            'id': 'id',
            'plugin': 'shell',
            'user': 'root'
        })
        with self.assertRaises(ValidationError) as boom:
            JobDefinitionValidator.validate(job, strict=True)
        self.assertEqual(boom.exception.field, JobDefinition.fields.user)
        self.assertEqual(boom.exception.problem, Problem.useless)

    def test_validate_checks_for_uselss_environ(self):
        """
        verify that validate() checks for jobs that have the 'environ' field
        but don't have the 'command' field.
        """
        job = JobDefinition({
            'id': 'id',
            'plugin': 'shell',
            'environ': 'VAR_NAME'
        })
        with self.assertRaises(ValidationError) as boom:
            JobDefinitionValidator.validate(job, strict=True)
        self.assertEqual(boom.exception.field, JobDefinition.fields.environ)
        self.assertEqual(boom.exception.problem, Problem.useless)

    def test_validate_checks_for_description_on_manual_jobs(self):
        """
        verify that validate() checks for manual jobs that don't have a value
        for the 'description' field.
        """
        job = JobDefinition({
            'id': 'id',
            'plugin': 'manual',
        })
        with self.assertRaises(ValidationError) as boom:
            JobDefinitionValidator.validate(job)
        self.assertEqual(boom.exception.field,
                         JobDefinition.fields.description)
        self.assertEqual(boom.exception.problem, Problem.missing)

    def test_validate_checks_for_command_on_manual_jobs(self):
        """
        verify that validate() checks for manual jobs that have a value for the
        'command' field.
        """
        job = JobDefinition({
            'id': 'id',
            'plugin': 'manual',
            'description': 'Runs some test',
            'command': 'run_some_test'
        })
        with self.assertRaises(ValidationError) as boom:
            JobDefinitionValidator.validate(job, strict=True)
        self.assertEqual(boom.exception.field, JobDefinition.fields.command)
        self.assertEqual(boom.exception.problem, Problem.useless)


class JobDefinitionValidatorTests2(TestCaseWithParameters):
    """
    Continuation of unit tests for JobDefinitionValidator.

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
            'id': 'id',
            'plugin': self.parameters.plugin
        })
        with self.assertRaises(ValidationError) as boom:
            JobDefinitionValidator.validate(job)
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
            'id': 'id',
            'plugin': self.parameters.plugin,
            'command': 'true',
            'user': 'fred',
        })
        with self.assertRaises(ValidationError) as boom:
            JobDefinitionValidator.validate(job)
        self.assertEqual(boom.exception.field, JobDefinition.fields.user)
        self.assertEqual(boom.exception.problem, Problem.wrong)


class TestJobDefinition(TestCase):

    def setUp(self):
        self._full_record = RFC822Record({
            'plugin': 'plugin',
            'id': 'id',
            'summary': 'summary',
            'requires': 'requires',
            'command': 'command',
            'description': 'description'
        }, Origin(FileTextSource('file.txt'), 1, 5))
        self._full_gettext_record = RFC822Record({
            '_plugin': 'plugin',
            '_id': 'id',
            '_summary': 'summary',
            '_requires': 'requires',
            '_command': 'command',
            '_description': 'description'
        }, Origin(FileTextSource('file.txt.in'), 1, 5))
        self._min_record = RFC822Record({
            'plugin': 'plugin',
            'id': 'id',
        }, Origin(FileTextSource('file.txt'), 1, 2))

    def test_smoke_full_record(self):
        job = JobDefinition(self._full_record.data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.id, "id")
        self.assertEqual(job.requires, "requires")
        self.assertEqual(job.command, "command")
        self.assertEqual(job.description, "description")

    def test_smoke_full_gettext_record(self):
        job = JobDefinition(self._full_gettext_record.data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.id, "id")
        self.assertEqual(job.requires, "requires")
        self.assertEqual(job.command, "command")
        self.assertEqual(job.description, "description")

    def test_smoke_min_record(self):
        job = JobDefinition(self._min_record.data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.id, "id")
        self.assertEqual(job.requires, None)
        self.assertEqual(job.command, None)
        self.assertEqual(job.description, None)

    def test_from_rfc822_record_full_record(self):
        job = JobDefinition.from_rfc822_record(self._full_record)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.id, "id")
        self.assertEqual(job.requires, "requires")
        self.assertEqual(job.command, "command")
        self.assertEqual(job.description, "description")

    def test_from_rfc822_record_min_record(self):
        job = JobDefinition.from_rfc822_record(self._min_record)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.id, "id")
        self.assertEqual(job.requires, None)
        self.assertEqual(job.command, None)
        self.assertEqual(job.description, None)

    def test_str(self):
        job = JobDefinition(self._min_record.data)
        self.assertEqual(str(job), "id")

    def test_id(self):
        # NOTE: this test will change when namespace support lands
        job = JobDefinition(self._min_record.data)
        self.assertEqual(job.id, "id")

    def test_partial_id(self):
        job = JobDefinition(self._min_record.data)
        self.assertEqual(job.partial_id, "id")

    def test_repr(self):
        job = JobDefinition(self._min_record.data)
        expected = "<JobDefinition id:'id' plugin:'plugin'>"
        observed = repr(job)
        self.assertEqual(expected, observed)

    def test_hash(self):
        job1 = JobDefinition(self._min_record.data)
        job2 = JobDefinition(self._min_record.data)
        job3 = JobDefinition(self._full_record.data)
        self.assertEqual(hash(job1), hash(job2))
        self.assertNotEqual(hash(job1), hash(job3))

    def test_dependency_parsing_empty(self):
        job = JobDefinition({
            'id': 'id',
            'plugin': 'plugin'})
        expected = set()
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)

    def test_dependency_parsing_single_word(self):
        job = JobDefinition({
            'id': 'id',
            'plugin': 'plugin',
            'depends': 'word'})
        expected = set(['word'])
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)

    def test_environ_parsing_empty(self):
        job = JobDefinition({
            'id': 'id',
            'plugin': 'plugin'})
        expected = set()
        observed = job.get_environ_settings()
        self.assertEqual(expected, observed)

    def test_environ_parsing_single_word(self):
        job = JobDefinition({
            'id': 'id',
            'plugin': 'plugin',
            'environ': 'word'})
        expected = set(['word'])
        observed = job.get_environ_settings()
        self.assertEqual(expected, observed)

    def test_resource_parsing_empty(self):
        job = JobDefinition({
            'id': 'id',
            'plugin': 'plugin'})
        expected = set()
        observed = job.get_resource_dependencies()
        self.assertEqual(expected, observed)

    def test_resource_parsing_typical(self):
        job = JobDefinition({
            'id': 'id',
            'plugin': 'plugin',
            'requires': 'foo.bar == 10'})
        expected = set(['foo'])
        observed = job.get_resource_dependencies()
        self.assertEqual(expected, observed)

    def test_resource_parsing_many(self):
        job = JobDefinition({
            'id': 'id',
            'plugin': 'plugin',
            'requires': (
                "foo.bar == 10\n"
                "froz.bot == 10\n")})
        expected = set(['foo', 'froz'])
        observed = job.get_resource_dependencies()
        self.assertEqual(expected, observed)

    def test_resource_parsing_broken(self):
        job = JobDefinition({
            'id': 'id',
            'plugin': 'plugin',
            'requires': "foo.bar == bar"})
        self.assertRaises(Exception, job.get_resource_dependencies)

    def test_checksum_smoke(self):
        job1 = JobDefinition({
            'id': 'id',
            'plugin': 'plugin'
        })
        identical_to_job1 = JobDefinition({
            'id': 'id',
            'plugin': 'plugin'
        })
        # Two distinct but identical jobs have the same checksum
        self.assertEqual(job1.checksum, identical_to_job1.checksum)
        job2 = JobDefinition({
            'id': 'other id',
            'plugin': 'plugin'
        })
        # Two jobs with different definitions have different checksum
        self.assertNotEqual(job1.checksum, job2.checksum)
        # The checksum is stable and does not change over time
        self.assertEqual(
            job1.checksum,
            "cd21b33e6a2f4d1291977b60d922bbd276775adce73fca8c69b4821c96d7314a")

    def test_via_does_not_change_checksum(self):
        """
        verify that the 'via' attribute in no way influences job checksum
        """
        # Create a 'parent' job
        parent = JobDefinition({'id': 'parent', 'plugin': 'local'})
        # Create a 'child' job, using create_child_job_from_record() should
        # time the two so that child.via should be parent.checksum.
        #
        # The elaborate record that gets passed has all the meta-data that
        # traces back to the 'parent' job (as well as some imaginary line_start
        # and line_end values for the purpose of the test).
        child = parent.create_child_job_from_record(
            RFC822Record(
                data={'id': 'test', 'plugin': 'shell'},
                origin=Origin(
                    source=JobOutputTextSource(parent),
                    line_start=1,
                    line_end=1)))
        # Now 'child.via' should be the same as 'parent.checksum'
        self.assertEqual(child.via, parent.checksum)
        # Create an unrelated job 'helper' with the definition identical as
        # 'child' but without any ties to the 'parent' job
        helper = JobDefinition({'id': 'test', 'plugin': 'shell'})
        # And again, child.checksum should be the same as helper.checksum
        self.assertEqual(child.checksum, helper.checksum)

    def test_estimated_duration(self):
        job1 = JobDefinition({})
        self.assertEqual(job1.estimated_duration, None)
        job2 = JobDefinition({'estimated_duration': 'foo'})
        self.assertEqual(job2.estimated_duration, None)
        job3 = JobDefinition({'estimated_duration': '123.5'})
        self.assertEqual(job3.estimated_duration, 123.5)

    def test_summary(self):
        job1 = JobDefinition({})
        self.assertEqual(job1.summary, None)
        job2 = JobDefinition({'name': 'name'})
        self.assertEqual(job2.summary, 'name')
        job3 = JobDefinition({'summary': 'summary'})
        self.assertEqual(job3.summary, 'summary')
        job4 = JobDefinition({'summary': 'summary', 'name': 'name'})
        self.assertEqual(job4.summary, 'summary')

    def test_get_translated_data__typical(self):
        """
        Verify the runtime behavior of get_translated_data()
        """
        job = JobDefinition(self._full_record.data)
        with mock.patch.object(job, "_provider") as mock_provider:
            retval = job.get_translated_data('foo')
        mock_provider.get_translated_data.assert_called_with("foo")
        self.assertEqual(retval, mock_provider.get_translated_data())

    def test_get_translated_data__no_provider(self):
        """
        Verify the runtime behavior of get_translated_data()
        """
        job = JobDefinition(self._full_record.data)
        job._provider = None
        self.assertEqual(job.get_translated_data('foo'), 'foo')

    def test_get_translated_data__empty_msgid(self):
        """
        Verify the runtime behavior of get_translated_data()
        """
        job = JobDefinition(self._full_record.data)
        with mock.patch.object(job, "_provider"):
            self.assertEqual(job.get_translated_data(''), '')

    def test_get_translated_data__None_msgid(self):
        """
        Verify the runtime behavior of get_translated_data()
        """
        job = JobDefinition(self._full_record.data)
        with mock.patch.object(job, "_provider"):
            self.assertEqual(job.get_translated_data(None), None)

    @mock.patch('plainbox.impl.unit.job.normalize_rfc822_value')
    def test_get_normalized_translated_data__typical(self, mock_norm):
        """
        verify the runtime behavior of get_normalized_translated_data()
        """
        job = JobDefinition(self._full_record.data)
        with mock.patch.object(job, "get_translated_data") as mock_tr:
            retval = job.get_normalized_translated_data('foo')
        # get_translated_data('foo') was called
        mock_tr.assert_called_with("foo")
        # normalize_rfc822_value(x) was called
        mock_norm.assert_called_with(mock_tr())
        # return value was returned
        self.assertEqual(retval, mock_norm())

    @mock.patch('plainbox.impl.unit.job.normalize_rfc822_value')
    def test_get_normalized_translated_data__no_translation(self, mock_norm):
        """
        verify the runtime behavior of get_normalized_translated_data()
        """
        job = JobDefinition(self._full_record.data)
        with mock.patch.object(job, "get_translated_data") as mock_tr:
            mock_tr.return_value = None
            retval = job.get_normalized_translated_data('foo')
        # get_translated_data('foo') was called
        mock_tr.assert_called_with("foo")
        # normalize_rfc822_value(x) was NOT called
        self.assertEqual(mock_norm.call_count, 0)
        # return value was returned
        self.assertEqual(retval, 'foo')

    def test_tr_summary(self):
        """
        Verify that Provider1.tr_summary() works as expected
        """
        job = JobDefinition(self._full_record.data)
        with mock.patch.object(job, "get_normalized_translated_data") as mgntd:
            retval = job.tr_summary()
        # Ensure that get_translated_data() was called
        mgntd.assert_called_once_with(job.summary)
        # Ensure tr_summary() returned its return value
        self.assertEqual(retval, mgntd())

    def test_tr_summary__falls_back_to_id(self):
        """
        Verify that Provider1.tr_summary() falls back to job.id, if summary is
        not defined
        """
        job = JobDefinition({'id': 'id'})
        self.assertEqual(job.tr_summary(), 'id')

    def test_tr_description(self):
        """
        Verify that Provider1.tr_description() works as expected
        """
        job = JobDefinition(self._full_record.data)
        with mock.patch.object(job, "get_normalized_translated_data") as mgntd:
            retval = job.tr_description()
        # Ensure that get_translated_data() was called
        mgntd.assert_called_once_with(job.description)
        # Ensure tr_description() returned its return value
        self.assertEqual(retval, mgntd())


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
            'id': 'id',
            'plugin': self.parameters.plugin})
        expected = self.parameters_keymap[self.parameters.plugin]
        observed = job.startup_user_interaction_required
        self.assertEqual(expected, observed)


class JobParsingTests(TestCaseWithParameters):

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
            'id': 'id',
            'plugin': 'plugin',
            'environ': self.parameters_keymap[
                self.parameters.glue].join(['foo', 'bar', 'froz'])})
        expected = set({'foo', 'bar', 'froz'})
        observed = job.get_environ_settings()
        self.assertEqual(expected, observed)

    def test_dependency_parsing_with_various_separators(self):
        job = JobDefinition({
            'id': 'id',
            'plugin': 'plugin',
            'depends': self.parameters_keymap[
                self.parameters.glue].join(['foo', 'bar', 'froz'])})
        expected = set({'foo', 'bar', 'froz'})
        observed = job.get_direct_dependencies()
        self.assertEqual(expected, observed)
