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

import argparse
import io
import os
import shutil
import subprocess
from typing import List
from unittest import TestCase, mock, skipIf

from checkbox_ng.launcher import completion
from checkbox_ng.launcher.checkbox_cli import (
    build_top_parser,
    get_commands,
    main,
)

COMPLETIONS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "completions")
)
COMMITTED_SCRIPTS = {
    "bash": "checkbox-cli.bash",
    "zsh": "_checkbox-cli",
    "fish": "checkbox-cli.fish",
}


class DescribeParserTests(TestCase):
    def test_options_choices_and_suppressed(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--flag", action="store_true")
        parser.add_argument("-t", "--transport", choices=["?", "file"])
        parser.add_argument("-o", "--output-file")
        parser.add_argument("--hidden", help=argparse.SUPPRESS)

        spec = completion.describe_parser(parser)

        self.assertIn((["--flag"], False, None, []), spec.options)
        self.assertIn(
            (["-t", "--transport"], True, None, ["file"]), spec.options
        )
        self.assertIn(
            (["-o", "--output-file"], True, completion.FILE, []), spec.options
        )
        self.assertNotIn("--hidden", completion._option_words(spec))

    def test_dynamic_positional(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("TEST_PLAN")

        spec = completion.describe_parser(parser, "expand")

        self.assertEqual(spec.positional_kind, completion.TEST_PLANS)

    def test_first_useful_positional_wins(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("host")
        parser.add_argument("launcher", nargs="?")
        parser.add_argument("paths", nargs="*")

        spec = completion.describe_parser(parser, "control")

        self.assertEqual(spec.positional_kind, completion.FILE)
        self.assertEqual(spec.positional_choices, [])

    def test_subparsers_are_choices(self):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        sub.add_parser("check")
        sub.add_parser("defaults")

        spec = completion.describe_parser(parser, "config")

        self.assertEqual(spec.positional_choices, ["check", "defaults"])


class BuildSpecTests(TestCase):
    def test_top_level_offers_public_commands_and_files(self):
        commands = get_commands()

        spec = completion.build_spec(build_top_parser(commands), commands)

        self.assertNotIn("__complete", spec)
        self.assertNotIn("__complete", spec[None].positional_choices)
        self.assertIn("completion", spec[None].positional_choices)
        self.assertEqual(spec[None].positional_kind, completion.FILE)
        self.assertIn("--debug", completion._option_words(spec[None]))
        self.assertEqual(spec["show"].positional_kind, completion.UNITS)

    def test_hidden_command_not_in_help(self):
        parser = build_top_parser(get_commands())

        self.assertNotIn("__complete", parser.format_help())


class CommittedScriptsTests(TestCase):
    def test_committed_scripts_are_up_to_date(self):
        for shell, filename in COMMITTED_SCRIPTS.items():
            with self.subTest(shell=shell):
                path = os.path.join(COMPLETIONS_DIR, filename)
                with open(path) as f:
                    committed = f.read()
                self.assertEqual(
                    committed,
                    completion.generate(shell),
                    "{} is outdated, regenerate it with: checkbox-cli "
                    "completion {} > {}".format(filename, shell, path),
                )


@skipIf(not shutil.which("bash"), "bash is not available")
class BashScriptTests(TestCase):
    def complete(self, line: str, dynamic: str = "") -> List[str]:
        # emulate a TAB press at the end of `line` without bash-completion
        script = completion.generate("bash")
        harness = (
            "{script}\n"
            "_checkbox_cli_dynamic() {{ printf '%s\\n' {dynamic}; }}\n"
            'read -ra COMP_WORDS <<< "$1"\n'
            '[[ "$1" == *" " ]] && COMP_WORDS+=("")\n'
            "COMP_CWORD=$((${{#COMP_WORDS[@]}} - 1))\n"
            "_checkbox_cli\n"
            "printf '%s\\n' \"${{COMPREPLY[@]}}\"\n"
        ).format(script=script, dynamic=dynamic)
        out = subprocess.check_output(
            ["bash", "-c", harness, "bash", line], universal_newlines=True
        )
        return out.splitlines()

    def test_subcommands(self):
        self.assertEqual(
            self.complete("checkbox-cli li"), ["list", "list-bootstrapped"]
        )

    def test_choices_with_spaces_are_escaped(self):
        self.assertEqual(
            self.complete("checkbox-cli list te"), ["template", "test\\ plan"]
        )

    def test_option_choices(self):
        self.assertEqual(
            self.complete("checkbox-cli run -t "),
            ["file", "stream", "submission-service"],
        )

    def test_implicit_launcher_options(self):
        self.assertIn("--verify", self.complete("checkbox-cli my.conf --"))

    def test_deprecated_alias(self):
        self.assertIn("--log-level", self.complete("checkbox-cli slave --"))

    def test_dynamic_values(self):
        self.assertEqual(
            self.complete("checkbox-cli expand b", "a::x b::y bb::z"),
            ["b::y", "bb::z"],
        )


class GetUnitIdsTests(TestCase):
    @mock.patch("checkbox_ng.launcher.completion.Explorer")
    def test_collects_requested_groups(self, explorer_mock):
        def node(group, name, children=()):
            obj = mock.Mock(group=group, children=list(children))
            obj.name = name
            return obj

        provider = node(
            "provider",
            "provider",
            [node("test plan", "ns::tp"), node("job", "ns::job")],
        )
        explorer_mock().get_object_tree.return_value = provider

        sa = mock.Mock()
        self.assertEqual(
            completion.get_unit_ids(sa, completion.TEST_PLANS), ["ns::tp"]
        )
        self.assertEqual(
            completion.get_unit_ids(sa, completion.UNITS),
            ["ns::job", "ns::tp"],
        )


class DynamicCompletionTests(TestCase):
    @mock.patch("checkbox_ng.launcher.completion.get_unit_ids")
    def test_prints_one_id_per_line(self, get_unit_ids_mock):
        get_unit_ids_mock.return_value = ["a::b", "c::d"]
        ctx = mock.Mock()
        ctx.args.kind = completion.UNITS

        with mock.patch("sys.stdout", new=io.StringIO()) as stdout:
            completion.DynamicCompletion().invoked(ctx)

        self.assertEqual(stdout.getvalue(), "a::b\nc::d\n")

    @mock.patch("checkbox_ng.launcher.completion.get_unit_ids")
    def test_silent_on_error(self, get_unit_ids_mock):
        get_unit_ids_mock.side_effect = RuntimeError("broken provider")
        ctx = mock.Mock()

        with mock.patch("sys.stdout", new=io.StringIO()) as stdout:
            self.assertEqual(completion.DynamicCompletion().invoked(ctx), 0)

        self.assertEqual(stdout.getvalue(), "")


class CompletionCommandTests(TestCase):
    @mock.patch("checkbox_ng.launcher.checkbox_cli.SessionAssistant")
    @mock.patch("sys.argv", ["checkbox-cli", "completion", "fish"])
    def test_main_routes_to_completion(self, _sa_mock):
        with mock.patch("sys.stdout", new=io.StringIO()) as stdout:
            main()

        self.assertEqual(stdout.getvalue(), completion.generate("fish"))
