# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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


from io import StringIO
from textwrap import dedent
from unittest import TestCase, mock, SkipTest
from functools import wraps


from checkbox_ng.launcher.translator import (
    split_comment,
    split_string_values,
    Translator,
    commentable_value,
    CommentedError,
)


def only_if_rumel_installed_or_skip(f):
    try:
        from ruamel.yaml import YAML

        return f
    except ImportError:
        pass

    @wraps(f)
    def _f(self, *args, **kwargs):
        raise SkipTest(
            "Not testing as translator wasn't installed. To test install checkbox-ng[translator]"
        )

    return _f


class SplitStringableTests(TestCase):
    def test_no_comment_in_string(self):
        value, comment = split_comment("just some text")
        self.assertEqual(value, "just some text")
        self.assertEqual(comment, "")

    def test_string_is_just_a_comment(self):
        value, comment = split_comment("# this is only a comment")
        self.assertEqual(value, "")
        self.assertEqual(comment, "this is only a comment")

    def test_normal_text_with_comment(self):
        value, comment = split_comment("some text # a comment")
        self.assertEqual(value, "some text")
        self.assertEqual(comment, "a comment")

    def test_fake_comment_in_string_delimiters(self):
        # Double quotes
        value, comment = split_comment('"fake # inside" # real comment')
        self.assertEqual(value, '"fake # inside"')
        self.assertEqual(comment, "real comment")

        # Single quotes
        value, comment = split_comment("'fake # inside' # real comment")
        self.assertEqual(value, "'fake # inside'")
        self.assertEqual(comment, "real comment")

    def test_nested_escaped_delimiters_with_fake_comments(self):
        # Escaped quote inside string, fake comments, real comment at end
        value, comment = split_comment("'it\\'s \"a #fake\" test' # real")
        self.assertEqual(value, "'it\\'s \"a #fake\" test'")
        self.assertEqual(comment, "real")

    def test_string_values(self):
        value, attributes = split_string_values(
            '"bluetooth/bluez-internal-hci-tests_Read Country Code" '
            "certification-status=blocker"
        )
        self.assertEqual(
            value, '"bluetooth/bluez-internal-hci-tests_Read Country Code"'
        )
        self.assertEqual(attributes, "certification-status=blocker")


class CommentedValueTranslatorTests(TestCase):
    def test_no_comment(self):
        value = commentable_value("value")
        self.assertEqual(value, "value")

    def test_comment(self):
        with self.assertRaises(CommentedError) as cm:
            _ = commentable_value("value # some comment")
        self.assertEqual("value", cm.exception.value)
        self.assertEqual("some comment", cm.exception.comment)


class TranslatorTestCase(TestCase):
    @only_if_rumel_installed_or_skip
    def run_translator(self, pxu_input):
        from ruamel.yaml import YAML

        input_file = StringIO(pxu_input)
        output_file = StringIO()

        mock_path = mock.MagicMock()
        mock_path.open.return_value.__enter__.return_value = input_file
        mock_path.__str__.return_value = "test.pxu"

        mock_yaml_path = mock.MagicMock()
        mock_yaml_path.open.return_value.__enter__.return_value = output_file
        mock_path.with_suffix.return_value = mock_yaml_path

        mock_ctx = mock.MagicMock()
        mock_ctx.args.paths = [mock_path]

        translator = Translator()
        translator.invoked(mock_ctx)

        output_file.seek(0)
        yaml = YAML()
        return list(yaml.load_all(output_file))

    @only_if_rumel_installed_or_skip
    def parse_yaml(self, yaml_str):
        from ruamel.yaml import YAML

        yaml = YAML()
        return list(yaml.load_all(StringIO(yaml_str)))

    def assertYamlEqual(self, first, second):
        """
        Compare two yamls ignoring order of keys
        """
        first = [dict(sorted(x.items())) for x in first]
        second = [dict(sorted(x.items())) for x in second]
        self.assertEqual(first, second)


class TranslatorJobUnitTests(TranslatorTestCase):

    def test_basic_job_unit(self):
        pxu_input = dedent("""
            id: test-job
            _summary: A test job
            plugin: shell
            command: echo "hello"
            requires: package.name == 'foo'
            depends:
                other-job
                another-job
            flags: simple, preserve-cwd
            """).strip()

        expected_yaml = dedent("""
            id: test-job
            summary: A test job
            plugin: shell
            command: echo "hello"
            requires:
              - package.name == 'foo'
            depends:
              - other-job
              - another-job
            flags:
              - simple
              - preserve-cwd
            """).strip()

        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)

    def test_job_unit_with_comments(self):
        pxu_input = dedent("""
            id: test-job  # the job identifier
            _summary: A test job
            plugin: shell  # automated test
            command: echo "hello"
            requires:
                # requires comment above
                package.name == 'foo'  # need foo installed
                # requires comment in the middle
                package.version > 10
            depends: other-job another-job  # must run after these
            flags: simple, preserve-cwd  # keep it simple
            """).strip()

        expected_yaml = dedent("""
            id: test-job  # the job identifier
            summary: A test job
            plugin: shell  # automated test
            command: echo "hello"
            requires:
              # requires comment above
              - package.name == 'foo'  # need foo installed
              # requires comment in the middle
              - package.version > 10
            depends:
              - other-job
              - another-job  # must run after these
            flags:
              - simple
              - preserve-cwd  # keep it simple
            """).strip()

        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)

    def test_dont_translate_jinja(self):
        pxu_input = dedent("""
            requires:
                {% jinja comments, for some reson %}
                package.name == 'foo'
                package.version > 10
            """).strip()

        expected_yaml = dedent("""
            requires: |
                {% jinja comments, for some reson %}
                package.name == 'foo'
                package.version > 10
            """)

        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)

    def test_multiline_fields(self):
        pxu_input = dedent("""
            id: test-job
            _summary: A test job
            plugin: user-interact-verify
            command:
              echo "hello"
            _purpose:
              This test verifies that the thing works.
              It does multiple checks.
            _steps:
              1. Do the first thing
              2. Do the second thing
              3. Observe the result
            _verification:
              Did the thing work correctly?
            requires:
              package.name == 'foo'
              device.category == 'DISK'
            """).strip()

        expected_yaml = dedent("""
            id: test-job
            summary: A test job
            plugin: user-interact-verify
            command: echo "hello"
            purpose: |
              This test verifies that the thing works.
              It does multiple checks.
            steps: |
              1. Do the first thing
              2. Do the second thing
              3. Observe the result
            verification: Did the thing work correctly?
            requires:
              - package.name == 'foo'
              - device.category == 'DISK'
            """).strip()

        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)

    def test_siblings_json_to_yaml(self):
        pxu_input = dedent("""
            id: foo
            _summary: foo foo foo
            plugin: shell
            command: echo "Hello world"
            flags: simple
            _siblings: [
                { "id": "foo-after-suspend",
                  "_summary": "foo foo foo after suspend",
                  "depends": "suspend/advanced"},
                { "id": "foo-after-reboot",
                  "_summary": "foo foo foo after reboot",
                  "depends": "reboot/advanced"}
                ]
            """).strip()

        expected_yaml = dedent("""
            id: foo
            summary: foo foo foo
            plugin: shell
            command: echo "Hello world"
            flags:
              - simple
            siblings:
              - id: foo-after-suspend
                summary: foo foo foo after suspend
                depends:
                  - suspend/advanced
              - id: foo-after-reboot
                summary: foo foo foo after reboot
                depends:
                  - reboot/advanced
            """).strip()

        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)

    def test_siblings_template_json_to_yaml(self):
        pxu_input = dedent("""
            _siblings: [
                {{ "id": "{id_field}",
                  "_summary": "{summary_field}"}}
                ]
            """).strip()

        expected_yaml = dedent("""
            siblings:
              - id: '{id_field}'
                summary: '{summary_field}'
            """).strip()
        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)

    def test_imports_lines_to_array(self):
        pxu_input = dedent("""
            id: test-job
            _summary: A test job
            plugin: shell
            command: echo "test"
            imports:
              from com.canonical.certification import cpuinfo
              from com.canonical.certification import cpu-01-info as cpu01
              from com.canonical.certification import meminfo
            requires:
              'armhf' in cpuinfo.platform
              'avx2' in cpu01.other
            """).strip()

        expected_yaml = dedent("""
            id: test-job
            summary: A test job
            plugin: shell
            command: echo "test"
            imports:
              - from com.canonical.certification import cpuinfo
              - from com.canonical.certification import cpu-01-info as cpu01
              - from com.canonical.certification import meminfo
            requires:
              - "'armhf' in cpuinfo.platform"
              - "'avx2' in cpu01.other"
            """).strip()

        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)

    def test_other_array_fields(self):
        pxu_input = dedent("""
            id: test-job # test job comment
            _summary: A test job
            plugin: shell
            command: echo "test"
            user: root
            environ: HOME PATH DISPLAY
            after: setup-job prepare-job
            before: cleanup-job teardown-job
            salvages: failed-job broken-job
            """).strip()

        expected_yaml = dedent("""
            id: test-job
            summary: A test job
            plugin: shell
            command: echo "test"
            user: root
            environ:
              - HOME
              - PATH
              - DISPLAY
            after:
              - setup-job
              - prepare-job
            before:
              - cleanup-job
              - teardown-job
            salvages:
              - failed-job
              - broken-job
            """).strip()

        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)

    def test_top_level_comment(self):
        pxu_input = dedent("""
            # top level comments
            # should be preserved (best effort)
            id: test-job
            _summary: A test job
            # not this one, this one is impossible
            plugin: shell
            command: echo "test"
            """).strip()

        expected_yaml = dedent("""
            # top level comments
            # should be preserved (best effort)
            id: test-job
            summary: A test job
            # not this one, this one is impossible
            plugin: shell
            command: echo "test"
            """).strip()

        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)

    def test_jinja_depends_ignored(self):
        pxu_input = dedent("""
            id: test-job
            _summary: A test job
            depends:
                {% if true %}
                a
                {% endif %}
                b
            plugin: shell
            command: echo "test"
            """).strip()

        expected_yaml = dedent("""
            id: test-job
            summary: A test job
            depends: |
                {% if true %}
                a
                {% endif %}
                b
            plugin: shell
            command: echo "test"
            """).strip()

        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)


class TranslatorTestPlanTests(TranslatorTestCase):
    def test_basic_test_plan(self):
        pxu_input = dedent("""
            unit: test plan
            id: my-test-plan
            _name: My Test Plan
            _description:
                This is a test plan that runs some tests.
                It has multiple lines.
            include:
                # first item comment
                job-foo
                job-bar # comment in line
                # middle comment
                job-baz certification-status=blocker
            exclude:
                job-skip-me
            """).strip()

        expected_yaml = dedent("""
            unit: test plan
            id: my-test-plan
            name: My Test Plan
            description: |
                This is a test plan that runs some tests.
                It has multiple lines.
            include:
              # first item comment
              - job-foo
              - job-bar # comment in line
              # middle comment
              - job-baz:
                  certification-status: blocker
            exclude:
              - job-skip-me
            """).strip()

        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)

    def test_test_plan_all_inclusions(self):
        pxu_input = dedent("""
            unit: test plan
            id: full-test-plan
            _name: Full Test Plan
            setup_include:
                setup-job1
                com.canonical.qa::setup-job2
            bootstrap_include:
                resource-job-1
                resource-job-2
            mandatory_include:
                critical-job
                com.canonical.certification::submission-cert-automated
            include:
                test-job-1
                test-job-2
            nested_part:
                nested-part1
                nested-part2
            """).strip()

        expected_yaml = dedent("""
            unit: test plan
            id: full-test-plan
            name: Full Test Plan
            setup_include:
              - setup-job1
              - com.canonical.qa::setup-job2
            bootstrap_include:
              - resource-job-1
              - resource-job-2
            mandatory_include:
              - critical-job
              - com.canonical.certification::submission-cert-automated
            include:
              - test-job-1
              - test-job-2
            nested_part:
              - nested-part1
              - nested-part2
            """).strip()

        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)

    def test_test_plan_empty_include(self):
        pxu_input = dedent("""
            unit: test plan
            id: composite-test-plan
            _name: Composite Test Plan
            nested_part:
                other-test-plan
            include:
            """).strip()

        expected_yaml = dedent("""
            unit: test plan
            id: composite-test-plan
            name: Composite Test Plan
            nested_part:
              - other-test-plan
            include: []
            """).strip()

        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)

    def test_test_plan_with_nested_parts_and_overrides(self):
        pxu_input = dedent("""
            unit: test plan
            id: composite-test-plan
            _name: Composite Test Plan
            include:
            certification_status_overrides:
                apply blocker to .*wireless.*
                apply non-blocker to audio/.*
            """).strip()

        expected_yaml = dedent("""
            unit: test plan
            id: composite-test-plan
            name: Composite Test Plan
            include: []
            certification_status_overrides:
              - apply blocker to .*wireless.*
              - apply non-blocker to audio/.*
            """).strip()

        result = self.run_translator(pxu_input)
        expected = self.parse_yaml(expected_yaml)
        self.assertYamlEqual(result, expected)
