# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
plainbox.impl.unit.test_job
===========================

Test definitions for plainbox.impl.unit.job module
"""

from unittest import TestCase
import warnings

from plainbox.impl.providers.v1 import Provider1
from plainbox.impl.secure.origin import FileTextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.rfc822 import RFC822Record
from plainbox.impl.unit.job import JobDefinition
from plainbox.impl.unit.job import propertywithsymbols
from plainbox.impl.unit.test_unit_with_id import UnitWithIdFieldValidationTests
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.validators import UnitValidationContext
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity
from plainbox.impl.validation import ValidationError
from plainbox.testing_utils.testcases import TestCaseWithParameters
from plainbox.vendor import mock


class DecoratorTests(TestCase):

    def setUp(self):
        self.symbols = mock.Mock(name='symbols')

        class C:

            @propertywithsymbols(symbols=self.symbols)
            def prop(self):
                """a docstring"""
                return 'prop'
        self.C = C

    def test_propertywithsymbols__fget_works(self):
        self.assertEqual(self.C().prop, 'prop')

    def test_propertywithsmybols__symbols_works(self):
        self.assertIs(self.C.prop.symbols, self.symbols)

    def test_propertywithsymbols__inherits_doc_from_fget(self):
        self.assertEqual(self.C.prop.__doc__, 'a docstring')

    def test_propertywithsymbols__honors_doc_argument(self):

        class C:

            @propertywithsymbols(doc='different', symbols=self.symbols)
            def prop(self):
                """a docstring"""
                return 'prop'

        self.assertEqual(C.prop.__doc__, 'different')


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
            'category_id': 'category_id-value',
        }, raw_data={
            'plugin': 'plugin-raw',
            'command': 'command-raw',
            'environ': 'environ-raw',
            'user': 'user-raw',
            'shell': 'shell-raw',
            'flags': 'flags-raw',
            'category_id': 'category_id-raw',
        })
        self.assertEqual(job.plugin, "plugin-value")
        self.assertEqual(job.command, "command-value")
        self.assertEqual(job.environ, "environ-value")
        self.assertEqual(job.user, "user-value")
        self.assertEqual(job.shell, "shell-value")
        self.assertEqual(job.flags, "flags-value")
        self.assertEqual(job.category_id, "category_id-value")

    def test_qml_file_property_none_when_missing_provider(self):
        """
        Ensure that qml_file property is set to None when provider is not set.
        """
        job = JobDefinition({
            'qml_file': 'qml_file-value'
        }, raw_data={
            'qml_file': 'qml_file-raw'
        })
        self.assertEqual(job.qml_file, None)

    def test_qml_file_property(self):
        """
        Ensure that qml_file property is properly constructed
        """
        mock_provider = mock.Mock()
        type(mock_provider).data_dir = mock.PropertyMock(return_value='data')
        job = JobDefinition({
            'qml_file': 'qml_file-value'
        }, raw_data={
            'qml_file': 'qml_file-raw'
        }, provider=mock_provider)
        with mock.patch('os.path.join', return_value='path') as mock_join:
            self.assertEqual(job.qml_file, 'path')
            mock_join.assert_called_with('data', 'qml_file-value')

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
        self.assertEqual(job.category_id,
                         '2013.com.canonical.plainbox::uncategorised')
        self.assertEqual(job.qml_file, None)

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


class JobDefinitionFieldValidationTests(UnitWithIdFieldValidationTests):

    unit_cls = JobDefinition

    def test_unit__present(self):
        # NOTE: this is overriding an identical method from the base class to
        # disable this test.
        pass

    def test_name__untranslatable(self):
        issue_list = self.unit_cls({
            '_name': 'name'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.name,
                              Problem.unexpected_i18n, Severity.warning)

    def test_name__template_variant(self):
        issue_list = self.unit_cls({
            'name': 'name'
        }, parameters={}, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.name,
                              Problem.constant, Severity.error)

    def test_name__deprecated(self):
        issue_list = self.unit_cls({
            'name': 'name'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.name,
                              Problem.deprecated, Severity.advice)

    def test_summary__translatable(self):
        issue_list = self.unit_cls({
            'summary': 'summary'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.summary,
                              Problem.expected_i18n, Severity.warning)

    def test_summary__template_variant(self):
        issue_list = self.unit_cls({
            'summary': 'summary'
        }, provider=self.provider, parameters={}).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.summary,
                              Problem.constant, Severity.error)

    def test_summary__present(self):
        issue_list = self.unit_cls({
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.summary,
                              Problem.missing, Severity.advice)

    def test_summary__one_line(self):
        issue_list = self.unit_cls({
            'summary': 'line1\nline2'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.summary,
                              Problem.wrong, Severity.warning)

    def test_summary__short_line(self):
        issue_list = self.unit_cls({
            'summary': 'x' * 81
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.summary,
                              Problem.wrong, Severity.warning)

    def test_plugin__untranslatable(self):
        issue_list = self.unit_cls({
            '_plugin': 'plugin'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.plugin,
                              Problem.unexpected_i18n, Severity.warning)

    def test_plugin__template_invarinat(self):
        issue_list = self.unit_cls({
            'plugin': '{attr}'
        }, parameters={'attr': 'plugin'}, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.plugin,
                              Problem.variable, Severity.error)

    def test_plugin__correct(self):
        issue_list = self.unit_cls({
            'plugin': 'foo'
        }, provider=self.provider).check()
        message = ("field 'plugin', valid values are: attachment, local,"
                   " manual, qml, resource, shell, user-interact,"
                   " user-interact-verify, user-verify")
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.plugin,
                              Problem.wrong, Severity.error, message)

    def test_plugin__not_local(self):
        issue_list = self.unit_cls({
            'plugin': 'local'
        }, provider=self.provider).check()
        message = ("field 'plugin', please migrate to job templates, "
                   "see plainbox-template-unit(7) for details")
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.plugin,
                              Problem.deprecated, Severity.advice, message)

    def test_plugin__not_user_verify(self):
        issue_list = self.unit_cls({
            'plugin': 'user-verify'
        }, provider=self.provider).check()
        message = "field 'plugin', please migrate to user-interact-verify"
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.plugin,
                              Problem.deprecated, Severity.advice, message)

    def test_command__untranslatable(self):
        issue_list = self.unit_cls({
            '_command': 'command'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.command,
                              Problem.unexpected_i18n, Severity.warning)

    def test_command__present__on_non_manual(self):
        for plugin in self.unit_cls.plugin.symbols.get_all_symbols():
            if plugin in ('manual', 'qml'):
                continue
            # TODO: switch to subTest() once we depend on python3.4
            issue_list = self.unit_cls({
                'plugin': plugin,
            }, provider=self.provider).check()
            self.assertIssueFound(
                issue_list, self.unit_cls.Meta.fields.command,
                Problem.missing, Severity.error)

    def test_command__useless__on_manual(self):
        issue_list = self.unit_cls({
            'plugin': 'manual',
            'command': 'command'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.command,
            Problem.useless, Severity.warning)

    def test_command__useless__on_qml(self):
        issue_list = self.unit_cls({
            'plugin': 'qml',
            'command': 'command'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.command,
            Problem.useless, Severity.warning)

    def test_command__not_using_CHECKBOX_SHARE(self):
        issue_list = self.unit_cls({
            'command': '$CHECKBOX_SHARE'
        }, provider=self.provider).check()
        message = ("field 'command', please use PLAINBOX_PROVIDER_DATA"
                   " instead of CHECKBOX_SHARE")
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.command,
            Problem.deprecated, Severity.advice, message)

    def test_command__not_using_CHECKBOX_DATA(self):
        issue_list = self.unit_cls({
            'command': '$CHECKBOX_DATA'
        }, provider=self.provider).check()
        message = ("field 'command', please use PLAINBOX_SESSION_SHARE"
                   " instead of CHECKBOX_DATA")
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.command,
            Problem.deprecated, Severity.advice, message)

    def test_command__has_valid_syntax(self):
        issue_list = self.unit_cls({
            'command': """# Echo a few numbers
            for i in 1 2 "3; do
                echo $i
            done"""
        }, provider=self.provider).check()
        message = ("field 'command', No closing quotation, near '2'")
        issue = self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.command,
            Problem.syntax_error, Severity.error, message)
        # Make sure the offset was good too. Since offset is dependant on the
        # place where we instantiate the unit in the self.unit_cls({}) line
        # above let's just ensure that the reported error is at a +3 offset
        # from that line. Note, the offset is a bit confusing since the error
        # is on line reading 'for i in 1 2 "3; do' but shlex will actually only
        # report it at the end of the input which is the line with 'done'
        self.assertEqual(
            issue.origin.line_start,
            issue.unit.origin.line_start + 3)

    def test_description__translatable(self):
        issue_list = self.unit_cls({
            'description': 'description'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.description,
            Problem.expected_i18n, Severity.warning)

    def test_description__template_variant(self):
        issue_list = self.unit_cls({
            'description': 'description'
        }, parameters={}, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.description,
            Problem.constant, Severity.error)

    def test_description__present__on_non_manual(self):
        for plugin in self.unit_cls.plugin.symbols.get_all_symbols():
            if plugin == 'manual':
                continue
            message = ("field 'description', all jobs should have a"
                       " description field, or a set of purpose, steps and"
                       " verification fields")
            # TODO: switch to subTest() once we depend on python3.4
            issue_list = self.unit_cls({
                'plugin': plugin
            }, provider=self.provider).check()
            self.assertIssueFound(
                issue_list, self.unit_cls.Meta.fields.description,
                Problem.missing, Severity.advice, message)

    def test_description__present__on_manual(self):
        message = ("field 'description', manual jobs must have a description"
                   " field, or a set of purpose, steps, and verification"
                   " fields")
        issue_list = self.unit_cls({
            'plugin': 'manual'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.description,
            Problem.missing, Severity.error, message)

    def test_user__untranslatable(self):
        issue_list = self.unit_cls({
            '_user': 'user'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.user,
                              Problem.unexpected_i18n, Severity.warning)

    def test_user__template_invarinat(self):
        issue_list = self.unit_cls({
            'user': '{attr}'
        }, parameters={'attr': 'user'}, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.user,
                              Problem.variable, Severity.error)

    def test_user__defined_but_not_root(self):
        message = "field 'user', user can only be 'root'"
        issue_list = self.unit_cls({
            'user': 'user'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.user,
                              Problem.wrong, Severity.error, message)

    def test_user__useless_without_command(self):
        message = "field 'user', user without a command makes no sense"
        issue_list = self.unit_cls({
            'user': 'user'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.user,
                              Problem.useless, Severity.warning, message)

    def test_environ__untranslatable(self):
        issue_list = self.unit_cls({'_environ': 'environ'}).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.environ,
                              Problem.unexpected_i18n, Severity.warning)

    def test_environ__template_invarinat(self):
        issue_list = self.unit_cls({
            'environ': '{attr}'
        }, parameters={'attr': 'environ'}, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.environ,
                              Problem.variable, Severity.error)

    def test_environ__useless_without_command(self):
        message = "field 'environ', environ without a command makes no sense"
        issue_list = self.unit_cls({
            'environ': 'environ'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.environ,
                              Problem.useless, Severity.warning, message)

    def test_estimated_duration__untranslatable(self):
        issue_list = self.unit_cls({
            '_estimated_duration': 'estimated_duration'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.estimated_duration,
            Problem.unexpected_i18n, Severity.warning)

    def test_estimated_duration__template_invarinat(self):
        issue_list = self.unit_cls({
            'estimated_duration': '{attr}'
        }, parameters={'attr': 'value'}, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.estimated_duration,
            Problem.variable, Severity.error)

    def test_estimated_duration__present(self):
        issue_list = self.unit_cls({
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.estimated_duration,
            Problem.missing, Severity.advice)

    def test_estimated_duration__positive(self):
        issue_list = self.unit_cls({
            'estimated_duration': '0'
        }, provider=self.provider).check()
        message = "field 'estimated_duration', value must be a positive number"
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.estimated_duration,
            Problem.wrong, Severity.error, message)

    def test_depends__untranslatable(self):
        issue_list = self.unit_cls({
            '_depends': 'depends'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.depends,
            Problem.unexpected_i18n, Severity.warning)

    def test_depends__refers_to_other_units(self):
        unit = self.unit_cls({
            'depends': 'some-unit'
        }, provider=self.provider)
        message = "field 'depends', unit 'ns::some-unit' is not available"
        self.provider.unit_list = [unit]
        context = UnitValidationContext([self.provider])
        issue_list = unit.check(context=context)
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.depends,
            Problem.bad_reference, Severity.error, message)

    def test_depends__refers_to_other_jobs(self):
        other_unit = UnitWithId({
            'id': 'some-unit'
        }, provider=self.provider)
        unit = self.unit_cls({
            'depends': 'some-unit'
        }, provider=self.provider)
        message = "field 'depends', the referenced unit is not a job"
        self.provider.unit_list = [unit, other_unit]
        context = UnitValidationContext([self.provider])
        issue_list = unit.check(context=context)
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.depends,
            Problem.bad_reference, Severity.error, message)

    def test_requires__untranslatable(self):
        issue_list = self.unit_cls({
            '_requires': 'requires'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.requires,
            Problem.unexpected_i18n, Severity.warning)

    def test_requires__refers_to_other_units(self):
        unit = self.unit_cls({
            'requires': 'some_unit.attr == "value"'
        }, provider=self.provider)
        message = "field 'requires', unit 'ns::some_unit' is not available"
        self.provider.unit_list = [unit]
        context = UnitValidationContext([self.provider])
        issue_list = unit.check(context=context)
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.requires,
            Problem.bad_reference, Severity.error, message)

    def test_requires__refers_to_other_jobs(self):
        other_unit = UnitWithId({
            'id': 'some_unit'
        }, provider=self.provider)
        unit = self.unit_cls({
            'requires': 'some_unit.attr == "value"'
        }, provider=self.provider)
        message = "field 'requires', the referenced unit is not a job"
        self.provider.unit_list = [unit, other_unit]
        context = UnitValidationContext([self.provider])
        issue_list = unit.check(context=context)
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.requires,
            Problem.bad_reference, Severity.error, message)

    def test_requires__refers_to_other_resource_jobs(self):
        other_unit = JobDefinition({
            'id': 'some_unit', 'plugin': 'shell'
        }, provider=self.provider)
        unit = self.unit_cls({
            'requires': 'some_unit.attr == "value"'
        }, provider=self.provider)
        message = "field 'requires', the referenced job is not a resource job"
        self.provider.unit_list = [unit, other_unit]
        context = UnitValidationContext([self.provider])
        issue_list = unit.check(context=context)
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.requires,
            Problem.bad_reference, Severity.error, message)

    def test_shell__untranslatable(self):
        issue_list = self.unit_cls({
            '_shell': 'shell'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.shell,
                              Problem.unexpected_i18n, Severity.warning)

    def test_shell__template_invarinat(self):
        issue_list = self.unit_cls({
            'shell': '{attr}'
        }, parameters={'attr': 'shell'}, provider=self.provider).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.shell,
                              Problem.variable, Severity.error)

    def test_shell__defined_but_invalid(self):
        message = "field 'shell', only /bin/sh and /bin/bash are allowed"
        issue_list = self.unit_cls({'shell': 'shell'},).check()
        self.assertIssueFound(issue_list, self.unit_cls.Meta.fields.shell,
                              Problem.wrong, Severity.error, message)

    def test_category_id__untranslatable(self):
        issue_list = self.unit_cls({
            '_category_id': 'category_id'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.category_id,
            Problem.unexpected_i18n, Severity.warning)

    def test_category_id__template_invarinat(self):
        issue_list = self.unit_cls({
            'category_id': '{attr}'
        }, parameters={'attr': 'category_id'}, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.category_id,
            Problem.variable, Severity.error)

    def test_category_id__refers_to_other_units(self):
        unit = self.unit_cls({
            'category_id': 'some-unit'
        }, provider=self.provider)
        message = "field 'category_id', unit 'ns::some-unit' is not available"
        self.provider.unit_list = [unit]
        context = UnitValidationContext([self.provider])
        issue_list = unit.check(context=context)
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.category_id,
            Problem.bad_reference, Severity.error, message)

    def test_category_id__refers_to_other_jobs(self):
        other_unit = UnitWithId({
            'id': 'some-unit'
        }, provider=self.provider)
        unit = self.unit_cls({
            'category_id': 'some-unit'
        }, provider=self.provider)
        message = "field 'category_id', the referenced unit is not a category"
        self.provider.unit_list = [unit, other_unit]
        context = UnitValidationContext([self.provider])
        issue_list = unit.check(context=context)
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.category_id,
            Problem.bad_reference, Severity.error, message)

    def test_flags__preserve_locale_is_set(self):
        message = ("field 'flags', please ensure that the command supports"
                   " non-C locale then set the preserve-locale flag")
        issue_list = self.unit_cls({
            'command': 'command'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.flags,
            Problem.expected_i18n, Severity.advice, message)


class JobDefinitionValidatorTests(TestCase):

    def setUp(self):
        warnings.filterwarnings(
            'ignore', 'validate is deprecated since version 0.11')

    def tearDown(self):
        warnings.resetwarnings()

    def test_validate_checks_for_deprecated_name(self):
        """
        verify that validate() checks if jobs have a value for the 'id'
        field.
        """
        job = JobDefinition({
            'name': 'name'
        })
        with self.assertRaises(ValidationError) as boom:
            job.validate(deprecated=True)
        self.assertEqual(boom.exception.field, JobDefinition.fields.name)
        self.assertEqual(boom.exception.problem, Problem.deprecated)

    def test_validate_checks_for_missing_id(self):
        """
        verify that validate() checks if jobs have a value for the 'id'
        field.
        """
        job = JobDefinition({})
        with self.assertRaises(ValidationError) as boom:
            job.validate()
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
            job.validate()
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
            job.validate()
        self.assertEqual(boom.exception.field, JobDefinition.fields.plugin)
        self.assertEqual(boom.exception.problem, Problem.wrong)

    def test_validate_checks_for_useless_user(self):
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
            job.validate(strict=True)
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
            job.validate(strict=True)
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
            job.validate()
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
            job.validate(strict=True)
        self.assertEqual(boom.exception.field, JobDefinition.fields.command)
        self.assertEqual(boom.exception.problem, Problem.useless)


class JobDefinitionValidatorTests2(TestCaseWithParameters):
    """
    Continuation of unit tests for JobDefinition.validate().

    Moved to a separate class because of limitations of TestCaseWithParameters
    which operates on the whole class.
    """

    parameter_names = ('plugin',)
    parameter_values = (
        ('shell',), ('local',), ('resource',), ('attachment',),
        ('user-verify',), ('user-interact',),)

    def setUp(self):
        warnings.filterwarnings(
            'ignore', 'validate is deprecated since version 0.11')

    def tearDown(self):
        warnings.resetwarnings()

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
            job.validate()
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
            job.validate()
        self.assertEqual(boom.exception.field, JobDefinition.fields.user)
        self.assertEqual(boom.exception.problem, Problem.wrong)


class TestJobDefinition(TestCase):

    def setUp(self):
        self._full_record = RFC822Record({
            'plugin': 'plugin',
            'id': 'id',
            'summary': 'summary-value',
            'requires': 'requires',
            'command': 'command',
            'description': 'description-value'
        }, Origin(FileTextSource('file.txt'), 1, 5))
        self._full_gettext_record = RFC822Record({
            '_plugin': 'plugin',
            '_id': 'id',
            '_summary': 'summary-value',
            '_requires': 'requires',
            '_command': 'command',
            '_description': 'description-value'
        }, Origin(FileTextSource('file.txt.in'), 1, 5))
        self._min_record = RFC822Record({
            'plugin': 'plugin',
            'id': 'id',
        }, Origin(FileTextSource('file.txt'), 1, 2))
        self._split_description_record = RFC822Record({
            'id': 'id',
            'purpose': 'purpose-value',
            'steps': 'steps-value',
            'verification': 'verification-value'
        }, Origin(FileTextSource('file.txt'), 1, 1))

    def test_instantiate_template(self):
        data = mock.Mock(name='data')
        raw_data = mock.Mock(name='raw_data')
        origin = mock.Mock(name='origin')
        provider = mock.Mock(name='provider')
        parameters = mock.Mock(name='parameters')
        field_offset_map = mock.Mock(name='field_offset_map')
        unit = JobDefinition.instantiate_template(
            data, raw_data, origin, provider, parameters, field_offset_map)
        self.assertIs(unit._data, data)
        self.assertIs(unit._raw_data, raw_data)
        self.assertIs(unit._origin, origin)
        self.assertIs(unit._provider, provider)
        self.assertIs(unit._parameters, parameters)
        self.assertIs(unit._field_offset_map, field_offset_map)

    def test_smoke_full_record(self):
        job = JobDefinition(self._full_record.data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.id, "id")
        self.assertEqual(job.requires, "requires")
        self.assertEqual(job.command, "command")
        self.assertEqual(job.description, "description-value")

    def test_smoke_full_gettext_record(self):
        job = JobDefinition(self._full_gettext_record.data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.id, "id")
        self.assertEqual(job.requires, "requires")
        self.assertEqual(job.command, "command")
        self.assertEqual(job.description, "description-value")

    def test_smoke_min_record(self):
        job = JobDefinition(self._min_record.data)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.id, "id")
        self.assertEqual(job.requires, None)
        self.assertEqual(job.command, None)
        self.assertEqual(job.description, None)

    def test_smoke_description_split(self):
        job = JobDefinition(self._split_description_record.data)
        self.assertEqual(job.id, "id")
        self.assertEqual(job.purpose, "purpose-value")
        self.assertEqual(job.steps, "steps-value")
        self.assertEqual(job.verification, "verification-value")

    def test_description_combining(self):
        job = JobDefinition(self._split_description_record.data)
        expected = ("PURPOSE:\npurpose-value\nSTEPS:\nsteps-value\n"
                    "VERIFICATION:\nverification-value")
        self.assertEqual(job.description, expected)

    def test_from_rfc822_record_full_record(self):
        job = JobDefinition.from_rfc822_record(self._full_record)
        self.assertEqual(job.plugin, "plugin")
        self.assertEqual(job.id, "id")
        self.assertEqual(job.requires, "requires")
        self.assertEqual(job.command, "command")
        self.assertEqual(job.description, "description-value")

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

    def test_dependency_parsing_quoted_word(self):
        job = JobDefinition({
            'id': 'id',
            'plugin': 'plugin',
            'depends': '"quoted word"'})
        expected = set(['quoted word'])
        observed = job.get_direct_dependencies()
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

    def test_tr_summary(self):
        """
        Verify that Provider1.tr_summary() works as expected
        """
        job = JobDefinition(self._full_record.data)
        with mock.patch.object(job, "get_translated_record_value") as mgtrv:
            retval = job.tr_summary()
        # Ensure that get_translated_record_value() was called
        mgtrv.assert_called_once_with('summary', job.partial_id)
        # Ensure tr_summary() returned its return value
        self.assertEqual(retval, mgtrv())

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
        with mock.patch.object(job, "get_translated_record_value") as mgtrv:
            retval = job.tr_description()
        # Ensure that get_translated_record_value() was called
        mgtrv.assert_called_once_with('description')
        # Ensure tr_description() returned its return value
        self.assertEqual(retval, mgtrv())

    def test_tr_description_combining(self):
        """
        Verify that translated description is properly generated
        """
        job = JobDefinition(self._split_description_record.data)

        def side_effect(arg):
            return {
                'description': None,
                'PURPOSE': 'TR_PURPOSE',
                'STEPS': 'TR_STEPS',
                'VERIFICATION': 'TR_VERIFICATION',
                'purpose': 'tr_purpose_value',
                'steps': 'tr_steps_value',
                'verification': 'tr_verification_value'
            }[arg]
        with mock.patch.object(job, "get_translated_record_value") as mgtrv:
            mgtrv.side_effect = side_effect
            with mock.patch('plainbox.impl.unit.job._') as mock_gettext:
                mock_gettext.side_effect = side_effect
                retval = job.tr_description()
        mgtrv.assert_any_call('description')
        mgtrv.assert_any_call('purpose')
        mgtrv.assert_any_call('steps')
        mgtrv.assert_any_call('verification')
        self.assertEqual(mgtrv.call_count, 4)
        mock_gettext.assert_any_call('PURPOSE')
        mock_gettext.assert_any_call('STEPS')
        mock_gettext.assert_any_call('VERIFICATION')
        self.assertEqual(mock_gettext.call_count, 3)
        expected = ("TR_PURPOSE:\ntr_purpose_value\nTR_STEPS:\n"
                    "tr_steps_value\nTR_VERIFICATION:\ntr_verification_value")
        self.assertEqual(retval, expected)

    def test_tr_purpose(self):
        """
        Verify that Provider1.tr_purpose() works as expected
        """
        job = JobDefinition(self._split_description_record.data)
        with mock.patch.object(job, "get_translated_record_value") as mgtrv:
            retval = job.tr_purpose()
        # Ensure that get_translated_record_value() was called
        mgtrv.assert_called_once_with('purpose')
        # Ensure tr_purpose() returned its return value
        self.assertEqual(retval, mgtrv())

    def test_tr_steps(self):
        """
        Verify that Provider1.tr_steps() works as expected
        """
        job = JobDefinition(self._split_description_record.data)
        with mock.patch.object(job, "get_translated_record_value") as mgtrv:
            retval = job.tr_steps()
        # Ensure that get_translated_record_value() was called
        mgtrv.assert_called_once_with('steps')
        # Ensure tr_steps() returned its return value
        self.assertEqual(retval, mgtrv())

    def test_tr_verification(self):
        """
        Verify that Provider1.tr_verification() works as expected
        """
        job = JobDefinition(self._split_description_record.data)
        with mock.patch.object(job, "get_translated_record_value") as mgtrv:
            retval = job.tr_verification()
        # Ensure that get_translated_record_value() was called
        mgtrv.assert_called_once_with('verification')
        # Ensure tr_verification() returned its return value
        self.assertEqual(retval, mgtrv())

    def test_imports(self):
        job1 = JobDefinition({})
        self.assertEqual(job1.imports, None)
        job2 = JobDefinition({'imports': 'imports'})
        self.assertEqual(job2.imports, 'imports')

    def test_get_imported_jobs(self):
        job1 = JobDefinition({})
        self.assertEqual(list(job1.get_imported_jobs()), [])
        job2 = JobDefinition({
            'imports': 'from 2013.com.canonical.certification import package'
        })
        self.assertEqual(list(job2.get_imported_jobs()), [
            ('2013.com.canonical.certification::package', 'package')
        ])
        job3 = JobDefinition({
            'imports': ('from 2013.com.canonical.certification'
                        ' import package as pkg')
        })
        self.assertEqual(list(job3.get_imported_jobs()), [
            ('2013.com.canonical.certification::package', 'pkg')
        ])

    def test_get_resource_program_using_imports(self):
        job = JobDefinition({
            'imports': ('from 2013.com.canonical.certification'
                        ' import package as pkg'),
            'requires': 'pkg.name == "checkbox"',
        })
        prog = job.get_resource_program()
        self.assertEqual(
            prog.required_resources,
            {'2013.com.canonical.certification::package'})


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


class RegressionTests(TestCase):

    """ Regression tests. """

    def test_1444242(self):
        """ Regression test for http://pad.lv/1444242/. """
        provider = mock.Mock(spec_set=Provider1, name='provider')
        provider.namespace = '2013.com.canonical.certification'
        job = JobDefinition({
            'id': 'audio/playback_thunderbolt',
            'imports': 'from 2013.com.canonical.plainbox import manifest',
            'requires': (
                "device.category == 'AUDIO'\n"
                "manifest.has_thunderbolt == 'True'\n"),
        }, provider=provider)
        prog = job.get_resource_program()
        self.assertEqual(prog.expression_list[-1].resource_id,
                         '2013.com.canonical.plainbox::manifest')
