#!/usr/bin/env python3
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
import glob
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

GSETTINGS_POWER = "org.gnome.settings-daemon.plugins.power"
GSETTINGS_SESSION = "org.gnome.desktop.session"
LOGGER_TAG = "idle_suspend_test"

SUSPEND_PATTERNS = [
    r"PM: suspend entry",
    r"Suspending system",
    r"Reached target.*[Ss]leep",
]
RESUME_PATTERNS = [
    r"PM: suspend exit",
    r"PM: resume",
    r"Finished.*[Rr]esume",
    r"ACPI: Waking",
]

AC_ONLINE_GLOBS = [
    "/sys/class/power_supply/ADP*/online",
    "/sys/class/power_supply/AC*/online",
    "/sys/class/power_supply/ACAD*/online",
]


def run_cmd(cmd: List[str], check: bool = True) -> str:
    """Run a shell command and return stdout as a stripped string."""
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError("Command {} failed: {}".format(cmd, result.stderr))
    return result.stdout.strip()


def _find_ac_online_path() -> Optional[str]:
    """Return the first sysfs AC online path found, or None."""
    for pattern in AC_ONLINE_GLOBS:
        paths = glob.glob(pattern)
        if paths:
            return paths[0]
    return None


def check_power_mode(mode: str) -> None:
    """Verify system is on the expected power mode.

    Raises SystemExit if the requirement is not met.
    """
    ac_path = _find_ac_online_path()
    if ac_path is None:
        raise SystemExit("Cannot determine AC power status.")
    try:
        with open(ac_path) as fh:
            ac_online = fh.read().strip() == "1"
    except OSError as exc:
        raise SystemExit("Cannot read power status: {}".format(exc))
    if mode == "ac" and not ac_online:
        raise SystemExit("Mode is 'ac' but system is running on battery.")
    if mode == "battery" and ac_online:
        raise SystemExit("Mode is 'battery' but system is on AC power.")


def log_timestamp() -> datetime:
    """Log a start timestamp to the system journal via logger.

    Returns the captured naive UTC datetime.
    """
    now = datetime.now(timezone.utc)
    message = "SUSPEND_TEST_START: {}".format(
        now.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    run_cmd(["logger", "-t", LOGGER_TAG, message])
    return now


def get_journal_since(since: datetime) -> str:
    """Retrieve journal entries since the given naive UTC datetime."""
    since_str = since.strftime("%Y-%m-%d %H:%M:%S")
    return run_cmd(
        [
            "journalctl",
            "--since",
            since_str,
            "--no-pager",
            "-o",
            "short-iso",
        ],
        check=False,
    )


def _parse_ts(ts_str: str) -> Optional[datetime]:
    """Parse a short-iso timestamp string to a naive UTC datetime.

    Returns None on parse failure.
    """
    normalized = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", ts_str)
    try:
        dt = datetime.strptime(normalized, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) - dt.utcoffset()


def parse_journal_suspend_times(
    journal_output: str,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Parse journal output for the latest suspend and resume times.

    Returns a tuple (suspend_utc, resume_utc) of naive UTC datetimes.
    Either value may be None if not found.
    """
    suspend_utc = None
    resume_utc = None
    ts_re = re.compile(
        r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})"
    )
    for line in journal_output.splitlines():
        match = ts_re.match(line)
        if not match:
            continue
        ts = _parse_ts(match.group(1))
        if ts is None:
            continue
        for pattern in SUSPEND_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                suspend_utc = ts
                break
        for pattern in RESUME_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                resume_utc = ts
                break
    return suspend_utc, resume_utc


def build_parser() -> argparse.ArgumentParser:
    """Return the configured argument parser."""
    parser = argparse.ArgumentParser(
        description="Test automatic idle suspend on Ubuntu GNOME."
    )
    parser.add_argument(
        "--mode",
        choices=["ac", "battery"],
        required=True,
        help="Power mode to test: 'ac' or 'battery'.",
    )
    parser.add_argument(
        "--suspend-time",
        type=int,
        default=15,
        help="Automatic suspend delay in minutes (default: 15).",
    )
    parser.add_argument(
        "--extra-percent",
        type=float,
        default=10.0,
        help=("Extra wait percentage beyond suspend time " "(default: 10)."),
    )
    return parser


def main() -> None:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    suspend_seconds = args.suspend_time * 60
    extra_factor = 1.0 + args.extra_percent / 100.0
    wait_seconds = suspend_seconds * extra_factor
    allowed_delta = suspend_seconds * (args.extra_percent / 100.0)

    check_power_mode(args.mode)

    log_start_utc = log_timestamp()
    print(
        "Test started at (UTC): {}".format(
            log_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        ),
        flush=True,
    )
    print(
        "Waiting {:.0f}s for system to suspend and "
        "resume...".format(wait_seconds),
        flush=True,
    )

    time.sleep(wait_seconds)

    journal_since = log_start_utc - timedelta(seconds=5)
    journal_output = get_journal_since(journal_since)
    suspend_utc, resume_utc = parse_journal_suspend_times(journal_output)

    if suspend_utc is None:
        raise SystemExit("FAIL: No suspend entry found in journal.")
    if suspend_utc < log_start_utc:
        raise SystemExit(
            "FAIL: Suspend entry ({}) predates test start "
            "({}).".format(
                suspend_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                log_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        )

    actual_delta = (suspend_utc - log_start_utc).total_seconds()
    if abs(actual_delta - suspend_seconds) > allowed_delta:
        raise SystemExit(
            "FAIL: Suspend delay {:.1f}s vs expected {}s "
            "(tolerance {:.1f}s).".format(
                actual_delta, suspend_seconds, allowed_delta
            )
        )

    print("Log at ({})".format(log_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")))
    print("Suspend at ({})".format(suspend_utc.strftime("%Y-%m-%dT%H:%M:%SZ")))
    print("Resume at ({})".format(resume_utc.strftime("%Y-%m-%dT%H:%M:%SZ")))
    print(
        "Suspend delay {:.1f}s vs expected {}s "
        "(tolerance {:.1f}s).".format(
            actual_delta, suspend_seconds, allowed_delta
        )
    )
    print("PASS: Automatic suspend test passed.")


if __name__ == "__main__":
    main()
