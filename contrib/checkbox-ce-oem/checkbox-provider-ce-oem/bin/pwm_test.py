#!/usr/bin/env python3
"""Discover and validate Linux PWM sysfs devices."""

from __future__ import annotations

import argparse
import errno
import glob
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path


DEBUGFS_PWM = Path("/sys/kernel/debug/pwm")
SYSFS_PWM = Path("/sys/class/pwm")
TEST_PERIOD = "1000000"
TEST_DUTY_CYCLE = "500000"
EXPORT_WAIT_ATTEMPTS = 20
EXPORT_WAIT_SECONDS = 0.05


class PwmError(Exception):
    """Expected user-facing PWM error."""


@dataclass(frozen=True)
class PwmOutput:
    """PWM output parsed from `/sys/kernel/debug/pwm`."""

    chip_name: str
    pwm_name: str
    consumer: str | None
    requested: bool
    enabled: bool
    period: int | None
    duty: int | None
    polarity: str | None

    @property
    def chip_basename(self) -> str:
        """Return the stable basename used by sysfs device symlink targets."""
        return self.chip_name.rsplit("/", 1)[-1]

    @property
    def consumer_label(self) -> str:
        """Return the resource output label for an undefined consumer."""
        return self.consumer if self.consumer is not None else "NotDefined"


@dataclass(frozen=True)
class TestValues:
    """Period and duty-cycle values used by the test command."""

    period: str
    duty_cycle: str


@dataclass(frozen=True)
class PwmPaths:
    """Runtime sysfs paths for one selected PWM output."""

    pwmchip: Path
    pwm: Path
    pwm_sysfs_name: str

    @property
    def enable(self) -> Path:
        """Return the sysfs enable file path."""
        return self.pwm / "enable"

    @property
    def period(self) -> Path:
        """Return the sysfs period file path."""
        return self.pwm / "period"

    @property
    def duty_cycle(self) -> Path:
        """Return the sysfs duty_cycle file path."""
        return self.pwm / "duty_cycle"

    @property
    def polarity(self) -> Path:
        """Return the sysfs polarity file path."""
        return self.pwm / "polarity"

    @property
    def export(self) -> Path:
        """Return the sysfs export file path."""
        return self.pwmchip / "export"

    @property
    def unexport(self) -> Path:
        """Return the sysfs unexport file path."""
        return self.pwmchip / "unexport"


@dataclass
class OriginalState:
    """Original PWM state captured before test writes."""

    exported: bool
    period: str | None = None
    duty_cycle: str | None = None
    polarity: str | None = None
    enable: str | None = None


class DebugfsPwmParser:
    """Parse Linux debugfs PWM controller and output records."""

    CONTROLLER_RE = re.compile(
        r"^\s*(?:\d+:\s*)?(?P<name>[^,]+),\s+\d+\s+PWM devices?\s*$"
    )
    PWM_RE = re.compile(
        r"^\s*(?P<pwm>pwm-\d+)\s+\((?P<consumer>.*)\):\s*(?P<state>.*)$"
    )

    def parse(self, text: str) -> list[PwmOutput]:
        """Parse debugfs text into PWM outputs.

        Args:
            text: Raw contents of `/sys/kernel/debug/pwm`.

        Returns:
            Parsed PWM output records.
        """
        outputs: list[PwmOutput] = []
        current_chip: str | None = None

        for line in text.splitlines():
            controller_match = self.CONTROLLER_RE.match(line)
            if controller_match:
                current_chip = controller_match.group("name").strip()
                continue

            pwm_match = self.PWM_RE.match(line)
            if not pwm_match or current_chip is None:
                continue

            outputs.append(self._parse_output(current_chip, pwm_match))

        return outputs

    def _parse_output(
        self,
        chip_name: str,
        match: re.Match[str],
    ) -> PwmOutput:
        state = match.group("state")
        period_match = re.search(r"period:\s*(\d+)\s+ns", state)
        duty_match = re.search(r"duty:\s*(\d+)\s+ns", state)
        polarity_match = re.search(r"polarity:\s*(\S+)", state)
        state_words = state.split()

        return PwmOutput(
            chip_name=chip_name,
            pwm_name=match.group("pwm"),
            consumer=normalize_consumer(match.group("consumer")),
            requested="requested" in state_words,
            enabled="enabled" in state_words,
            period=int(period_match.group(1)) if period_match else None,
            duty=int(duty_match.group(1)) if duty_match else None,
            polarity=polarity_match.group(1) if polarity_match else None,
        )


class StepLogger:
    """Print test step logs in the documented block-style format."""

    def step(
        self,
        title: str,
        fields: list[tuple[str, object]],
        result: str,
        error: str | None = None,
    ) -> None:
        """Print one step block.

        Args:
            title: Step title shown after `STEP:`.
            fields: Ordered key/value fields to print.
            result: Step result string, usually `PASS`, `FAIL`, or `SKIP`.
            error: Optional error text to include.
        """
        print(f"STEP: {title}")
        for key, value in fields:
            print(f"  {key}: {value}")
        print(f"  result: {result}")
        if error:
            print(f"  error: {error}")
        print()


class PwmSysfs:
    """Read debugfs and operate on PWM sysfs files."""

    def __init__(
        self,
        debugfs_pwm: Path = DEBUGFS_PWM,
        sysfs_pwm: Path = SYSFS_PWM,
        parser: DebugfsPwmParser | None = None,
    ) -> None:
        """Create a PWM sysfs gateway.

        Args:
            debugfs_pwm: Path to the debugfs PWM listing.
            sysfs_pwm: Root path for PWM sysfs chips.
            parser: Optional parser implementation.
        """
        self.debugfs_pwm = debugfs_pwm
        self.sysfs_pwm = sysfs_pwm
        self.parser = parser or DebugfsPwmParser()

    def read_outputs(self) -> list[PwmOutput]:
        """Read and parse all PWM outputs from debugfs."""
        try:
            text = self.debugfs_pwm.read_text(encoding="utf-8")
        except OSError as exc:
            raise PwmError(f"cannot read {self.debugfs_pwm}: {exc}") from exc

        outputs = self.parser.parse(text)
        if not outputs:
            raise PwmError(f"no PWM outputs found in {self.debugfs_pwm}")
        return outputs

    def resolve_pwmchip_path(self, output: PwmOutput) -> Path:
        """Map a stable debugfs chip name to the current sysfs pwmchip path."""
        device_glob = str(self.sysfs_pwm / "pwmchip*" / "device")
        for device_link in glob.glob(device_glob):
            link_path = Path(device_link)
            try:
                target_basename = os.path.basename(os.readlink(link_path))
            except OSError:
                continue
            if target_basename == output.chip_basename:
                return link_path.parent
        raise PwmError(
            f"cannot map {output.chip_name} to a current "
            f"{self.sysfs_pwm}/pwmchip* node"
        )

    def read_file(self, path: Path) -> str:
        """Read a sysfs file and strip trailing whitespace."""
        return path.read_text(encoding="utf-8").strip()

    def write_file(self, path: Path, value: str) -> None:
        """Write a newline-terminated value to a sysfs file."""
        path.write_text(f"{value}\n", encoding="utf-8")

    def wait_for_path(self, path: Path) -> None:
        """Wait briefly for an exported PWM path to appear."""
        for _ in range(EXPORT_WAIT_ATTEMPTS):
            if path.exists():
                return
            time.sleep(EXPORT_WAIT_SECONDS)
        raise PwmError(f"timed out waiting for {path}")


class ResourceCommand:
    """Implement the `resource` subcommand."""

    def __init__(self, pwm: PwmSysfs) -> None:
        """Create a resource command.

        Args:
            pwm: Gateway used to read debugfs PWM output data.
        """
        self.pwm = pwm

    def run(self, ignore_raw: str | None, allow_raw: str | None) -> int:
        """Print eligible PWM resources.

        Args:
            ignore_raw: Comma-separated controller or consumer names to skip.
            allow_raw: Comma-separated controller or consumer names to include.

        Returns:
            Process exit code.
        """
        outputs = self.pwm.read_outputs()
        ignore = parse_csv(ignore_raw)
        allow = parse_csv(allow_raw)
        selected = [
            output
            for output in outputs
            if self._is_selected(output, ignore, allow)
        ]

        if not selected:
            raise PwmError("no eligible PWM outputs found")

        for index, output in enumerate(selected):
            if index:
                print()
            print(f"PWM_CHIP_NAME: {output.chip_name}")
            print(f"PWM_NAME: {output.pwm_name}")
            print(f"PWM_ID: {make_resource_id(output)}")
            print(f"Consumer: {output.consumer_label}")

        return 0

    def _is_selected(
        self,
        output: PwmOutput,
        ignore: set[str],
        allow: set[str],
    ) -> bool:
        if is_ignored(output, ignore):
            return False
        return output.consumer is None or is_allowed(output, allow)


class PwmRestorer:
    """Restore PWM state after a test attempt."""

    def __init__(self, pwm: PwmSysfs, logger: StepLogger) -> None:
        """Create a restorer.

        Args:
            pwm: Sysfs gateway used for file I/O.
            logger: Logger for restore step output.
        """
        self.pwm = pwm
        self.logger = logger

    def restore(
        self,
        paths: PwmPaths,
        pwm_index: int,
        state: OriginalState,
    ) -> list[str]:
        """Restore the captured state and return restore failures."""
        failures: list[str] = []

        if paths.enable.exists():
            self._restore_value(
                paths.enable,
                "0",
                "Disable PWM for restore",
                failures,
            )

        self._restore_value(
            paths.polarity,
            state.polarity,
            "Restore polarity",
            failures,
        )
        self._lower_duty_before_period(paths, state, failures)
        self._restore_value(
            paths.duty_cycle,
            state.duty_cycle,
            "Restore duty_cycle",
            failures,
        )
        self._restore_period(paths, state, failures)

        if state.exported:
            self._restore_value(
                paths.enable,
                state.enable,
                "Restore enable",
                failures,
            )
        else:
            self._unexport(paths, pwm_index, failures)

        return failures

    def _restore_value(
        self,
        path: Path,
        value: str | None,
        title: str,
        failures: list[str],
    ) -> None:
        if value is None or not path.exists():
            return
        try:
            current = self.pwm.read_file(path)
            if current == value:
                self.logger.step(
                    title,
                    [
                        ("path", path),
                        ("value", value),
                        ("action", "skip unchanged"),
                    ],
                    "PASS",
                )
                return
            self.pwm.write_file(path, value)
            self.logger.step(title, [("path", path), ("value", value)], "PASS")
        except OSError as exc:
            message = str(exc)
            failures.append(f"{path}: {message}")
            self.logger.step(
                title,
                [("path", path), ("value", value)],
                "FAIL",
                message,
            )

    def _lower_duty_before_period(
        self,
        paths: PwmPaths,
        state: OriginalState,
        failures: list[str],
    ) -> None:
        if state.period is None or not paths.duty_cycle.exists():
            return
        try:
            current_duty = int(self.pwm.read_file(paths.duty_cycle))
            target_period = int(state.period)
            if current_duty > target_period:
                self._restore_value(
                    paths.duty_cycle,
                    "0",
                    "Lower duty_cycle before restoring period",
                    failures,
                )
        except (OSError, ValueError) as exc:
            message = str(exc)
            failures.append(f"{paths.duty_cycle}: {message}")
            self.logger.step(
                "Read duty_cycle before restoring period",
                [("path", paths.duty_cycle)],
                "FAIL",
                message,
            )

    def _restore_period(
        self,
        paths: PwmPaths,
        state: OriginalState,
        failures: list[str],
    ) -> None:
        if state.period == "0":
            self.logger.step(
                "Restore period",
                [
                    ("path", paths.period),
                    ("value", 0),
                    ("reason", "zero period not writable"),
                ],
                "PASS",
            )
            return
        self._restore_value(
            paths.period,
            state.period,
            "Restore period",
            failures,
        )

    def _unexport(
        self,
        paths: PwmPaths,
        pwm_index: int,
        failures: list[str],
    ) -> None:
        try:
            self.pwm.write_file(paths.unexport, str(pwm_index))
            self.logger.step(
                "Unexport PWM",
                [("path", paths.unexport), ("value", pwm_index)],
                "PASS",
            )
        except OSError as exc:
            message = str(exc)
            failures.append(f"{paths.unexport}: {message}")
            self.logger.step(
                "Unexport PWM",
                [("path", paths.unexport), ("value", pwm_index)],
                "FAIL",
                message,
            )


class TestCommand:
    """Implement the `test` subcommand."""

    def __init__(self, pwm: PwmSysfs, logger: StepLogger) -> None:
        """Create a test command.

        Args:
            pwm: Sysfs gateway used for discovery and file I/O.
            logger: Logger for test step output.
        """
        self.pwm = pwm
        self.logger = logger
        self.restorer = PwmRestorer(pwm, logger)

    def run(
        self,
        chip_name: str,
        pwm_name: str,
        force: bool,
        values: TestValues,
    ) -> int:
        """Run the PWM sysfs validation.

        Args:
            chip_name: Stable PWM controller name or basename.
            pwm_name: Debugfs PWM output name, such as `pwm-0`.
            force: Whether to test a PWM with an active consumer.
            values: Period and duty-cycle test values.

        Returns:
            Process exit code.
        """
        output = find_output(self.pwm.read_outputs(), chip_name, pwm_name)
        pwm_index = pwm_name_to_index(output.pwm_name)
        paths = self._resolve_paths(output)

        self._validate_consumer(output, force)
        self._print_header(output)
        self._log_resolved(output, paths)

        originally_exported = paths.pwm.exists()
        self._ensure_exported(paths, pwm_index, originally_exported)
        original_state = self._capture_original_state(
            paths,
            originally_exported,
        )

        test_failure = self._run_test_steps(paths, output, values)
        restore_failures = self.restorer.restore(
            paths,
            pwm_index,
            original_state,
        )

        if test_failure or restore_failures:
            print("RESULT: FAIL")
            return 1

        print("RESULT: PASS")
        return 0

    def _resolve_paths(self, output: PwmOutput) -> PwmPaths:
        pwm_sysfs_name = pwm_name_to_sysfs(output.pwm_name)
        pwmchip_path = self.pwm.resolve_pwmchip_path(output)
        return PwmPaths(
            pwmchip=pwmchip_path,
            pwm=pwmchip_path / pwm_sysfs_name,
            pwm_sysfs_name=pwm_sysfs_name,
        )

    def _validate_consumer(self, output: PwmOutput, force: bool) -> None:
        if output.consumer is not None and not force:
            raise PwmError(
                f"{output.chip_name} {output.pwm_name} has active consumer "
                f"{output.consumer}; use --force to test it"
            )
        if output.consumer is not None and force:
            print(
                f"WARNING {output.chip_name} {output.pwm_name} "
                f"active consumer={output.consumer}; continuing due to --force"
            )

    def _print_header(self, output: PwmOutput) -> None:
        print("TEST: PWM sysfs validation")
        print(f"TARGET: {output.chip_name} {output.pwm_name}")
        print("FIELDS: period duty_cycle polarity enable")
        print()

    def _log_resolved(self, output: PwmOutput, paths: PwmPaths) -> None:
        self.logger.step(
            "Resolve PWM device",
            [
                ("name", output.chip_name),
                ("pwmchip", paths.pwmchip),
                ("pwm", paths.pwm_sysfs_name),
            ],
            "PASS",
        )

    def _ensure_exported(
        self,
        paths: PwmPaths,
        pwm_index: int,
        originally_exported: bool,
    ) -> None:
        if not originally_exported:
            self._write_step(paths.export, str(pwm_index), "Export PWM")
            self.pwm.wait_for_path(paths.pwm)
            return
        self.logger.step(
            "Check PWM export state",
            [("path", paths.pwm), ("exported", "already")],
            "PASS",
        )

    def _capture_original_state(
        self,
        paths: PwmPaths,
        exported: bool,
    ) -> OriginalState:
        state = OriginalState(exported=exported)
        for field in ("period", "duty_cycle", "polarity", "enable"):
            path = paths.pwm / field
            if path.exists():
                try:
                    setattr(state, field, self.pwm.read_file(path))
                except OSError as exc:
                    raise PwmError(
                        f"cannot read original {path}: {exc}"
                    ) from exc

        self.logger.step(
            "Record original state",
            [
                ("period", state.period),
                ("duty_cycle", state.duty_cycle),
                ("polarity", state.polarity),
                ("enable", state.enable),
                ("originally_exported", state.exported),
            ],
            "PASS",
        )
        return state

    def _run_test_steps(
        self,
        paths: PwmPaths,
        output: PwmOutput,
        values: TestValues,
    ) -> str | None:
        try:
            self._disable_if_needed(paths)
            self._write_step(paths.period, values.period, "Write period")
            self._verify_step(paths.period, values.period, "Verify period")
            self._write_step(
                paths.duty_cycle,
                values.duty_cycle,
                "Write duty_cycle",
            )
            self._verify_step(
                paths.duty_cycle,
                values.duty_cycle,
                "Verify duty_cycle",
            )
            self._test_polarity(paths)
            self._test_enable(paths)
        except (OSError, PwmError) as exc:
            message = str(exc)
            self.logger.step(
                "Test failed",
                [("target", f"{output.chip_name} {output.pwm_name}")],
                "FAIL",
                message,
            )
            return message
        return None

    def _disable_if_needed(self, paths: PwmPaths) -> None:
        if not paths.enable.exists():
            return
        current_enable = self.pwm.read_file(paths.enable)
        if current_enable == "0":
            self.logger.step(
                "Disable PWM",
                [
                    ("path", paths.enable),
                    ("value", "0"),
                    ("action", "skip unchanged"),
                ],
                "PASS",
            )
            return
        self._write_step(paths.enable, "0", "Disable PWM")
        self._verify_step(paths.enable, "0", "Verify disable")

    def _test_polarity(self, paths: PwmPaths) -> None:
        if not paths.polarity.exists():
            self.logger.step(
                "Skip polarity",
                [("path", paths.polarity), ("reason", "not supported")],
                "SKIP",
            )
            return
        self._write_step(paths.polarity, "normal", "Write polarity normal")
        self._verify_step(paths.polarity, "normal", "Verify polarity normal")
        if self._optional_write_step(
            paths.polarity,
            "inversed",
            "Write polarity inversed",
        ):
            self._verify_step(
                paths.polarity,
                "inversed",
                "Verify polarity inversed",
            )

    def _test_enable(self, paths: PwmPaths) -> None:
        if not paths.enable.exists():
            self.logger.step(
                "Skip enable",
                [("path", paths.enable), ("reason", "not supported")],
                "SKIP",
            )
            return
        self._write_step(paths.enable, "1", "Enable PWM")
        self._verify_step(paths.enable, "1", "Verify enable")
        self._write_step(paths.enable, "0", "Disable PWM")
        self._verify_step(paths.enable, "0", "Verify disable")

    def _write_step(self, path: Path, value: str, title: str) -> None:
        try:
            self.pwm.write_file(path, value)
            self.logger.step(title, [("path", path), ("value", value)], "PASS")
        except OSError as exc:
            self.logger.step(
                title,
                [("path", path), ("value", value)],
                "FAIL",
                str(exc),
            )
            raise

    def _verify_step(self, path: Path, expected: str, title: str) -> None:
        actual = self.pwm.read_file(path)
        result = "PASS" if actual == expected else "FAIL"
        self.logger.step(
            title,
            [("path", path), ("expected", expected), ("actual", actual)],
            result,
        )
        if actual != expected:
            raise PwmError(f"{path} expected {expected}, got {actual}")

    def _optional_write_step(self, path: Path, value: str, title: str) -> bool:
        try:
            self.pwm.write_file(path, value)
            self.logger.step(title, [("path", path), ("value", value)], "PASS")
            return True
        except OSError as exc:
            if exc.errno == errno.EINVAL:
                self.logger.step(
                    f"Skip {title.removeprefix('Write ')}",
                    [
                        ("path", path),
                        ("value", value),
                        ("reason", "not supported"),
                    ],
                    "SKIP",
                )
                return False
            self.logger.step(
                title,
                [("path", path), ("value", value)],
                "FAIL",
                str(exc),
            )
            raise


def require_root() -> None:
    """Raise an error unless the process is running as root."""
    if os.geteuid() != 0:
        raise PwmError("this script must run as root")


def parse_csv(value: str | None) -> set[str]:
    """Parse a comma-separated CLI value into non-empty items."""
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def normalize_consumer(raw: str) -> str | None:
    """Normalize debugfs consumer text to `None` for undefined consumers."""
    consumer = raw.strip()
    if consumer == "(null)" or not consumer:
        return None
    return consumer


def matches_chip(output: PwmOutput, value: str) -> bool:
    """Return whether a value matches a full chip name or chip basename."""
    return value == output.chip_name or value == output.chip_basename


def matches_filter(output: PwmOutput, value: str) -> bool:
    """Return whether a resource filter matches chip or consumer."""
    if matches_chip(output, value):
        return True
    return output.consumer == value


def is_ignored(output: PwmOutput, ignore: set[str]) -> bool:
    """Return whether a PWM output matches the resource ignore set."""
    return any(matches_filter(output, item) for item in ignore)


def is_allowed(output: PwmOutput, allow: set[str]) -> bool:
    """Return whether a PWM output matches the resource allow set."""
    return any(matches_filter(output, item) for item in allow)


def pwm_name_to_index(pwm_name: str) -> int:
    """Convert a debugfs PWM name like `pwm-2` to numeric index `2`."""
    match = re.fullmatch(r"pwm-(\d+)", pwm_name)
    if not match:
        raise PwmError(
            f"PWM_NAME must use debugfs form like pwm-0: {pwm_name}"
        )
    return int(match.group(1))


def pwm_name_to_sysfs(pwm_name: str) -> str:
    """Convert a debugfs PWM name like `pwm-2` to sysfs name `pwm2`."""
    return f"pwm{pwm_name_to_index(pwm_name)}"


def make_resource_id(output: PwmOutput) -> str:
    """Create a safe Checkbox job-id suffix for a PWM output."""
    raw_id = f"{output.chip_name}-{output.pwm_name}"
    return re.sub(r"[^A-Za-z0-9_.-]", "-", raw_id)


def find_output(
    outputs: list[PwmOutput],
    chip_name: str,
    pwm_name: str,
) -> PwmOutput:
    """Find one PWM output by stable chip name and debugfs PWM name."""
    if chip_name.startswith("pwmchip"):
        raise PwmError("PWM_CHIP_NAME must not be a pwmchip* sysfs name")

    pwm_name_to_index(pwm_name)
    chip_matches = [
        output for output in outputs if matches_chip(output, chip_name)
    ]
    if not chip_matches:
        raise PwmError(f"cannot find PWM_CHIP_NAME: {chip_name}")

    for output in chip_matches:
        if output.pwm_name == pwm_name:
            return output

    available = ", ".join(output.pwm_name for output in chip_matches)
    raise PwmError(
        f"cannot find PWM_NAME {pwm_name} under "
        f"{chip_matches[0].chip_name}; available: {available}"
    )


def validate_test_values(period: int, duty_cycle: int) -> TestValues:
    """Validate CLI period and duty-cycle values."""
    if period <= 0:
        raise PwmError("--period must be greater than 0")
    if duty_cycle < 0:
        raise PwmError("--duty-cycle must be greater than or equal to 0")
    if duty_cycle > period:
        raise PwmError("--duty-cycle must be less than or equal to --period")
    return TestValues(period=str(period), duty_cycle=str(duty_cycle))


def print_resource(args: argparse.Namespace) -> int:
    """CLI adapter for the `resource` command."""
    return ResourceCommand(PwmSysfs()).run(args.ignore, args.allow)


def run_test(args: argparse.Namespace) -> int:
    """CLI adapter for the `test` command."""
    values = validate_test_values(args.period, args.duty_cycle)
    return TestCommand(PwmSysfs(), StepLogger()).run(
        chip_name=args.pwm_chip_name,
        pwm_name=args.pwm_name,
        force=args.force,
        values=values,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser without executing commands."""
    parser = argparse.ArgumentParser(
        description="Discover and validate Linux PWM sysfs devices."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    resource = subparsers.add_parser(
        "resource",
        help="List stable PWM resources eligible for testing.",
    )
    resource.add_argument(
        "--ignore",
        help="Comma-separated controller or consumer names to skip.",
    )
    resource.add_argument(
        "--allow",
        help="Comma-separated controller or consumer names to include.",
    )
    resource.set_defaults(func=print_resource)

    test = subparsers.add_parser("test", help="Validate one PWM output.")
    test.add_argument("pwm_chip_name", metavar="PWM_CHIP_NAME")
    test.add_argument("pwm_name", metavar="PWM_NAME")
    test.add_argument(
        "--force",
        action="store_true",
        help="Test an active-consumer PWM output.",
    )
    test.add_argument(
        "--period",
        type=int,
        default=int(TEST_PERIOD),
        help=f"Test period in ns. Default: {TEST_PERIOD}.",
    )
    test.add_argument(
        "--duty-cycle",
        type=int,
        default=int(TEST_DUTY_CYCLE),
        help=f"Test duty cycle in ns. Default: {TEST_DUTY_CYCLE}.",
    )
    test.set_defaults(func=run_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        require_root()
        return args.func(args)
    except PwmError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
