#!/usr/bin/env python3
"""GPIO validation using libgpiod command-line tools."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass

CONSUMER = "gpio-test"
_DETECTED_MAJOR: int | None = None


@dataclass(frozen=True)
class GpioLine:
    chip: str
    offset: int
    name: str
    used: bool
    direction: str | None
    active_low: bool


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


@dataclass(frozen=True)
class TestState:
    major: int
    lines: dict[str, GpioLine]


@dataclass(frozen=True)
class SavedLineState:
    line: GpioLine
    value: int | None


class GpioTestError(Exception):
    pass


class StepError(GpioTestError):
    def __init__(self, step: str, message: str) -> None:
        super().__init__(message)
        self.step = step
        self.message = message


def print_step(message: str) -> str:
    print()
    print(f"[INFO] {message}")
    return message


def print_detail(key: str, value: object) -> None:
    print(f"       {key}: {value}")


def print_test_header(name: str, target: str) -> None:
    print(f"TEST: {name}")
    print(f"TARGET: {target}")


def print_block(label: str, content: str) -> None:
    if not content:
        return
    print(f"       {label}:")
    for line in content.rstrip().splitlines():
        print(f"         {line}")


def print_result(status: str) -> None:
    upper = status.upper()
    print()
    print(f"RESULT: {upper}")
    print(f"GPIO_TEST_RESULT={status}")


def print_command(command: list[str]) -> None:
    print_detail("command", " ".join(command))


def print_command_output(result: CommandResult) -> None:
    if not result.stdout and not result.stderr:
        return

    if result.stdout and result.stderr:
        print_block("stdout", result.stdout)
        print_block("stderr", result.stderr)
        return

    if result.stdout:
        print_block("output", result.stdout)
    elif result.stderr:
        print_block("output", result.stderr)


def run_command(command: list[str], log: bool = True) -> CommandResult:
    if log:
        print_command(command)
    proc = subprocess.run(command, text=True, capture_output=True, check=False)
    result = CommandResult(proc.stdout, proc.stderr, proc.returncode)
    if log:
        print_command_output(result)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise GpioTestError(
            detail or f"command failed with exit code {result.returncode}"
        )
    return result


def filter_gpioinfo_output(output: str, offsets: set[int]) -> str:
    if not offsets:
        return output

    filtered: list[str] = []
    include_current_chip = False
    for line in output.splitlines():
        if re.match(r"^gpiochip\d+\s+-\s+\d+\s+lines:", line):
            filtered.append(line)
            include_current_chip = True
            continue
        if not include_current_chip:
            continue
        match = re.match(r"\s*line\s+(\d+):", line)
        if match and int(match.group(1)) in offsets:
            filtered.append(line)
    return "\n".join(filtered)


def run_gpioinfo(
    command: list[str], log: bool, focus_offsets: set[int] | None = None
) -> CommandResult:
    if not log:
        return run_command(command, log=False)

    print_command(command)
    proc = subprocess.run(command, text=True, capture_output=True, check=False)
    result = CommandResult(proc.stdout, proc.stderr, proc.returncode)
    display_stdout = filter_gpioinfo_output(
        result.stdout, focus_offsets or set()
    )
    print_command_output(
        CommandResult(display_stdout, result.stderr, result.returncode)
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise GpioTestError(
            detail or f"command failed with exit code {result.returncode}"
        )
    return result


def detect_major_version(log: bool = True) -> int:
    global _DETECTED_MAJOR
    if _DETECTED_MAJOR is not None:
        return _DETECTED_MAJOR

    if not shutil.which("gpioinfo"):
        raise GpioTestError("gpioinfo command not found")

    result = run_command(["gpioinfo", "-v"], log=log)
    match = re.search(r"v(\d+)\.", result.stdout + result.stderr)
    if not match:
        raise GpioTestError(
            "unable to detect libgpiod version from gpioinfo -v"
        )
    major = int(match.group(1))
    if major not in (1, 2):
        raise GpioTestError(f"unsupported libgpiod major version: {major}")
    _DETECTED_MAJOR = major
    return major


def require_commands() -> None:
    missing = [
        cmd
        for cmd in ("gpiodetect", "gpioinfo", "gpioget", "gpioset")
        if not shutil.which(cmd)
    ]
    if missing:
        raise GpioTestError(
            f"missing required command(s): {', '.join(missing)}"
        )


def parse_line(chip: str, line: str, major: int) -> GpioLine | None:
    match = re.match(r"\s*line\s+(\d+):\s*(.*)$", line)
    if not match:
        return None

    offset = int(match.group(1))
    details = match.group(2)
    quoted = re.findall(r'"([^"]*)"', details)

    if major == 1:
        if quoted:
            name = quoted[0]
        elif re.search(r"\bunnamed\b", details):
            name = ""
        else:
            name = ""
        used = not bool(re.search(r"\bunused\b", details))
    else:
        name = quoted[0] if quoted else ""
        used = 'consumer="' in details

    direction_match = re.search(r"\b(input|output)\b", details)
    direction = direction_match.group(1) if direction_match else None
    active_low = "active-low" in details or "active_low" in details
    return GpioLine(chip, offset, name, used, direction, active_low)


def parse_gpioinfo(output: str, major: int) -> dict[str, GpioLine]:
    lines: dict[str, GpioLine] = {}
    chip: str | None = None
    for raw_line in output.splitlines():
        header = re.match(r"^(gpiochip\d+)\s+-\s+\d+\s+lines:", raw_line)
        if header:
            chip = header.group(1)
            continue
        if chip is None:
            continue
        parsed = parse_line(chip, raw_line, major)
        if parsed is not None:
            lines[f"{parsed.chip}-{parsed.offset}"] = parsed
    return lines


def load_lines(
    chip: str | None = None,
    log: bool = True,
    focus_offsets: set[int] | None = None,
) -> dict[str, GpioLine]:
    require_commands()
    major = detect_major_version(log=log)
    command = ["gpioinfo"]
    if chip:
        if major == 2:
            command.extend(["--chip", chip])
        else:
            command.append(chip)
    result = run_gpioinfo(command, log=log, focus_offsets=focus_offsets)
    return parse_gpioinfo(result.stdout, major)


def initialize_test_state() -> TestState:
    require_commands()
    print_step("Get libgpiod version")
    major = detect_major_version(log=True)
    print_step("List all GPIO chips and lines")
    result = run_gpioinfo(["gpioinfo"], log=True)
    return TestState(major=major, lines=parse_gpioinfo(result.stdout, major))


def parse_line_id(identifier: str) -> tuple[str, int]:
    match = re.fullmatch(r"(gpiochip\d+)-(\d+)", identifier.strip())
    if not match:
        raise GpioTestError(f"invalid GPIO line identifier: {identifier}")
    return match.group(1), int(match.group(2))


def parse_ignore(value: str | None, lines: dict[str, GpioLine]) -> set[str]:
    if not value:
        return set()

    ignored: set[str] = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue

        chip_match = re.fullmatch(r"(gpiochip\d+)(?:-\*)?", item)
        if chip_match:
            chip = chip_match.group(1)
            ignored.update(
                key for key, line in lines.items() if line.chip == chip
            )
            continue

        range_match = re.fullmatch(r"(gpiochip\d+)-(\d+)\.\.(\d+)", item)
        if range_match:
            chip = range_match.group(1)
            start = int(range_match.group(2))
            end = int(range_match.group(3))
            if start > end:
                raise GpioTestError(f"invalid ignore range: {item}")
            ignored.update(
                f"{chip}-{offset}" for offset in range(start, end + 1)
            )
            continue

        chip, offset = parse_line_id(item)
        ignored.add(f"{chip}-{offset}")
    return ignored


def parse_pairs(value: str) -> list[tuple[str, int, str, int]]:
    pairs = []
    for item in value.split(","):
        if ":" not in item:
            raise GpioTestError(f"invalid loopback pair: {item}")
        input_, output = item.split(":", 1)
        in_chip, in_line = parse_line_id(input_)
        out_chip, out_line = parse_line_id(output)
        pairs.append((out_chip, out_line, in_chip, in_line))
    return pairs


def emit_records(records: list[dict[str, object]], fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(records, indent=2, sort_keys=True))
        return
    for record in records:
        for key, value in record.items():
            print(f"{key}={value}")
        print()


def resource_simple(args: argparse.Namespace) -> int:
    lines = load_lines(log=False)
    ignored = parse_ignore(args.ignore, lines)
    candidates = []
    for key in sorted(
        lines,
        key=lambda item: (
            int(item.split("-")[0].removeprefix("gpiochip")),
            int(item.split("-")[1]),
        ),
    ):
        line = lines[key]
        if line.used or key in ignored:
            continue
        candidates.append({"GPIO_CHIP": line.chip, "GPIO_LINE": line.offset})
    emit_records(candidates, args.format)
    return 0


def resource_loopback(args: argparse.Namespace) -> int:
    lines = load_lines(log=False)
    records = []
    for out_chip, out_line, in_chip, in_line in parse_pairs(args.pairs):
        out_key = f"{out_chip}-{out_line}"
        in_key = f"{in_chip}-{in_line}"
        if out_key == in_key:
            raise GpioTestError(
                f"loopback output and input are the same line: {out_key}"
            )
        if out_key not in lines:
            raise GpioTestError(f"output line not found: {out_key}")
        if in_key not in lines:
            raise GpioTestError(f"input line not found: {in_key}")
        if lines[out_key].used:
            raise GpioTestError(f"output line is already used: {out_key}")
        if lines[in_key].used:
            raise GpioTestError(f"input line is already used: {in_key}")
        records.append(
            {
                "GPIO_OUTPUT_CHIP": out_chip,
                "GPIO_OUTPUT_LINE": out_line,
                "GPIO_INPUT_CHIP": in_chip,
                "GPIO_INPUT_LINE": in_line,
            }
        )
    emit_records(records, args.format)
    return 0


def get_line_or_raise(chip: str, offset: int, purpose: str = "") -> GpioLine:
    label = f"{chip}-{offset}"
    print_step(f"Find {purpose + ' ' if purpose else ''}{label}")
    lines = load_lines(chip, log=True, focus_offsets={offset})
    if label not in lines:
        raise StepError(f"Find {label}", f"GPIO line not found: {label}")
    return lines[label]


def get_line_from_state_or_raise(
    state: TestState,
    chip: str,
    offset: int,
    purpose: str = "",
) -> GpioLine:
    label = f"{chip}-{offset}"
    print_step(f"Find {purpose + ' ' if purpose else ''}{label}")
    if label not in state.lines:
        raise StepError(f"Find {label}", f"GPIO line not found: {label}")
    return state.lines[label]


def get_loopback_lines_or_raise(
    args: argparse.Namespace, state: TestState
) -> tuple[GpioLine, GpioLine]:
    out_label = f"{args.out_chip}-{args.out_line}"
    in_label = f"{args.in_chip}-{args.in_line}"

    print_step(f"Find input {in_label}")
    print_step(f"Find output {out_label}")

    if out_label not in state.lines:
        raise StepError(
            f"Find output {out_label}", f"GPIO line not found: {out_label}"
        )
    if in_label not in state.lines:
        raise StepError(
            f"Find input {in_label}", f"GPIO line not found: {in_label}"
        )
    return state.lines[out_label], state.lines[in_label]


def ensure_unused(line: GpioLine) -> None:
    step = print_step(f"Check {line.chip}-{line.offset} is unused")
    if line.used:
        raise StepError(
            step, f"GPIO line is already used: {line.chip}-{line.offset}"
        )


def cmd_gpioget(chip: str, offset: int, major: int) -> list[str]:
    if major == 2:
        return ["gpioget", "--numeric", "--chip", chip, str(offset)]
    return ["gpioget", chip, str(offset)]


def cmd_gpioset(chip: str, offset: int, value: int, major: int) -> list[str]:
    if major == 2:
        return [
            "gpioset",
            "--toggle",
            "0",
            "--chip",
            chip,
            f"{offset}={value}",
        ]
    return ["gpioset", chip, f"{offset}={value}"]


def read_value(chip: str, offset: int, major: int) -> int:
    result = run_command(cmd_gpioget(chip, offset, major))
    output = result.stdout.strip()
    if output not in ("0", "1"):
        raise GpioTestError(f"unexpected GPIO value: {output!r}")
    return int(output)


def set_value(chip: str, offset: int, value: int, major: int) -> None:
    run_command(cmd_gpioset(chip, offset, value, major))


def save_line_state(line: GpioLine, major: int) -> SavedLineState:
    value = (
        read_value(line.chip, line.offset, major)
        if line.direction == "output"
        else None
    )
    return SavedLineState(line=line, value=value)


def restore_line_state(saved: SavedLineState, major: int) -> None:
    line = saved.line
    if line.direction == "input":
        read_value(line.chip, line.offset, major)
    elif line.direction == "output":
        set_value(
            line.chip,
            line.offset,
            saved.value if saved.value is not None else 0,
            major,
        )


def recover_saved_states(
    states: list[SavedLineState], major: int | None
) -> None:
    if major is None:
        return
    for saved in states:
        try:
            restore_line_state(saved, major)
        except Exception as exc:
            print(
                f"GPIO_RECOVERY_ERROR={saved.line.chip}-{saved.line.offset}: {exc}",
                file=sys.stderr,
            )


def cmd_gpioset_hold(
    chip: str, offset: int, value: int, major: int
) -> list[str]:
    if major == 2:
        return ["gpioset", "--chip", chip, f"{offset}={value}"]
    return ["gpioset", "--mode=signal", chip, f"{offset}={value}"]


def start_held_value(
    chip: str, offset: int, value: int, major: int
) -> subprocess.Popen[str]:
    command = cmd_gpioset_hold(chip, offset, value, major)
    print_command(command)
    proc = subprocess.Popen(
        command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    time.sleep(0.05)
    if proc.poll() is not None:
        stdout, stderr = proc.communicate()
        print_command_output(
            CommandResult(stdout, stderr, proc.returncode or 1)
        )
        detail = (stderr or stdout).strip()
        raise GpioTestError(
            detail or f"command failed with exit code {proc.returncode}"
        )
    return proc


def stop_held_value(proc: subprocess.Popen[str]) -> None:
    proc.send_signal(signal.SIGTERM)
    try:
        stdout, stderr = proc.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
    print_command_output(CommandResult(stdout, stderr, proc.returncode or 0))


def release_line(chip: str, offset: int) -> None:
    print_step(f"Release {chip}-{offset}")


def test_simple_input(args: argparse.Namespace) -> int:
    try:
        print_test_header("GPIO simple input", f"{args.chip}-{args.line}")
        state = initialize_test_state()
        line = get_line_from_state_or_raise(state, args.chip, args.line)
        ensure_unused(line)
        print_step(f"Request {args.chip}-{args.line} as input")
        print_detail(
            "note",
            "gpioget requests the line as input when the read command runs",
        )
        print_step(f"Read value from {args.chip}-{args.line}")
        value = read_value(args.chip, args.line, state.major)
        release_line(args.chip, args.line)
        print(f"GPIO_VALUE={value}")
        print_result("pass")
        return 0
    except Exception as exc:
        return fail_current_step(exc)


def test_simple_output(args: argparse.Namespace) -> int:
    saved: SavedLineState | None = None
    major: int | None = None
    try:
        print_test_header("GPIO simple output", f"{args.chip}-{args.line}")
        state = initialize_test_state()
        major = state.major
        line = get_line_from_state_or_raise(state, args.chip, args.line)
        ensure_unused(line)
        print_step(f"Save original state for {args.chip}-{args.line}")
        saved = save_line_state(line, state.major)
        print_step(f"Request {args.chip}-{args.line} as output")
        print_detail(
            "note",
            "gpioset requests the line as output when the set command runs",
        )
        print_step(f"Set {args.chip}-{args.line} low")
        set_value(args.chip, args.line, 0, state.major)
        print_step(f"Set {args.chip}-{args.line} high")
        set_value(args.chip, args.line, 1, state.major)
        print_step(f"Recover original state for {args.chip}-{args.line}")
        restore_line_state(saved, state.major)
        release_line(args.chip, args.line)
        print_result("pass")
        return 0
    except Exception as exc:
        if saved is not None:
            print_step(f"Recover original state for {args.chip}-{args.line}")
            recover_saved_states([saved], major)
        return fail_current_step(exc)


def test_loopback(args: argparse.Namespace) -> int:
    saved_states: list[SavedLineState] = []
    major: int | None = None
    try:
        print_test_header(
            "GPIO loopback",
            f"input={args.in_chip}-{args.in_line} output={args.out_chip}-{args.out_line}",
        )
        state = initialize_test_state()
        major = state.major
        output, input_ = get_loopback_lines_or_raise(args, state)
        if (args.out_chip, args.out_line) == (args.in_chip, args.in_line):
            raise StepError(
                "Check loopback lines", "output and input line are the same"
            )

        step = print_step(
            f"Check {args.out_chip}-{args.out_line} and {args.in_chip}-{args.in_line} are unused"
        )
        if output.used or input_.used:
            raise StepError(
                step, "one or both loopback lines are already used"
            )

        print_step(
            f"Save original state for {args.out_chip}-{args.out_line} and {args.in_chip}-{args.in_line}"
        )
        saved_states = [
            save_line_state(output, state.major),
            save_line_state(input_, state.major),
        ]
        print_step(f"Request {args.out_chip}-{args.out_line} as output")
        print_detail(
            "note",
            "gpioset requests and holds the output line while verification runs",
        )
        print_step(f"Request {args.in_chip}-{args.in_line} as input")
        print_detail(
            "note",
            "gpioget requests the input line when each read command runs",
        )

        held: subprocess.Popen[str] | None = None
        for _ in range(args.repeat):
            print_step(f"Set {args.out_chip}-{args.out_line} low")
            held = start_held_value(
                args.out_chip, args.out_line, 0, state.major
            )
            try:
                time.sleep(args.delay)
                print_step(f"Verify {args.in_chip}-{args.in_line} reads low")
                if read_value(args.in_chip, args.in_line, state.major) != 0:
                    raise StepError(
                        f"Verify {args.in_chip}-{args.in_line} reads low",
                        "input did not read low",
                    )
            finally:
                stop_held_value(held)
                held = None

            print_step(f"Set {args.out_chip}-{args.out_line} high")
            held = start_held_value(
                args.out_chip, args.out_line, 1, state.major
            )
            try:
                time.sleep(args.delay)
                print_step(f"Verify {args.in_chip}-{args.in_line} reads high")
                if read_value(args.in_chip, args.in_line, state.major) != 1:
                    raise StepError(
                        f"Verify {args.in_chip}-{args.in_line} reads high",
                        "input did not read high",
                    )
            finally:
                stop_held_value(held)
                held = None

        print_step(
            f"Recover original state for {args.out_chip}-{args.out_line} and {args.in_chip}-{args.in_line}"
        )
        recover_saved_states(saved_states, state.major)
        print_step(
            f"Release {args.out_chip}-{args.out_line} and {args.in_chip}-{args.in_line}"
        )
        print_result("pass")
        return 0
    except Exception as exc:
        if saved_states:
            print_step(
                f"Recover original state for {args.out_chip}-{args.out_line} and {args.in_chip}-{args.in_line}"
            )
            recover_saved_states(saved_states, major)
        return fail_current_step(exc)


def fail_current_step(exc: Exception) -> int:
    if isinstance(exc, StepError):
        print()
        print(f"[FAIL] {exc.step}")
        print_detail("error", exc.message)
        print(f"GPIO_ERROR={exc.message}", file=sys.stderr)
    else:
        print()
        print("[FAIL] GPIO test failed")
        print_detail("error", exc)
        print(f"GPIO_ERROR={exc}", file=sys.stderr)
    print_result("fail")
    return 1


def build_parser() -> argparse.ArgumentParser:
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=formatter
    )
    subparsers = parser.add_subparsers(dest="category", required=True)

    resource = subparsers.add_parser("resource", formatter_class=formatter)
    resource_sub = resource.add_subparsers(
        dest="resource_command", required=True
    )
    simple_resource = resource_sub.add_parser(
        "simple",
        formatter_class=formatter,
        epilog=(
            "Examples:\n"
            "  gpio_test_subprocess.py resource simple\n"
            "  gpio_test_subprocess.py resource simple --ignore gpiochip0-2,gpiochip1-14\n"
            "  gpio_test_subprocess.py resource simple --ignore gpiochip14,gpiochip16-0..4\n"
            "  gpio_test_subprocess.py resource simple --ignore gpiochip14-*,gpiochip16-0..1,gpiochip16-2..4\n"
            "  gpio_test_subprocess.py resource simple --allow-named --format json\n"
        ),
    )
    simple_resource.add_argument(
        "--ignore",
        metavar="IDS",
        help=(
            "Comma-separated GPIO lines, ranges, or chips to exclude. Supports "
            "gpiochipN-LINE, gpiochipN-START..END, gpiochipN, and gpiochipN-*. "
            "Examples: gpiochip0-2,gpiochip14,gpiochip16-0..4."
        ),
    )
    simple_resource.add_argument(
        "--allow-named",
        action="store_true",
        help=(
            "Compatibility option. Named unused GPIO lines are included by "
            "default; use --ignore to exclude unsafe platform lines."
        ),
    )
    simple_resource.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format. Default: text.",
    )
    simple_resource.set_defaults(func=resource_simple)

    loopback_resource = resource_sub.add_parser(
        "loopback",
        formatter_class=formatter,
        epilog=(
            "Examples:\n"
            "  gpio_test_subprocess.py resource loopback --pairs gpiochip0-100:gpiochip0-0\n"
            "  gpio_test_subprocess.py resource loopback --pairs gpiochip0-100:gpiochip0-0,gpiochip1-2:gpiochip1-1\n"
            "\n"
            "Pair format is INPUT:OUTPUT.\n"
        ),
    )
    loopback_resource.add_argument(
        "--pairs",
        required=True,
        help="Comma-separated loopback pairs in INPUT:OUTPUT format.",
    )
    loopback_resource.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format. Default: text.",
    )
    loopback_resource.set_defaults(func=resource_loopback)

    test = subparsers.add_parser("test", formatter_class=formatter)
    test_sub = test.add_subparsers(dest="test_command", required=True)
    simple_test = test_sub.add_parser("simple", formatter_class=formatter)
    simple_test_sub = simple_test.add_subparsers(
        dest="direction", required=True
    )

    input_test = simple_test_sub.add_parser("input")
    input_test.add_argument("chip")
    input_test.add_argument("line", type=int)
    input_test.add_argument(
        "--bias", choices=("pull-up", "pull-down", "disabled")
    )
    input_test.set_defaults(func=test_simple_input)

    output_test = simple_test_sub.add_parser("output")
    output_test.add_argument("chip")
    output_test.add_argument("line", type=int)
    output_test.add_argument("--initial", choices=("0", "1"))
    output_test.set_defaults(func=test_simple_output)

    loopback_test = test_sub.add_parser("loopback")
    loopback_test.add_argument("in_chip")
    loopback_test.add_argument("in_line", type=int)
    loopback_test.add_argument("out_chip")
    loopback_test.add_argument("out_line", type=int)
    loopback_test.add_argument("--repeat", type=int, default=3)
    loopback_test.add_argument("--delay", type=float, default=0.05)
    loopback_test.set_defaults(func=test_loopback)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except GpioTestError as exc:
        print(f"GPIO_ERROR={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
