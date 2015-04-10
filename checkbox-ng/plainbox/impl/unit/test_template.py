# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
plainbox.impl.unit.test_template
================================

Test definitions for plainbox.impl.unit.template module
"""

from unittest import TestCase
import warnings

from plainbox.abc import IProvider1
from plainbox.impl.resource import Resource
from plainbox.impl.resource import ResourceExpression
from plainbox.impl.unit.job import JobDefinition
from plainbox.impl.unit.template import TemplateUnit
from plainbox.impl.unit.test_unit import UnitFieldValidationTests
from plainbox.impl.unit.unit import Unit
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.validators import UnitValidationContext
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity
from plainbox.impl.validation import ValidationError
from plainbox.vendor import mock


class TemplateUnitValidator(TestCase):

    def setUp(self):
        warnings.filterwarnings(
            'ignore', 'validate is deprecated since version 0.11')

    def tearDown(self):
        warnings.resetwarnings()

    def test_checks_if_template_resource_is_defined(self):
        with self.assertRaises(ValidationError) as boom:
            TemplateUnit({}).validate()
        self.assertEqual(
            boom.exception.field, TemplateUnit.fields.template_resource)
        self.assertEqual(boom.exception.problem, Problem.missing)

    def test_checks_if_template_filter_is_bad(self):
        with self.assertRaises(ValidationError) as boom:
            TemplateUnit({
                'template-resource': 'resource',
                'template-filter': 'this is not a valid program'
            }).validate()
        self.assertEqual(
            boom.exception.field, TemplateUnit.fields.template_filter)
        self.assertEqual(boom.exception.problem, Problem.wrong)

    def test_checks_if_id_is_constant(self):
        with self.assertRaises(ValidationError) as boom:
            TemplateUnit({
                'template-resource': 'resource',
                'id': 'constant',
            }).validate()
        self.assertEqual(
            boom.exception.field, JobDefinition.fields.id)
        self.assertEqual(boom.exception.problem, Problem.constant)

    def test_checks_if_plugin_is_variable(self):
        with self.assertRaises(ValidationError) as boom:
            TemplateUnit({
                'template-resource': 'resource',
                'id': 'variable-{attr}',
                'plugin': 'variable-{attr}',
            }).validate()
        self.assertEqual(
            boom.exception.field, JobDefinition.fields.plugin)
        self.assertEqual(boom.exception.problem, Problem.variable)

    def test_checks_if_summary_is_constant(self):
        with self.assertRaises(ValidationError) as boom:
            TemplateUnit({
                'template-resource': 'resource',
                'id': 'variable-{attr}',
                'plugin': 'constant',
                'summary': 'constant',
            }).validate()
        self.assertEqual(
            boom.exception.field, JobDefinition.fields.summary)
        self.assertEqual(boom.exception.problem, Problem.constant)

    def test_checks_if_description_is_constant(self):
        with self.assertRaises(ValidationError) as boom:
            TemplateUnit({
                'template-resource': 'resource',
                'id': 'variable-{attr}',
                'plugin': 'constant',
                'summary': 'variable-{attr}',
                'description': 'constant',
            }).validate()
        self.assertEqual(
            boom.exception.field, JobDefinition.fields.description)
        self.assertEqual(boom.exception.problem, Problem.constant)

    def test_checks_if_user_is_variable(self):
        with self.assertRaises(ValidationError) as boom:
            TemplateUnit({
                'template-resource': 'resource',
                'id': 'variable-{attr}',
                'plugin': 'constant',
                'summary': 'variable-{attr}',
                'description': 'variable-{attr}',
                'command': 'variable-{attr}',
                'user': 'variable-{attr}',
            }).validate()
        self.assertEqual(
            boom.exception.field, JobDefinition.fields.user)
        self.assertEqual(boom.exception.problem, Problem.variable)

    def test_checks_instantiated_job(self):
        template = TemplateUnit({
            'template-resource': 'resource',
            'id': 'variable-{attr}',
            'plugin': 'constant',
            'summary': 'variable-{attr}',
            'description': 'variable-{attr}',
            'command': 'variable-{attr}',
            'user': 'constant',
        })
        job = mock.Mock(spec_set=JobDefinition)
        with mock.patch.object(template, 'instantiate_one', return_value=job):
            template.validate()
        job.validate.assert_called_once_with(strict=False, deprecated=False)


class TemplateUnitTests(TestCase):

    def test_resource_partial_id__empty(self):
        """
        Ensure that ``resource_partial_id`` defaults to None
        """
        self.assertEqual(TemplateUnit({}).resource_partial_id, None)

    def test_resource_partial_id__bare(self):
        """
        Ensure that ``resource_partial_id`` is looked up from the
        ``template-resource`` field
        """
        self.assertEqual(TemplateUnit({
            'template-resource': 'resource'
        }).resource_partial_id, 'resource')

    def test_resource_partial_id__explicit(self):
        """
        Ensure that ``resource_partial_id`` is correctly parsed from a fully
        qualified resource identifier.
        """
        self.assertEqual(TemplateUnit({
            'template-resource': 'explicit::resource'
        }).resource_partial_id, 'resource')

    def test_resource_namespace__empty(self):
        """
        Ensure that ``resource_namespace`` defaults to None
        """
        self.assertEqual(TemplateUnit({}).resource_namespace, None)

    def test_resource_namespace__bare(self):
        """
        Ensure that ``resource_namespace`` is correctly parsed from a
        not-qualified resource identifier
        """
        self.assertEqual(TemplateUnit({
            'template-resource': 'resource'
        }).resource_namespace, None)

    def test_resource_namespace__implicit(self):
        """
        Ensure that ``resource_namespace``, if not parsed from a
        fully-qualified resource identifier, defaults to the provider
        namespace.
        """
        provider = mock.Mock(spec=IProvider1)
        self.assertEqual(TemplateUnit({
            'template-resource': 'resource'
        }, provider=provider).resource_namespace, provider.namespace)

    def test_resource_namespace__explicit(self):
        """
        Ensure that ``resource_namespace``, is correctly pared from a
        fully-qualified resource identifier
        """
        self.assertEqual(TemplateUnit({
            'template-resource': 'explicit::resource'
        }).resource_namespace, 'explicit')

    def test_resource_id__empty(self):
        """
        Ensure that ``resource_id`` defaults to None
        """
        self.assertEqual(TemplateUnit({}).resource_id, None)

    def test_resource_id__bare(self):
        """
        Ensure that ``resource_id`` is just the partial resource identifier
        when both a fully-qualified resource identifier and the provider
        namespace are absent.
        """
        self.assertEqual(TemplateUnit({
            'template-resource': 'resource'
        }).resource_id, 'resource')

    def test_resource_id__explicit(self):
        """
        Ensure that ``resource_id`` is the fully-qualified resource identifier
        when ``template-resource`` is also fully-qualified.
        """
        self.assertEqual(TemplateUnit({
            'template-resource': 'explicit::resource'
        }).resource_id, 'explicit::resource')

    def test_resource_id__template_imports(self):
        """
        Ensure that ``resource_id`` is the fully-qualified resource identifier
        when ``template-resource`` refers to a ``template-imports`` imported
        name
        """
        self.assertEqual(TemplateUnit({
            'template-imports': (
                'from 2014.com.example import resource/name as rc'),
            'template-resource': 'rc'
        }).resource_id, '2014.com.example::resource/name')

    def test_resource_id__template_imports_and_provider_ns(self):
        """
        Ensure that ``resource_id`` is the fully-qualified resource identifier
        when ``template-resource`` refers to a ``template-imports`` imported
        name, even if provider namespace could have been otherwise used

        We're essentially testing priority of imports over the implicit namespa
        """
        provider = mock.Mock(spec=IProvider1)
        provider.namespace = 'namespace'
        self.assertEqual(TemplateUnit({
            'template-imports': (
                'from 2014.com.example import resource/name as rc'),
            'template-resource': 'rc'
        }, provider=provider).resource_id, '2014.com.example::resource/name')

    def test_resource_id__template_and_provider_ns(self):
        """
        Ensure that ``resource_id`` is the fully-qualified resource identifier
        when ``template-resource`` refers to a partial identifier but the
        provider has a namespace we can use
        """
        provider = mock.Mock(spec=IProvider1)
        provider.namespace = 'namespace'
        self.assertEqual(TemplateUnit({
            'template-resource': 'rc'
        }, provider=provider).resource_id, 'namespace::rc')

    def test_template_resource__empty(self):
        self.assertEqual(TemplateUnit({}).template_resource, None)

    def test_template_resource__bare(self):
        self.assertEqual(TemplateUnit({
            'template-resource': 'resource'
        }).template_resource, 'resource')

    def test_template_resource__explicit(self):
        self.assertEqual(TemplateUnit({
            'template-resource': 'explicit::resource'
        }).template_resource, 'explicit::resource')

    def test_template_filter__empty(self):
        """
        Ensure that ``template_filter`` defaults to None
        """
        self.assertEqual(TemplateUnit({}).template_filter, None)

    def test_template_filter__typical(self):
        """
        Ensure that ``template_filter`` is looked up from the
        ``template-filter`` field.
        """
        self.assertEqual(TemplateUnit({
            'template-filter': 'resource.attr == "value"'
        }).template_filter, 'resource.attr == "value"')

    def test_template_filter__multi_line(self):
        """
        Ensure that ``template_filter`` can have multiple lines
        (corresponding to multiple conditions that must be met)
        """
        self.assertEqual(TemplateUnit({
            'template-filter': (
                'resource.attr == "value"\n'
                'resource.other == "some other value"\n')
        }).template_filter, (
            'resource.attr == "value"\n'
            'resource.other == "some other value"\n'
        ))

    def test_get_filter_program__nothing(self):
        # Without a template-program field there is no filter program
        self.assertEqual(TemplateUnit({}).get_filter_program(), None)

    def test_get_filter_program__bare(self):
        # Programs are properly represented
        prog = TemplateUnit({
            'template-filter': 'resource.attr == "value"'
        }).get_filter_program()
        # The program wraps the right expressions
        self.assertEqual(
            prog.expression_list,
            [ResourceExpression('resource.attr == "value"')])
        # The program references the right resources
        self.assertEqual(prog.required_resources, set(['resource']))

    def test_get_filter_program__explicit(self):
        # Programs are properly represented
        prog = TemplateUnit({
            'template-resource': 'explicit::resource',
            'template-filter': 'resource.attr == "value"'
        }).get_filter_program()
        # The program wraps the right expressions
        self.assertEqual(
            prog.expression_list,
            [ResourceExpression('resource.attr == "value"')])
        # The program references the right resources
        self.assertEqual(prog.required_resources, set(['explicit::resource']))

    def test_get_filter_program__inherited(self):
        provider = mock.Mock(spec=IProvider1)
        provider.namespace = 'inherited'
        # Programs are properly represented
        prog = TemplateUnit({
            'template-resource': 'resource',
            'template-filter': 'resource.attr == "value"'
        }, provider=provider).get_filter_program()
        # The program wraps the right expressions
        self.assertEqual(
            prog.expression_list,
            [ResourceExpression('resource.attr == "value"')])
        # The program references the right resources
        self.assertEqual(prog.required_resources, set(['inherited::resource']))

    def test_get_target_unit_cls(self):
        t1 = TemplateUnit({})
        self.assertIs(t1.get_target_unit_cls(), JobDefinition)
        t2 = TemplateUnit({'template-unit': 'job'})
        self.assertIs(t2.get_target_unit_cls(), JobDefinition)
        t3 = TemplateUnit({'template-unit': 'unit'})
        self.assertIs(t3.get_target_unit_cls(), Unit)
        t4 = TemplateUnit({'template-unit': 'template'})
        self.assertIs(t4.get_target_unit_cls(), TemplateUnit)

    def test_instantiate_one(self):
        template = TemplateUnit({
            'template-resource': 'resource',
            'id': 'check-device-{dev_name}',
            'summary': 'Test {name} ({sys_path})',
            'plugin': 'shell',
        })
        job = template.instantiate_one(Resource({
            'dev_name': 'sda1',
            'name': 'some device',
            'sys_path': '/sys/something',
        }))
        self.assertIsInstance(job, JobDefinition)
        self.assertEqual(job.partial_id, 'check-device-sda1')
        self.assertEqual(job.summary, 'Test some device (/sys/something)')
        self.assertEqual(job.plugin, 'shell')

    def test_should_instantiate__filter(self):
        template = TemplateUnit({
            'template-resource': 'resource',
            'template-filter': 'resource.attr == "value"',
        })
        self.assertTrue(
            template.should_instantiate(Resource({'attr': 'value'})))
        self.assertFalse(
            template.should_instantiate(Resource({'attr': 'other value'})))
        self.assertFalse(
            template.should_instantiate(Resource()))

    def test_should_instantiate__no_filter(self):
        template = TemplateUnit({
            'template-resource': 'resource',
        })
        self.assertTrue(
            template.should_instantiate(Resource({'attr': 'value'})))
        self.assertTrue(
            template.should_instantiate(Resource({'attr': 'other value'})))
        self.assertTrue(
            template.should_instantiate(Resource()))

    def test_instantiate_all(self):
        template = TemplateUnit({
            'template-resource': 'resource',
            'template-filter': 'resource.attr == "value"',
            'id': 'check-device-{dev_name}',
            'summary': 'Test {name} ({sys_path})',
            'plugin': 'shell',
        })
        unit_list = template.instantiate_all([
            Resource({
                'attr': 'value',
                'dev_name': 'sda1',
                'name': 'some device',
                'sys_path': '/sys/something',
            }),
            Resource({
                'attr': 'bad value',
                'dev_name': 'sda2',
                'name': 'some other device',
                'sys_path': '/sys/something-else',
            })
        ])
        self.assertEqual(len(unit_list), 1)
        self.assertEqual(unit_list[0].partial_id, 'check-device-sda1')


class TemplateUnitFieldValidationTests(UnitFieldValidationTests):

    unit_cls = TemplateUnit

    def test_template_unit__untranslatable(self):
        issue_list = self.unit_cls({
            # NOTE: the value must be a valid unit!
            '_template-unit': 'unit'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.template_unit,
            Problem.unexpected_i18n, Severity.warning)

    def test_template_unit__present(self):
        issue_list = self.unit_cls({
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.template_unit,
            Problem.missing, Severity.advice)

    def test_template_resource__untranslatable(self):
        issue_list = self.unit_cls({
            '_template-resource': 'template_resource'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.template_resource,
            Problem.unexpected_i18n, Severity.warning)

    def test_template_resource__refers_to_other_units(self):
        unit = self.unit_cls({
            'template-resource': 'some-unit'
        }, provider=self.provider)
        message = ("field 'template-resource',"
                   " unit 'ns::some-unit' is not available")
        self.provider.unit_list = [unit]
        self.provider.problem_list = []
        context = UnitValidationContext([self.provider])
        issue_list = unit.check(context=context)
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.template_resource,
            Problem.bad_reference, Severity.error, message)

    def test_template_resource__refers_to_other_jobs(self):
        other_unit = UnitWithId({
            'id': 'some-unit'
        }, provider=self.provider)
        unit = self.unit_cls({
            'template-resource': 'some-unit'
        }, provider=self.provider)
        message = ("field 'template-resource',"
                   " the referenced unit is not a job")
        self.provider.unit_list = [unit, other_unit]
        self.provider.problem_list = []
        context = UnitValidationContext([self.provider])
        issue_list = unit.check(context=context)
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.template_resource,
            Problem.bad_reference, Severity.error, message)

    def test_template_filter__untranslatable(self):
        issue_list = self.unit_cls({
            '_template-filter': 'template-filter'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.template_filter,
            Problem.unexpected_i18n, Severity.warning)
