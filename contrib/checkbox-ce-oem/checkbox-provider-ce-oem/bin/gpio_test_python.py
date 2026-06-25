#!/usr/bin/env python3
"""GPIO validation using the Python gpiod binding."""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

CONSUMER = "gpio-test"


@dataclass(frozen=True)
class GpioLine:
    chip: str
    offset: int
    name: str
    used: bool
    direction: str | None
    active_low: bool


@dataclass(frozen=True)
class TestState:
    gpiod: object
    style: str
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


def print_result(status: str) -> None:
    upper = status.upper()
    print()
    print(f"RESULT: {upper}")
    print(f"GPIO_TEST_RESULT={status}")


def python_gpiod_error(action: str, line: str, exc: Exception) -> str:
    return (
        f"Python gpiod failed to {action} {line}: {exc} "
        "(kernel/libgpiod operation error)"
    )


def import_gpiod():
    try:
        import gpiod  # type: ignore
    except (
        Exception
    ) as exc:  # pragma: no cover - depends on target environment.
        raise GpioTestError(f"failed to import gpiod: {exc}") from exc
    return gpiod


def api_style(gpiod) -> str:
    if hasattr(gpiod, "request_lines") and hasattr(gpiod, "LineSettings"):
        return "v2"
    if hasattr(gpiod, "Chip"):
        return "v1"
    raise GpioTestError("unsupported Python gpiod API")


def gpiod_version(gpiod) -> str:
    for attr in ("__version__", "version"):
        value = getattr(gpiod, attr, None)
        if callable(value):
            value = value()
        if value:
            return str(value)
    return "unknown"


def chip_path(chip: str) -> str:
    path = Path("/dev") / chip
    return str(path) if path.exists() else chip


def chip_names() -> list[str]:
    names = [Path(path).name for path in glob.glob("/dev/gpiochip*")]
    return sorted(
        names,
        key=lambda item: (
            int(item.removeprefix("gpiochip"))
            if item.removeprefix("gpiochip").isdigit()
            else item
        ),
    )


def value_attr(obj, name: str):
    attr = getattr(obj, name, None)
    return attr() if callable(attr) else attr


def normalized_direction(direction) -> str | None:
    if direction is None:
        return None
    if isinstance(direction, int):
        return {1: "input", 2: "output"}.get(direction, str(direction))
    text = str(direction).lower()
    if "input" in text:
        return "input"
    if "output" in text:
        return "output"
    return text


def line_info_v1(gpiod, chip_name: str, offset: int) -> GpioLine:
    chip = gpiod.Chip(chip_name)
    try:
        line = chip.get_line(offset)
        name = value_attr(line, "name") or ""
        consumer = value_attr(line, "consumer")
        is_used = value_attr(line, "is_used")
        used = bool(is_used) if is_used is not None else bool(consumer)
        direction = normalized_direction(value_attr(line, "direction"))
        active_state = value_attr(line, "active_state")
        active_low = "low" in str(active_state).lower()
        return GpioLine(chip_name, offset, name, used, direction, active_low)
    finally:
        close = getattr(chip, "close", None)
        if callable(close):
            close()


def line_count_v1(gpiod, chip_name: str) -> int:
    chip = gpiod.Chip(chip_name)
    try:
        count = value_attr(chip, "num_lines")
        if count is None:
            raise GpioTestError(f"cannot determine line count for {chip_name}")
        return int(count)
    finally:
        close = getattr(chip, "close", None)
        if callable(close):
            close()


def line_info_v2(gpiod, chip_name: str, offset: int) -> GpioLine:
    chip = gpiod.Chip(chip_path(chip_name))
    try:
        info = chip.get_line_info(offset)
        name = value_attr(info, "name") or ""
        consumer = value_attr(info, "consumer")
        direction = normalized_direction(value_attr(info, "direction"))
        active_low = bool(value_attr(info, "active_low"))
        return GpioLine(
            chip_name, offset, name, bool(consumer), direction, active_low
        )
    finally:
        close = getattr(chip, "close", None)
        if callable(close):
            close()


def line_count_v2(gpiod, chip_name: str) -> int:
    chip = gpiod.Chip(chip_path(chip_name))
    try:
        info = chip.get_info()
        count = value_attr(info, "num_lines")
        if count is None:
            raise GpioTestError(f"cannot determine line count for {chip_name}")
        return int(count)
    finally:
        close = getattr(chip, "close", None)
        if callable(close):
            close()


def load_lines(chip: str | None = None) -> dict[str, GpioLine]:
    gpiod = import_gpiod()
    style = api_style(gpiod)
    names = [chip] if chip else chip_names()
    if not names:
        raise GpioTestError("no GPIO chips found under /dev")

    lines: dict[str, GpioLine] = {}
    for chip_name in names:
        count = (
            line_count_v2(gpiod, chip_name)
            if style == "v2"
            else line_count_v1(gpiod, chip_name)
        )
        for offset in range(count):
            line = (
                line_info_v2(gpiod, chip_name, offset)
                if style == "v2"
                else line_info_v1(gpiod, chip_name, offset)
            )
            lines[f"{line.chip}-{line.offset}"] = line
    return lines


def print_gpio_inventory(lines: dict[str, GpioLine]) -> None:
    by_chip: dict[str, list[GpioLine]] = {}
    for line in lines.values():
        by_chip.setdefault(line.chip, []).append(line)

    for chip in sorted(
        by_chip, key=lambda item: int(item.removeprefix("gpiochip"))
    ):
        chip_lines = sorted(by_chip[chip], key=lambda line: line.offset)
        print(f"       {chip} - {len(chip_lines)} lines:")
        for line in chip_lines:
            name = f'"{line.name}"' if line.name else "unnamed"
            used = "used" if line.used else "unused"
            direction = line.direction or "unknown"
            active = "active-low" if line.active_low else "active-high"
            print(
                f"         line {line.offset:3}: {name:18} {used:6} {direction:7} {active}"
            )


def initialize_test_state() -> TestState:
    print_step("Get Python gpiod version")
    gpiod = import_gpiod()
    style = api_style(gpiod)
    print_detail("python-gpiod-version", gpiod_version(gpiod))
    print_detail("python-gpiod-api", style)

    print_step("List all GPIO chips and lines")
    lines = load_lines()
    print_gpio_inventory(lines)
    return TestState(gpiod=gpiod, style=style, lines=lines)


def parse_line_id(identifier: str) -> tuple[str, int]:
    parts = identifier.strip().split("-", 1)
    if (
        len(parts) != 2
        or not parts[0].startswith("gpiochip")
        or not parts[1].isdigit()
    ):
        raise GpioTestError(f"invalid GPIO line identifier: {identifier}")
    return parts[0], int(parts[1])


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


def sort_key(identifier: str) -> tuple[int, int]:
    chip, offset = identifier.split("-", 1)
    return int(chip.removeprefix("gpiochip")), int(offset)


def resource_simple(args: argparse.Namespace) -> int:
    lines = load_lines()
    ignored = parse_ignore(args.ignore, lines)
    candidates = []
    for key in sorted(lines, key=sort_key):
        line = lines[key]
        if line.used or key in ignored:
            continue
        candidates.append({"GPIO_CHIP": line.chip, "GPIO_LINE": line.offset})
    emit_records(candidates, args.format)
    return 0


def resource_loopback(args: argparse.Namespace) -> int:
    lines = load_lines()
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
    lines = load_lines(chip)
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


def request_input_v1(gpiod, chip_name: str, offset: int):
    chip = gpiod.Chip(chip_name)
    line = chip.get_line(offset)
    line.request(consumer=CONSUMER, type=gpiod.LINE_REQ_DIR_IN)
    return chip, line


def request_output_v1(gpiod, chip_name: str, offset: int, value: int):
    chip = gpiod.Chip(chip_name)
    line = chip.get_line(offset)
    line.request(
        consumer=CONSUMER, type=gpiod.LINE_REQ_DIR_OUT, default_vals=[value]
    )
    return chip, line


def release_v1(handle) -> None:
    chip, line = handle
    try:
        line.release()
    finally:
        close = getattr(chip, "close", None)
        if callable(close):
            close()


def request_input_v2(gpiod, chip_name: str, offset: int):
    settings = gpiod.LineSettings(direction=gpiod.line.Direction.INPUT)
    return gpiod.request_lines(
        chip_path(chip_name), consumer=CONSUMER, config={offset: settings}
    )


def request_output_v2(gpiod, chip_name: str, offset: int, value: int):
    output_value = (
        gpiod.line.Value.ACTIVE if value else gpiod.line.Value.INACTIVE
    )
    settings = gpiod.LineSettings(
        direction=gpiod.line.Direction.OUTPUT, output_value=output_value
    )
    return gpiod.request_lines(
        chip_path(chip_name), consumer=CONSUMER, config={offset: settings}
    )


def read_handle(gpiod, style: str, handle, offset: int) -> int:
    if style == "v2":
        value = handle.get_value(offset)
        return 1 if value == gpiod.line.Value.ACTIVE else 0
    return int(handle[1].get_value())


def set_handle_value(
    gpiod, style: str, handle, offset: int, value: int
) -> None:
    if style == "v2":
        output_value = (
            gpiod.line.Value.ACTIVE if value else gpiod.line.Value.INACTIVE
        )
        handle.set_value(offset, output_value)
        return
    handle[1].set_value(value)


def release_handle(style: str, handle) -> None:
    if style == "v2":
        handle.release()
    else:
        release_v1(handle)


def request_input(gpiod, style: str, chip_name: str, offset: int):
    return (
        request_input_v2(gpiod, chip_name, offset)
        if style == "v2"
        else request_input_v1(gpiod, chip_name, offset)
    )


def request_output(gpiod, style: str, chip_name: str, offset: int, value: int):
    return (
        request_output_v2(gpiod, chip_name, offset, value)
        if style == "v2"
        else request_output_v1(gpiod, chip_name, offset, value)
    )


def save_line_state(state: TestState, line: GpioLine) -> SavedLineState:
    value = None
    if line.direction == "output":
        handle = request_input(
            state.gpiod, state.style, line.chip, line.offset
        )
        try:
            value = read_handle(state.gpiod, state.style, handle, line.offset)
        finally:
            release_handle(state.style, handle)
    return SavedLineState(line=line, value=value)


def restore_line_state(state: TestState, saved: SavedLineState) -> None:
    line = saved.line
    if line.direction == "input":
        handle = request_input(
            state.gpiod, state.style, line.chip, line.offset
        )
    elif line.direction == "output":
        handle = request_output(
            state.gpiod,
            state.style,
            line.chip,
            line.offset,
            saved.value if saved.value is not None else 0,
        )
    else:
        return
    release_handle(state.style, handle)


def recover_saved_states(
    state: TestState | None, states: list[SavedLineState]
) -> None:
    if state is None:
        return
    for saved in states:
        try:
            restore_line_state(state, saved)
        except Exception as exc:
            print(
                f"GPIO_RECOVERY_ERROR={saved.line.chip}-{saved.line.offset}: {exc}",
                file=sys.stderr,
            )


def test_simple_input(args: argparse.Namespace) -> int:
    handle = None
    try:
        print_test_header("GPIO simple input", f"{args.chip}-{args.line}")
        state = initialize_test_state()
        line = get_line_from_state_or_raise(state, args.chip, args.line)
        ensure_unused(line)
        step = print_step(f"Request {args.chip}-{args.line} as input")
        print_detail(
            "note", "Python gpiod API requests the line as input here"
        )
        try:
            handle = request_input(
                state.gpiod, state.style, args.chip, args.line
            )
        except Exception as exc:
            raise StepError(
                step,
                python_gpiod_error(
                    "request input", f"{args.chip}-{args.line}", exc
                ),
            ) from exc
        step = print_step(f"Read value from {args.chip}-{args.line}")
        try:
            value = read_handle(state.gpiod, state.style, handle, args.line)
        except Exception as exc:
            raise StepError(
                step,
                python_gpiod_error("read", f"{args.chip}-{args.line}", exc),
            ) from exc
        print_step(f"Release {args.chip}-{args.line}")
        release_handle(state.style, handle)
        handle = None
        print(f"GPIO_VALUE={value}")
        print_result("pass")
        return 0
    except Exception as exc:
        if handle is not None:
            try:
                release_handle(api_style(import_gpiod()), handle)
            except Exception:
                pass
        return fail_current_step(exc)


def test_simple_output(args: argparse.Namespace) -> int:
    handle = None
    state: TestState | None = None
    saved: SavedLineState | None = None
    try:
        print_test_header("GPIO simple output", f"{args.chip}-{args.line}")
        state = initialize_test_state()
        line = get_line_from_state_or_raise(state, args.chip, args.line)
        ensure_unused(line)
        print_step(f"Save original state for {args.chip}-{args.line}")
        saved = save_line_state(state, line)
        step = print_step(f"Request {args.chip}-{args.line} as output")
        print_detail(
            "note", "Python gpiod API requests the line as output here"
        )
        try:
            handle = request_output(
                state.gpiod,
                state.style,
                args.chip,
                args.line,
                int(args.initial or 0),
            )
        except Exception as exc:
            raise StepError(
                step,
                python_gpiod_error(
                    "request output", f"{args.chip}-{args.line}", exc
                ),
            ) from exc
        step = print_step(f"Set {args.chip}-{args.line} low")
        try:
            set_handle_value(state.gpiod, state.style, handle, args.line, 0)
        except Exception as exc:
            raise StepError(
                step,
                python_gpiod_error("set low", f"{args.chip}-{args.line}", exc),
            ) from exc
        step = print_step(f"Set {args.chip}-{args.line} high")
        try:
            set_handle_value(state.gpiod, state.style, handle, args.line, 1)
        except Exception as exc:
            raise StepError(
                step,
                python_gpiod_error(
                    "set high", f"{args.chip}-{args.line}", exc
                ),
            ) from exc
        print_step(f"Recover original state for {args.chip}-{args.line}")
        release_handle(state.style, handle)
        handle = None
        restore_line_state(state, saved)
        print_step(f"Release {args.chip}-{args.line}")
        print_result("pass")
        return 0
    except Exception as exc:
        if handle is not None:
            try:
                release_handle(api_style(import_gpiod()), handle)
            except Exception:
                pass
        if saved is not None:
            print_step(f"Recover original state for {args.chip}-{args.line}")
            recover_saved_states(state, [saved])
        return fail_current_step(exc)


def test_loopback(args: argparse.Namespace) -> int:
    out_handle = None
    in_handle = None
    state: TestState | None = None
    saved_states: list[SavedLineState] = []
    try:
        print_test_header(
            "GPIO loopback",
            f"input={args.in_chip}-{args.in_line} output={args.out_chip}-{args.out_line}",
        )
        state = initialize_test_state()
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
            save_line_state(state, output),
            save_line_state(state, input_),
        ]
        step = print_step(f"Request {args.out_chip}-{args.out_line} as output")
        print_detail("note", "Python gpiod API requests the output line here")
        try:
            out_handle = request_output(
                state.gpiod, state.style, args.out_chip, args.out_line, 0
            )
        except Exception as exc:
            raise StepError(
                step,
                python_gpiod_error(
                    "request output", f"{args.out_chip}-{args.out_line}", exc
                ),
            ) from exc
        step = print_step(f"Request {args.in_chip}-{args.in_line} as input")
        print_detail("note", "Python gpiod API requests the input line here")
        try:
            in_handle = request_input(
                state.gpiod, state.style, args.in_chip, args.in_line
            )
        except Exception as exc:
            raise StepError(
                step,
                python_gpiod_error(
                    "request input", f"{args.in_chip}-{args.in_line}", exc
                ),
            ) from exc

        for _ in range(args.repeat):
            step = print_step(f"Set {args.out_chip}-{args.out_line} low")
            try:
                set_handle_value(
                    state.gpiod, state.style, out_handle, args.out_line, 0
                )
            except Exception as exc:
                raise StepError(
                    step,
                    python_gpiod_error(
                        "set low", f"{args.out_chip}-{args.out_line}", exc
                    ),
                ) from exc
            time.sleep(args.delay)
            step = print_step(
                f"Verify {args.in_chip}-{args.in_line} reads low"
            )
            try:
                input_value = read_handle(
                    state.gpiod, state.style, in_handle, args.in_line
                )
            except Exception as exc:
                raise StepError(
                    step,
                    python_gpiod_error(
                        "read", f"{args.in_chip}-{args.in_line}", exc
                    ),
                ) from exc
            if input_value != 0:
                raise StepError(
                    f"Verify {args.in_chip}-{args.in_line} reads low",
                    "input did not read low",
                )

            step = print_step(f"Set {args.out_chip}-{args.out_line} high")
            try:
                set_handle_value(
                    state.gpiod, state.style, out_handle, args.out_line, 1
                )
            except Exception as exc:
                raise StepError(
                    step,
                    python_gpiod_error(
                        "set high", f"{args.out_chip}-{args.out_line}", exc
                    ),
                ) from exc
            time.sleep(args.delay)
            step = print_step(
                f"Verify {args.in_chip}-{args.in_line} reads high"
            )
            try:
                input_value = read_handle(
                    state.gpiod, state.style, in_handle, args.in_line
                )
            except Exception as exc:
                raise StepError(
                    step,
                    python_gpiod_error(
                        "read", f"{args.in_chip}-{args.in_line}", exc
                    ),
                ) from exc
            if input_value != 1:
                raise StepError(
                    f"Verify {args.in_chip}-{args.in_line} reads high",
                    "input did not read high",
                )

        print_step(
            f"Recover original state for {args.out_chip}-{args.out_line} and {args.in_chip}-{args.in_line}"
        )
        release_handle(state.style, out_handle)
        release_handle(state.style, in_handle)
        out_handle = None
        in_handle = None
        recover_saved_states(state, saved_states)
        print_step(
            f"Release {args.out_chip}-{args.out_line} and {args.in_chip}-{args.in_line}"
        )
        print_result("pass")
        return 0
    except Exception as exc:
        for handle in (out_handle, in_handle):
            if handle is not None:
                try:
                    release_handle(api_style(import_gpiod()), handle)
                except Exception:
                    pass
        if saved_states:
            print_step(
                f"Recover original state for {args.out_chip}-{args.out_line} and {args.in_chip}-{args.in_line}"
            )
            recover_saved_states(state, saved_states)
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
            "  gpio_test_python.py resource simple\n"
            "  gpio_test_python.py resource simple --ignore gpiochip0-2,gpiochip1-14\n"
            "  gpio_test_python.py resource simple --ignore gpiochip14,gpiochip16-0..4\n"
            "  gpio_test_python.py resource simple --ignore gpiochip14-*,gpiochip16-0..1,gpiochip16-2..4\n"
            "  gpio_test_python.py resource simple --allow-named --format json\n"
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
            "  gpio_test_python.py resource loopback --pairs gpiochip0-100:gpiochip0-0\n"
            "  gpio_test_python.py resource loopback --pairs gpiochip0-100:gpiochip0-0,gpiochip1-2:gpiochip1-1\n"
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
