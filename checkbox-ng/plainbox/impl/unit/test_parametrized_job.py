# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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

from unittest import TestCase

from plainbox.impl.unit.job import JobDefinition
from plainbox.impl.unit.parametrized_job import ParametrizedJobUnit
from plainbox.impl.validation import Severity


class ParametrizedJobTests(TestCase):
    def make_unit(self, **fields):
        data = {
            "unit": "parametrized-job",
            "template-id": "example",
            "parameters": [{"name": "first"}, {"name": "second"}],
            "id": "test-{name}",
            "_summary": "Test {name}",
            "plugin": "shell",
            "command": "echo {name} {__index__}",
        }
        data.update(fields)
        return ParametrizedJobUnit(data)

    def test_order_interpolation_and_metadata(self):
        unit = self.make_unit()
        jobs = unit.instantiate_jobs()
        self.assertEqual(
            [job.partial_id for job in jobs], ["test-first", "test-second"]
        )
        self.assertEqual(
            [job.command for job in jobs], ["echo first 1", "echo second 2"]
        )
        self.assertEqual(jobs[0].summary, "Test first")
        self.assertEqual(jobs[0].tr_summary(), "Test first")
        self.assertIs(jobs[0].origin, unit.origin)
        self.assertIs(jobs[0].provider, unit.provider)
        self.assertEqual(jobs[0].template_id, unit.template_id)
        self.assertTrue(all(isinstance(job, JobDefinition) for job in jobs))
        self.assertNotIn("parameters", jobs[0]._data)

    def test_source_identity(self):
        unit = self.make_unit(**{"template-id": None})
        self.assertEqual(unit.template_id, "test-name")
        self.assertEqual(str(unit), "test-name")
        self.assertIn("ParametrizedJobUnit", repr(unit))
        self.assertEqual(unit.unit, "parametrized-job")
        self.assertIsNone(unit.resource_id)
        self.assertIsNone(unit.parameters)
        self.assertFalse(unit.is_parametric)

    def test_template_id_is_allowed(self):
        unit = self.make_unit(**{"template-id": "example"})
        self.assertEqual(unit.template_id, "example")
        self.assertFalse(
            [
                issue
                for issue in unit.check()
                if issue.severity is Severity.error
            ]
        )

    def test_template_id_cannot_define_namespace(self):
        unit = self.make_unit(**{"template-id": "ns::example"})
        self.assertTrue(
            any(
                issue.field == "template-id"
                and issue.severity is Severity.error
                for issue in unit.check()
            )
        )

    def test_repeatable_expansion_preserves_source(self):
        unit = self.make_unit()
        data = unit._data.copy()
        raw_data = unit._raw_data.copy()
        records = [record.copy() for record in unit.parameter_records]
        first = unit.instantiate_jobs()
        second = unit.instantiate_jobs()
        self.assertEqual(
            [job.checksum for job in first], [job.checksum for job in second]
        )
        self.assertEqual(unit._data, data)
        self.assertEqual(unit._raw_data, raw_data)
        self.assertEqual(unit.parameter_records, records)

    def test_non_string_values(self):
        unit = self.make_unit(
            parameters=[{"name": "first", "count": 2}],
            **{"_summary": "Test {count}"},
        )
        self.assertEqual(unit.instantiate_jobs()[0].summary, "Test 2")
        self.assertFalse(
            [
                issue
                for issue in unit.check()
                if issue.severity is Severity.error
            ]
        )

    def test_empty_records(self):
        unit = self.make_unit(parameters=[])
        self.assertEqual(unit.instantiate_jobs(), [])
        self.assertFalse(
            [
                issue
                for issue in unit.check()
                if issue.severity is Severity.error
            ]
        )

    def test_list_values_are_not_cartesian_expanded(self):
        unit = self.make_unit(
            parameters=[{"name": "group", "members": ["first", "second"]}],
            command="echo {members}",
        )
        jobs = unit.instantiate_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].command, "echo ['first', 'second']")

    def test_empty_mapping_can_use_index(self):
        unit = self.make_unit(
            parameters=[{}],
            id="test-{__index__}",
            **{"_summary": "Test {__index__}", "command": "echo {__index__}"},
        )
        self.assertEqual(unit.instantiate_jobs()[0].partial_id, "test-1")

    def test_malformed_records(self):
        for value in (None, {}, "not json", [1], [["first"]]):
            with self.subTest(value=value):
                unit = self.make_unit(parameters=value)
                self.assertTrue(
                    any(
                        issue.field == "parameters"
                        and issue.severity is Severity.error
                        for issue in unit.check()
                    )
                )

    def test_template_fields_are_not_public(self):
        for field in (
            "template-resource",
            "template-filter",
            "template-imports",
            "template-engine",
            "template-unit",
            "template-summary",
            "template-description",
            "template-parameters",
        ):
            with self.subTest(field=field):
                unit = self.make_unit(**{field: ""})
                self.assertTrue(
                    any(
                        issue.field == "parameters"
                        and issue.severity is Severity.error
                        for issue in unit.check()
                    )
                )

    def test_validates_real_values(self):
        unit = self.make_unit(
            parameters=[{"name": "first", "plugin": "invalid"}],
            plugin="{plugin}",
        )
        self.assertTrue(
            any(
                issue.field == "plugin" and issue.severity is Severity.error
                for issue in unit.check()
            )
        )

    def test_missing_record_parameter(self):
        unit = self.make_unit(parameters=[{}])
        self.assertTrue(
            any(issue.severity is Severity.error for issue in unit.check())
        )

    def test_requires_does_not_supply_records(self):
        unit = self.make_unit(requires="device.present == 'yes'")
        self.assertEqual(len(unit.instantiate_jobs()), 2)
        self.assertEqual(
            unit.instantiate_jobs()[0].requires, "device.present == 'yes'"
        )
