# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
plainbox.impl.test_job
======================

Test definitions for plainbox.impl.job module
"""

from unittest import TestCase, expectedFailure

from plainbox.impl.job import CheckBoxJobValidator
from plainbox.impl.job import JobDefinition
from plainbox.impl.job import JobOutputTextSource
from plainbox.impl.job import JobTreeNode
from plainbox.impl.job import Problem
from plainbox.impl.job import ValidationError
from plainbox.impl.secure.rfc822 import FileTextSource
from plainbox.impl.secure.rfc822 import Origin
from plainbox.impl.secure.rfc822 import RFC822Record
from plainbox.impl.testing_utils import make_job
from plainbox.testing_utils.testcases import TestCaseWithParameters
from plainbox.vendor import mock


class CheckBoxJobValidatorTests(TestCase):

    def test_validate_checks_for_missing_id(self):
        """
        verify that validate() checks if jobs have a value for the 'id'
        field.
        """
        job = JobDefinition({})
        with self.assertRaises(ValidationError) as boom:
            CheckBoxJobValidator.validate(job)
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
            CheckBoxJobValidator.validate(job)
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
            CheckBoxJobValidator.validate(job)
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
            CheckBoxJobValidator.validate(job)
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
            CheckBoxJobValidator.validate(job)
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
            'id': 'id',
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
            'id': 'id',
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
            'id': 'id',
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

    def test_from_rfc822_record_missing_id(self):
        record = RFC822Record({'plugin': 'plugin'})
        with self.assertRaises(ValueError):
            JobDefinition.from_rfc822_record(record)

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

    @mock.patch('plainbox.impl.job.normalize_rfc822_value')
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

    @mock.patch('plainbox.impl.job.normalize_rfc822_value')
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
        Verify that Provider1.tr_description() works as expected
        """
        job = JobDefinition(self._full_record.data)
        with mock.patch.object(job, "get_normalized_translated_data") as mgntd:
            retval = job.tr_summary()
        # Ensure that get_translated_data() was called
        mgntd.assert_called_once_with(job.summary)
        # Ensure tr_summary() returned its return value
        self.assertEqual(retval, mgntd())

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


class TestJobTreeNode_legacy(TestCase):

    def setUp(self):
        A = make_job('A')
        B = make_job('B', plugin='local', description='foo')
        C = make_job('C')
        D = B.create_child_job_from_record(
            RFC822Record(
                data={'id': 'D', 'plugin': 'shell'},
                origin=Origin(source=JobOutputTextSource(B),
                              line_start=1,
                              line_end=1)))
        E = B.create_child_job_from_record(
            RFC822Record(
                data={'id': 'E', 'plugin': 'local', 'description': 'bar'},
                origin=Origin(source=JobOutputTextSource(B),
                              line_start=1,
                              line_end=1)))
        F = E.create_child_job_from_record(
            RFC822Record(
                data={'id': 'F', 'plugin': 'shell'},
                origin=Origin(source=JobOutputTextSource(E),
                              line_start=1,
                              line_end=1)))
        G = make_job('G', plugin='local', description='baz')
        R = make_job('R', plugin='resource')
        Z = make_job('Z', plugin='local', description='zaz')

        self.tree = JobTreeNode.create_tree([R, B, C, D, E, F, G, A, Z],
                                            legacy_mode=True)

    def test_create_tree(self):
        self.assertIsInstance(self.tree, JobTreeNode)
        self.assertEqual(len(self.tree.categories), 3)
        [self.assertIsInstance(c, JobTreeNode) for c in self.tree.categories]
        self.assertEqual(len(self.tree.jobs), 3)
        [self.assertIsInstance(j, JobDefinition) for j in self.tree.jobs]
        self.assertIsNone(self.tree.parent)
        self.assertEqual(self.tree.depth, 0)
        node = self.tree.categories[1]
        self.assertEqual(node.name, 'foo')
        self.assertEqual(len(node.categories), 1)
        [self.assertIsInstance(c, JobTreeNode) for c in node.categories]
        self.assertEqual(len(node.jobs), 1)
        [self.assertIsInstance(j, JobDefinition) for j in node.jobs]


class TestNewJoB:
    """
    Simple Job definition to demonstrate the categories property and how it
    could be used to create a JobTreeNode
    """
    def __init__(self, name, categories={}):
        self.name = name
        self.categories = categories


class TestJobTreeNodeExperimental(TestCase):

    def brokenSetUp(self):
        A = TestNewJoB('A', {'Audio'})
        B = TestNewJoB('B', {'Audio', 'USB'})
        C = TestNewJoB('C', {'USB'})
        D = TestNewJoB('D', {'Wireless'})
        E = TestNewJoB('E', {})
        F = TestNewJoB('F', {'Wireless'})

        # Populate the tree with a existing hierarchy as plainbox does not
        # provide yet a way to build such categorization
        root = JobTreeNode()
        MM = JobTreeNode('Multimedia')
        Audio = JobTreeNode('Audio')
        root.add_category(MM)
        MM.add_category(Audio)
        self.tree = JobTreeNode.create_tree([A, B, C, D, E, F], root, link='')

    # This test fails is not using job definitions where it assumes jobs are
    # being handled and now it crashes inside JobTreeNode.add_job() which
    # receives a non-job object.
    @expectedFailure
    def test_create_tree(self):
        self.brokenSetUp()
        self.assertIsInstance(self.tree, JobTreeNode)
        self.assertEqual(len(self.tree.categories), 3)
        [self.assertIsInstance(c, JobTreeNode) for c in self.tree.categories]
        self.assertEqual(len(self.tree.jobs), 1)
        [self.assertIsInstance(j, TestNewJoB) for j in self.tree.jobs]
        self.assertIsNone(self.tree.parent)
        self.assertEqual(self.tree.depth, 0)
        node = self.tree.categories[0]
        self.assertEqual(node.name, 'Multimedia')
        self.assertEqual(len(node.categories), 1)
        [self.assertIsInstance(c, JobTreeNode) for c in node.categories]
        self.assertEqual(len(node.jobs), 0)
        node = node.categories[0]
        self.assertEqual(node.name, 'Audio')
        self.assertEqual(len(node.categories), 0)
        self.assertEqual(len(node.jobs), 2)
        self.assertIn('B', [job.name for job in node.jobs])
        [self.assertIsInstance(j, TestNewJoB) for j in node.jobs]
        node = self.tree.categories[1]
        self.assertEqual(node.name, 'USB')
        self.assertIn('B', [job.name for job in node.jobs])
        node = self.tree.categories[2]
        self.assertEqual(node.name, 'Wireless')
        self.assertEqual(len(node.categories), 0)
        self.assertEqual(len(node.jobs), 2)
        [self.assertIsInstance(j, TestNewJoB) for j in node.jobs]
