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
"""
Shell completion support for checkbox-cli.

``checkbox-cli completion SHELL`` prints a completion script generated from
the argparse definitions of all the subcommands. Values that depend on the
installed providers (test plans, units) are fetched at completion time via
the hidden ``checkbox-cli __complete KIND`` subcommand.
"""

import argparse
import gettext
import shlex
from collections import OrderedDict
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Type,
)

from plainbox.impl.highlevel import Explorer
from plainbox.impl.session.assistant import SessionAssistant

if TYPE_CHECKING:
    from checkbox_ng.launcher.checkbox_cli import Context

_ = gettext.gettext

SHELLS = ("bash", "zsh", "fish")
HIDDEN_COMMANDS = ("__complete",)
COMMAND_NAMES = ("checkbox-cli", "checkbox.checkbox-cli")

# value kinds
FILE = "file"
TEST_PLANS = "test-plans"
UNITS = "units"
DYNAMIC_KINDS: Dict[str, Tuple[str, ...]] = {
    TEST_PLANS: ("test plan",),
    UNITS: ("job", "template", "test plan"),
}

DYNAMIC_POSITIONALS: Dict[Tuple[Optional[str], str], str] = {
    ("expand", "TEST_PLAN"): TEST_PLANS,
    ("list-bootstrapped", "TEST_PLAN"): TEST_PLANS,
    ("tp-export", "TEST_PLAN"): TEST_PLANS,
    ("show", "IDs"): UNITS,
    ("run", "PATTERN"): UNITS,
}
FILE_DESTS = ("launcher", "submission", "paths", "output_file")


# (option_strings, takes_value, value_kind, choices)
OptionSpec = Tuple[List[str], bool, Optional[str], List[str]]


class CommandSpec:
    """Completion-relevant description of one (sub)command parser."""

    def __init__(self) -> None:
        self.options: List[OptionSpec] = []
        # kind of value offered for positionals (FILE, dynamic kind or None)
        self.positional_kind: Optional[str] = None
        # fixed words offered for positionals (choices, sub-subcommands)
        self.positional_choices: List[str] = []


# maps each public subcommand to its CommandSpec, None is the top level
Spec = Dict[Optional[str], CommandSpec]


def _clean_choices(choices: Iterable[object]) -> List[str]:
    # "?" is a sentinel meaning "list the possible values", not a value
    return [str(c) for c in choices if c != "?"]


def describe_parser(
    parser: argparse.ArgumentParser, command: Optional[str] = None
) -> CommandSpec:
    spec = CommandSpec()
    for action in parser._actions:
        if action.help == argparse.SUPPRESS:
            continue
        if action.option_strings:
            takes_value = action.nargs != 0
            kind = FILE if action.dest in FILE_DESTS else None
            choices = _clean_choices(action.choices or [])
            spec.options.append(
                (list(action.option_strings), takes_value, kind, choices)
            )
            continue
        if spec.positional_kind or spec.positional_choices:
            # only the first positional with something to offer is used
            continue
        if action.choices:
            spec.positional_choices = _clean_choices(action.choices)
        elif (command, action.dest) in DYNAMIC_POSITIONALS:
            spec.positional_kind = DYNAMIC_POSITIONALS[(command, action.dest)]
        elif action.dest in FILE_DESTS:
            spec.positional_kind = FILE
    return spec


def build_spec(
    top_parser: argparse.ArgumentParser, commands: Mapping[str, Type]
) -> Spec:
    """
    Return an OrderedDict mapping each public subcommand to its CommandSpec.
    The key ``None`` describes the top level (before any subcommand).
    """
    spec: Spec = OrderedDict()
    top = describe_parser(top_parser)
    top.positional_choices = [c for c in commands if c not in HIDDEN_COMMANDS]
    # with no known subcommand checkbox-cli treats the argument as a launcher
    top.positional_kind = FILE
    spec[None] = top
    for name, cmd_cls in commands.items():
        if name in HIDDEN_COMMANDS:
            continue
        parser = argparse.ArgumentParser()
        cmd_cls().register_arguments(parser)
        spec[name] = describe_parser(parser, name)
    return spec


def _option_words(cmd_spec: CommandSpec) -> List[str]:
    return [o for opts, _, _, _ in cmd_spec.options for o in opts]


def _sh_case_pattern(words: Iterable[str]) -> str:
    return "|".join(shlex.quote(w) for w in words)


def generate_bash(spec: Spec, deprecated: Mapping[str, str]) -> str:
    out: List[str] = []
    w = out.append
    w("# bash completion for checkbox-cli")
    w("# Generated by `checkbox-cli completion bash`, do not edit.")
    w("")
    w("_checkbox_cli_dynamic() {")
    w('    if [ -n "$SNAP" ] && [ -x "$SNAP/bin/checkbox-cli-wrapper" ]; then')
    w('        "$SNAP/bin/checkbox-cli-wrapper" __complete "$1" 2>/dev/null')
    w("    else")
    w('        "${COMP_WORDS[0]}" __complete "$1" 2>/dev/null')
    w("    fi")
    w("}")
    w("")
    w("_checkbox_cli_words() {")
    # match against the typed word without shell quoting
    w("    local word ucur=${cur//\\\\/}")
    w("    ucur=${ucur#[\\\"\\']}")
    w("    while IFS= read -r word; do")
    w('        if [[ -n $word && $word == "$ucur"* ]]; then')
    w("            if [[ $cur == [\\\"\\']* ]]; then")
    w('                COMPREPLY+=("$word")')
    w("            else")
    w('                COMPREPLY+=("$(printf \'%q\' "$word")")')
    w("            fi")
    w("        fi")
    w('    done <<< "$1"')
    w("}")
    w("")
    w("_checkbox_cli_files() {")
    w("    if declare -F _filedir >/dev/null; then")
    w("        _filedir")
    w("    else")
    w("        compopt -o filenames 2>/dev/null")
    w("        local IFS=$'\\n'")
    w('        COMPREPLY+=($(compgen -f -- "$cur"))')
    w("    fi")
    w("}")
    w("")
    w("_checkbox_cli() {")
    w("    local cur prev words cword")
    w("    COMPREPLY=()")
    w("    if declare -F _get_comp_words_by_ref >/dev/null; then")
    w("        _get_comp_words_by_ref -n : cur prev words cword")
    w("    else")
    w('        words=("${COMP_WORDS[@]}")')
    w("        cword=$COMP_CWORD")
    w('        cur="${words[cword]}"')
    w('        prev="${words[cword-1]}"')
    w("    fi")
    w("")
    w('    local cmd="" i')
    w("    for ((i = 1; i < cword; i++)); do")
    w('        case "${words[i]}" in')
    w("            -*) continue ;;")
    for old, new in sorted(deprecated.items()):
        w("            {}) cmd={} ;;".format(shlex.quote(old), new))
    known = [name for name in spec if name is not None]
    w('            {}) cmd="${{words[i]}}" ;;'.format(_sh_case_pattern(known)))
    w("            *) cmd=launcher ;;")
    w("        esac")
    w("        break")
    w("    done")
    w("")
    w('    local opts="" values="" kind=""')
    w('    case "$cmd" in')
    for name, cmd_spec in spec.items():
        w("        {})".format(shlex.quote(name or "")))
        value_cases = []
        for opts, takes_value, kind, choices in cmd_spec.options:
            if not takes_value:
                continue
            if choices:
                action = "_checkbox_cli_words {}".format(
                    shlex.quote("\n".join(choices))
                )
            elif kind == FILE:
                action = "_checkbox_cli_files"
            else:
                action = ":"
            value_cases.append((opts, action))
        if value_cases:
            w('            case "$prev" in')
            for opts, action in value_cases:
                w(
                    "                {}) {}; return 0 ;;".format(
                        _sh_case_pattern(opts), action
                    )
                )
            w("            esac")
        w(
            "            opts={}".format(
                shlex.quote("\n".join(_option_words(cmd_spec)))
            )
        )
        if cmd_spec.positional_choices:
            w(
                "            values={}".format(
                    shlex.quote("\n".join(cmd_spec.positional_choices))
                )
            )
        if cmd_spec.positional_kind:
            w("            kind={}".format(cmd_spec.positional_kind))
        w("            ;;")
    w("    esac")
    w("")
    w("    if [[ $cur == -* ]]; then")
    w('        _checkbox_cli_words "$opts"')
    w("    else")
    w('        _checkbox_cli_words "$values"')
    w('        case "$kind" in')
    w("            {}) _checkbox_cli_files ;;".format(FILE))
    w(
        "            {}) "
        '_checkbox_cli_words "$(_checkbox_cli_dynamic "$kind")" ;;'.format(
            _sh_case_pattern(sorted(DYNAMIC_KINDS))
        )
    )
    w("        esac")
    w("    fi")
    w("    if declare -F __ltrim_colon_completions >/dev/null; then")
    w('        __ltrim_colon_completions "$cur"')
    w("    fi")
    w("    return 0")
    w("}")
    w("")
    w("complete -F _checkbox_cli {}".format(" ".join(COMMAND_NAMES)))
    return "\n".join(out) + "\n"


def _zsh_array(words: Iterable[str]) -> str:
    return "({})".format(" ".join(shlex.quote(word) for word in words))


def generate_zsh(spec: Spec, deprecated: Mapping[str, str]) -> str:
    out: List[str] = []
    w = out.append
    w("#compdef {}".format(" ".join(COMMAND_NAMES)))
    w("# zsh completion for checkbox-cli")
    w("# Generated by `checkbox-cli completion zsh`, do not edit.")
    w("")
    w("_checkbox_cli_dynamic() {")
    w("    local -a ids")
    w('    ids=(${(f)"$(${words[1]} __complete $1 2>/dev/null)"})')
    w("    compadd -a ids")
    w("}")
    w("")
    w("_checkbox-cli() {")
    w('    local cmd="" i')
    w("    for ((i = 2; i < CURRENT; i++)); do")
    w("        case ${words[i]} in")
    w("            (-*) continue ;;")
    for old, new in sorted(deprecated.items()):
        w("            ({}) cmd={} ;;".format(shlex.quote(old), new))
    known = [name for name in spec if name is not None]
    w("            ({}) cmd=${{words[i]}} ;;".format(_sh_case_pattern(known)))
    w("            (*) cmd=launcher ;;")
    w("        esac")
    w("        break")
    w("    done")
    w("")
    w("    local prev=${words[CURRENT-1]} cur=${words[CURRENT]}")
    w('    local -a opts values choices; local kind=""')
    w("    case $cmd in")
    for name, cmd_spec in spec.items():
        w("        ({})".format(shlex.quote(name or "")))
        value_cases = []
        for opts, takes_value, kind, choices in cmd_spec.options:
            if not takes_value:
                continue
            if choices:
                action = "choices={}; compadd -a choices".format(
                    _zsh_array(choices)
                )
            elif kind == FILE:
                action = "_files"
            else:
                action = ":"
            value_cases.append((opts, action))
        if value_cases:
            w("            case $prev in")
            for opts, action in value_cases:
                w(
                    "                ({}) {}; return ;;".format(
                        _sh_case_pattern(opts), action
                    )
                )
            w("            esac")
        w("            opts={}".format(_zsh_array(_option_words(cmd_spec))))
        if cmd_spec.positional_choices:
            w(
                "            values={}".format(
                    _zsh_array(cmd_spec.positional_choices)
                )
            )
        if cmd_spec.positional_kind:
            w("            kind={}".format(cmd_spec.positional_kind))
        w("            ;;")
    w("    esac")
    w("")
    w("    if [[ $cur == -* ]]; then")
    w("        compadd -a opts")
    w("        return")
    w("    fi")
    w("    (( ${#values} )) && compadd -a values")
    w("    case $kind in")
    w("        ({}) _files ;;".format(FILE))
    w(
        "        ({}) _checkbox_cli_dynamic $kind ;;".format(
            _sh_case_pattern(sorted(DYNAMIC_KINDS))
        )
    )
    w("    esac")
    w("}")
    w("")
    w('if [ "$funcstack[1]" = "_checkbox-cli" ]; then')
    w('    _checkbox-cli "$@"')
    w("else")
    w("    compdef _checkbox-cli {}".format(" ".join(COMMAND_NAMES)))
    w("fi")
    return "\n".join(out) + "\n"


def _fish_quote(word: str) -> str:
    return "'{}'".format(word.replace("\\", "\\\\").replace("'", "\\'"))


def _fish_option_flags(opts: Iterable[str]) -> str:
    flags = []
    for opt in opts:
        if opt.startswith("--"):
            flags.append("-l {}".format(opt[2:]))
        elif len(opt) == 2:
            flags.append("-s {}".format(opt[1:]))
        else:
            flags.append("-o {}".format(opt[1:]))
    return " ".join(flags)


def generate_fish(spec: Spec, deprecated: Mapping[str, str]) -> str:
    out: List[str] = []
    w = out.append
    w("# fish completion for checkbox-cli")
    w("# Generated by `checkbox-cli completion fish`, do not edit.")
    w("")
    w("function __checkbox_cli_cmd")
    w("    for token in (commandline -opc)[2..-1]")
    w("        switch $token")
    w("            case '-*'")
    w("                continue")
    groups: Dict[str, List[str]] = OrderedDict()
    for old, new in sorted(deprecated.items()):
        groups.setdefault(new, []).append(old)
    for new, olds in groups.items():
        w("            case {}".format(" ".join(_fish_quote(o) for o in olds)))
        w("                echo {}".format(new))
    known = [name for name in spec if name is not None]
    w("            case {}".format(" ".join(_fish_quote(k) for k in known)))
    w("                echo $token")
    w("            case '*'")
    w("                echo launcher")
    w("        end")
    w("        return")
    w("    end")
    w("end")
    w("")
    w("function __checkbox_cli_using")
    w("    set -l cmd (__checkbox_cli_cmd)")
    w('    test "$cmd" = "$argv[1]"')
    w("end")
    w("")
    w("function __checkbox_cli_dynamic")
    w("    set -l cmd (commandline -opc)[1]")
    w("    $cmd __complete $argv 2>/dev/null")
    w("end")
    w("")
    w("complete -c checkbox-cli -f")
    for name, cmd_spec in spec.items():
        cond = "-n {}".format(
            _fish_quote(
                "__checkbox_cli_using {}".format(_fish_quote(name or ""))
            )
        )
        prefix = "complete -c checkbox-cli {}".format(cond)
        for opts, takes_value, kind, choices in cmd_spec.options:
            line = "{} {}".format(prefix, _fish_option_flags(opts))
            if choices:
                line += " -x -a {}".format(
                    _fish_quote(" ".join(_fish_quote(c) for c in choices))
                )
            elif kind == FILE:
                line += " -r -F"
            elif takes_value:
                line += " -x"
            w(line)
        if cmd_spec.positional_choices:
            w(
                "{} -a {}".format(
                    prefix,
                    _fish_quote(
                        " ".join(
                            _fish_quote(c) for c in cmd_spec.positional_choices
                        )
                    ),
                )
            )
        if cmd_spec.positional_kind == FILE:
            w("{} -F".format(prefix))
        elif cmd_spec.positional_kind:
            w(
                "{} -a {}".format(
                    prefix,
                    _fish_quote(
                        "(__checkbox_cli_dynamic {})".format(
                            cmd_spec.positional_kind
                        )
                    ),
                )
            )
    for alias in COMMAND_NAMES[1:]:
        w("complete -c {} -w checkbox-cli".format(alias))
    return "\n".join(out) + "\n"


GENERATORS: Dict[str, Callable[[Spec, Mapping[str, str]], str]] = {
    "bash": generate_bash,
    "zsh": generate_zsh,
    "fish": generate_fish,
}


def generate(shell: str) -> str:
    # imported here to avoid a circular import with checkbox_cli
    from checkbox_ng.launcher.checkbox_cli import (
        DEPRECATED_COMMANDS,
        build_top_parser,
        get_commands,
    )

    commands = get_commands()
    spec = build_spec(build_top_parser(commands), commands)
    return GENERATORS[shell](spec, DEPRECATED_COMMANDS)


class Completion:
    def register_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "shell",
            choices=SHELLS,
            help=_("shell to print the completion script for"),
        )

    def invoked(self, ctx: "Context") -> None:
        print(generate(ctx.args.shell), end="")


def get_unit_ids(sa: SessionAssistant, kind: str) -> List[str]:
    groups = DYNAMIC_KINDS[kind]
    root = Explorer(sa.get_selected_providers()).get_object_tree()
    ids: Set[str] = set()
    to_visit = [root]
    while to_visit:
        obj = to_visit.pop()
        if obj.group in groups:
            ids.add(obj.name)
        to_visit.extend(obj.children)
    return sorted(ids)


class DynamicCompletion:
    """
    Print completion candidates that depend on the installed providers, one
    per line. Used by the generated completion scripts.
    """

    def register_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("kind", choices=sorted(DYNAMIC_KINDS))

    def invoked(self, ctx: "Context") -> int:
        try:
            ids = get_unit_ids(ctx.sa, ctx.args.kind)
        except Exception:
            # a broken provider must never break the user's shell
            return 0
        for unit_id in ids:
            print(unit_id)
        return 0
