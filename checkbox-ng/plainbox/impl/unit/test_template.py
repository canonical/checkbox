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

from plainbox.abc import IProvider1
from plainbox.impl.resource import Resource
from plainbox.impl.resource import ResourceExpression
from plainbox.impl.unit.job import JobDefinition
from plainbox.impl.unit.template import TemplateUnit
from plainbox.impl.unit.test_unit import UnitFieldValidationTests
from plainbox.impl.unit.unit import Unit
from plainbox.impl.unit.unit import MissingParam
from plainbox.impl.unit.unit_with_id import UnitWithId
from plainbox.impl.unit.validators import UnitValidationContext
from plainbox.impl.validation import Problem
from plainbox.impl.validation import Severity
from plainbox.vendor import mock


class TemplateUnitTests(TestCase):

    def test_id(self):
        template = TemplateUnit({
            "template-resource": "resource",
            "template-id": "check-devices",
            "id": "check-device-{dev_name}",
        })
        self.assertEqual(template.id, "check-device-{dev_name}")

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
        provider.namespace = 'namespace'
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
                'from com.example import resource/name as rc'),
            'template-resource': 'rc'
        }).resource_id, 'com.example::resource/name')

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
                'from com.example import resource/name as rc'),
            'template-resource': 'rc'
        }, provider=provider).resource_id, 'com.example::resource/name')

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

    def test_slugify(self):
        self.assertEqual(
            TemplateUnit.slugify_template_id("stress/benchmark_{disk}"),
            "stress/benchmark_disk"
        )
        self.assertEqual(
            TemplateUnit.slugify_template_id("ns::stress/benchmark_{disk}"),
            "ns::stress/benchmark_disk"
        )
        self.assertEqual(
            TemplateUnit.slugify_template_id("suspend_{{ iterations }}_times"),
            "suspend_iterations_times"
        )
        self.assertEqual(TemplateUnit.slugify_template_id(), None)

    def test_template_id(self):
        self.assertEqual(TemplateUnit({
            "template-id": "template_id",
        }).template_id, "template_id")

    def test_template_id__from_job_id(self):
        self.assertEqual(TemplateUnit({
            "id": "job_id_{param}",
        }).template_id, "job_id_param")

    def test_template_id__precedence(self):
        """Ensure template-id takes precedence over job id."""
        self.assertEqual(TemplateUnit({
            "template-id": "template_id",
            "id": "job_id_{param}",
        }).template_id, "template_id")

    def test_template_id__from_job_id_jinja2(self):
        self.assertEqual(TemplateUnit({
            "template-resource": "resource",
            "template-engine": "jinja2",
            "id": "job_id_{{ param }}",
        }).template_id, "job_id_param")

    def test_template_id__precedence_jinja2(self):
        """Ensure template-id takes precedence over Jinja2-templated job id."""
        self.assertEqual(TemplateUnit({
            "template-id": "template_id",
            "template-resource": "resource",
            "template-engine": "jinja2",
            "id": "job_id_{{ param }}",
        }).template_id, "template_id")

    def test_template_summary(self):
        self.assertEqual(TemplateUnit({
            "template-summary": "summary",
        }).template_summary, "summary")

    def test_template_description(self):
        self.assertEqual(TemplateUnit({
            "template-description": "description",
        }).template_description, "description")

    def test_tr_template_summary(self):
        """Ensure template_summary is populated with the translated field."""
        self.assertEqual(TemplateUnit({
            "_template-summary": "summary",
        }).template_summary, "summary")

    def test_tr_template_description(self):
        """
        Ensure template_description is populated with the translated field.
        """
        self.assertEqual(TemplateUnit({
            "_template-description": "description",
        }).template_description, "description")

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

    def test_instantiate_missing_parameter(self):
        """
        Ensure that a MissingParam exeception is raised when attempting to
        instantiate a template unit that contains a paremeter not present in
        the associated resource.
        """
        template = TemplateUnit({
            'template-resource': 'resource',
            'id': 'check-device-{missing}',
            'plugin': 'shell',
        })
        job = template.instantiate_one(Resource({
            'dev_name': 'sda1',
            'name': 'some device',
            'sys_path': '/sys/something',
        }))
        self.assertIsInstance(job, JobDefinition)
        with self.assertRaises(MissingParam):
            self.assertEqual(job.partial_id, 'check-device-sda1')

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


class TemplateUnitJinja2Tests(TestCase):

    def test_id_jinja2(self):
        template = TemplateUnit({
            'template-resource': 'resource',
            'template-engine': 'jinja2',
            'id': 'check-device-{{ dev_name }}',
        })
        self.assertEqual(template.id, "check-device-{{ dev_name }}")

    def test_instantiate_one_jinja2(self):
        template = TemplateUnit({
            'template-resource': 'resource',
            'template-engine': 'jinja2',
            'id': 'check-device-{{ dev_name }}',
            'summary': 'Test {{ name }} ({{ sys_path }})',
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


class TemplateUnitFieldValidationTests(UnitFieldValidationTests):

    unit_cls = TemplateUnit

    def test_template_id__untranslatable(self):
        issue_list = self.unit_cls({
            '_template-id': 'template_id'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.template_id,
            Problem.unexpected_i18n, Severity.warning)

    def test_template_id__bare(self):
        issue_list = self.unit_cls({
            "template-id": "ns::id"
        }, provider=self.provider).check()
        message = ("template 'ns::id', field 'template-id', identifier cannot "
                   "define a custom namespace")
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.template_id,
            Problem.wrong, Severity.error, message)

    def test_template_id__unique(self):
        unit = self.unit_cls({
            'template-id': 'id'
        }, provider=self.provider)
        other_unit = self.unit_cls({
            'template-id': 'id'
        }, provider=self.provider)
        self.provider.unit_list = [unit, other_unit]
        self.provider.problem_list = []
        context = UnitValidationContext([self.provider])
        message_start = (
            "{} 'id', field 'template-id', clashes with 1 other unit,"
            " look at: "
        ).format(unit.tr_unit())
        issue_list = unit.check(context=context)
        issue = self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.template_id,
            Problem.not_unique, Severity.error)
        self.assertTrue(issue.message.startswith(message_start))

    def test_unit__present(self):
        """
        TemplateUnit.unit always returns "template", the default error for the
        base Unit class should never happen.
        """
        issue_list = self.unit_cls({
        }, provider=self.provider).check()
        message = "field 'unit', unit should explicitly define its type"
        self.assertIssueNotFound(issue_list, self.unit_cls.Meta.fields.unit,
                                 Problem.missing, Severity.advice, message)

    def test_template_unit__untranslatable(self):
        issue_list = self.unit_cls({
            # NOTE: the value must be a valid unit!
            '_template-unit': 'unit'
        }, provider=self.provider).check()
        self.assertIssueFound(
            issue_list, self.unit_cls.Meta.fields.template_unit,
            Problem.unexpected_i18n, Severity.warning)

    def test_template_summary__translatable(self):
        issue_list = self.unit_cls({
            'template-summary': 'template_summary'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list,
                              self.unit_cls.Meta.fields.template_summary,
                              Problem.expected_i18n,
                              Severity.warning)

    def test_template_summary__present(self):
        issue_list = self.unit_cls({
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list,
                              self.unit_cls.Meta.fields.template_summary,
                              Problem.missing,
                              Severity.advice)

    def test_template_summary__one_line(self):
        issue_list = self.unit_cls({
            'template-summary': 'line1\nline2'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list,
                              self.unit_cls.Meta.fields.template_summary,
                              Problem.wrong,
                              Severity.warning)

    def test_template_summary__short_line(self):
        issue_list = self.unit_cls({
            'template-summary': 'x' * 81
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list,
                              self.unit_cls.Meta.fields.template_summary,
                              Problem.wrong,
                              Severity.warning)

    def test_template_description__translatable(self):
        issue_list = self.unit_cls({
            'template-description': 'template_description'
        }, provider=self.provider).check()
        self.assertIssueFound(issue_list,
                              self.unit_cls.Meta.fields.template_description,
                              Problem.expected_i18n,
                              Severity.warning)

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
