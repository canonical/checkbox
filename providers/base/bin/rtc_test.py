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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.

import argparse
import glob
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional


def find_rtc_devices() -> List[str]:
    """Return a sorted list of rtc device names under /dev, e.g. ['rtc0']."""
    return sorted(os.path.basename(p) for p in glob.glob("/dev/rtc[0-9]*"))


def _is_readable(path: Path) -> bool:
    try:
        path.read_text()
    except OSError:
        return False
    return True


def cmd_list(args: argparse.Namespace) -> int:
    """Resource job: emit one record per RTC device found."""
    for rtc in find_rtc_devices():
        print(f"rtc: {rtc}")
        print()
    return 0


def cmd_battery(args: argparse.Namespace) -> int:
    """Disable any pending wakealarm, then power off with a
    wake scheduled in N seconds.
    """
    rtc: str = args.rtc
    default_seconds: int = args.seconds
    seconds = get_rtc_seconds("RTC_WAKEUP_SECONDS", rtc, default_seconds)
    print(f"{rtc} will wake the system in {seconds}s")
    subprocess.run(["rtcwake", "-v", "-d", rtc, "-m", "disable"], check=False)
    result = subprocess.run(
        ["rtcwake", "-v", "-d", rtc, "-m", "off", "-s", str(seconds)],
        check=False,
    )
    return result.returncode


def cmd_number(args: argparse.Namespace) -> int:
    """Check that the number of RTC devices matches the expected count."""
    expected: Optional[int] = args.total
    if expected is None:
        env_val = os.environ.get("TOTAL_RTC_NUM")
        if env_val:
            expected = int(env_val)
        else:
            print("TOTAL_RTC_NUM not defined, defaulting to 1")
            expected = 1

    found = find_rtc_devices()
    print(f"TOTAL_RTC_NUM: {expected}")
    print(f"Number of RTC devices found in sysfs: {len(found)}")

    if len(found) != expected:
        print("RTC number mismatch")
        return 1
    print("RTC number matched")
    return 0


def cmd_read_and_sync(args: argparse.Namespace) -> int:
    """Check /sys/class/rtc/<rtc>/since_epoch is readable;
    sync via hwclock if not.
    """
    rtc: str = args.rtc
    since_epoch_path = Path("/sys/class/rtc") / rtc / "since_epoch"

    if _is_readable(since_epoch_path):
        return 0

    print(f"Warning: Unable to read {since_epoch_path}.")

    hwclock_cmd = ["hwclock", "--systohc", "--utc", f"--rtc=/dev/{rtc}"]
    subprocess.run(hwclock_cmd, check=True)
    print(f"Synced system time to /dev/{rtc} via hwclock.")

    if not _is_readable(since_epoch_path):
        raise SystemExit(
            "Error: RTC is still not readable after hwclock sync."
        )

    return 0


def get_rtc_seconds(env_name: str, rtc: str, default: int) -> int:
    """Return the per-device seconds for ``rtc`` from ``env_name``.

    The variable is a comma-separated list of <rtc>:<seconds> entries,
    e.g. "rtc1:120,rtc2:90". Devices not listed use ``default``.
    """
    mapping = os.environ.get(env_name, "")
    for entry in mapping.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            name, seconds = entry.split(":")
            seconds = int(seconds)
        except ValueError:
            raise SystemExit(f"Invalid {env_name} entry: '{entry}'")
        if seconds <= 0:
            raise SystemExit(
                f"Invalid {env_name} entry: '{entry}', seconds "
                "must be a positive integer"
            )
        if os.path.basename(name.strip()) == os.path.basename(rtc):
            return seconds
    return default


def cmd_alarm(args: argparse.Namespace) -> int:
    """Check that the RTC's wakealarm works via rtcwake,
    with a timeout guard.
    """
    rtc: str = args.rtc
    unsupported = os.environ.get("UNSUPPORTED_RTC_ALARM_DEVICES", "")
    if rtc in [dev.strip() for dev in unsupported.split(",")]:
        print(f"{rtc} does not support RTC alarm")
        return 0

    wakealarm_path = Path("/sys/class/rtc") / rtc / "wakealarm"

    if not wakealarm_path.is_file():
        raise SystemExit(f"{rtc} does not support wakealarm")

    default_seconds: int = args.seconds
    seconds = get_rtc_seconds("RTC_WAKEUP_SECONDS", rtc, default_seconds)
    default_timeout: int = args.timeout
    timeout = get_rtc_seconds("RTC_WAKEUP_TIMEOUT", rtc, default_timeout)
    if timeout <= seconds:
        raise SystemExit(
            f"Error: timeout ({timeout}s) must be greater than the wakeup "
            f"time ({seconds}s), adjust RTC_WAKEUP_TIMEOUT for {rtc}"
        )
    print(f"Setting {rtc} alarm in {seconds}s (timeout {timeout}s)")

    cmd = ["rtcwake", "-v", "-d", rtc, "-m", "on", "-s", str(seconds)]
    try:
        subprocess.run(cmd, timeout=timeout, check=True)
    except subprocess.TimeoutExpired:
        raise SystemExit("Error: rtcwake timed out!")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"Error: rtcwake failed with exit code {exc.returncode}"
        )

    return 0


def cmd_clock(args: argparse.Namespace) -> int:
    """Check that the RTC clock is synchronized with the system clock."""
    rtc: str = args.rtc
    since_epoch_path = Path("/sys/class/rtc") / rtc / "since_epoch"

    rtc_time = int(since_epoch_path.read_text().strip())
    sys_time = int(time.time())
    diff = abs(sys_time - rtc_time)

    tolerance: int = args.tolerance
    if diff <= tolerance:
        print(f"{rtc} Clock synchronized with System Clock")
        print(f"RTC clock= {rtc_time}")
        return 0

    print(f"System clock= {sys_time}")
    print(f"RTC clock= {rtc_time}")
    raise SystemExit(f"{rtc} Clock not synchronized with System Clock")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RTC test utility")
    sub = parser.add_subparsers(dest="action")

    default_rtc = os.environ.get("RTC_DEVICE_FILE", "rtc0")

    p_list = sub.add_parser("list", help="List RTC devices (resource job)")
    p_list.set_defaults(func=cmd_list)

    p_battery = sub.add_parser(
        "battery", help="RTC battery wake-from-poweroff test"
    )
    p_battery.add_argument("--rtc", default=default_rtc)
    p_battery.add_argument(
        "--seconds",
        type=int,
        default=30,
        help="Wakeup delay (overridden per device by $RTC_WAKEUP_SECONDS)",
    )
    p_battery.set_defaults(func=cmd_battery)

    p_number = sub.add_parser("number", help="Check RTC device count")
    p_number.add_argument(
        "--total",
        type=int,
        default=None,
        help="Expected RTC count (falls back to $TOTAL_RTC_NUM, then 1)",
    )
    p_number.set_defaults(func=cmd_number)

    p_read = sub.add_parser(
        "read",
        help="Check RTC is readable. If not, sync it via hwclock.",
    )
    p_read.add_argument("--rtc", default=default_rtc)
    p_read.set_defaults(func=cmd_read_and_sync)

    p_alarm = sub.add_parser("alarm", help="Check RTC wakealarm")
    p_alarm.add_argument("--rtc", default=default_rtc)
    p_alarm.add_argument(
        "--seconds",
        type=int,
        default=30,
        help="Wakeup delay (overridden per device by $RTC_WAKEUP_SECONDS)",
    )
    p_alarm.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="rtcwake timeout (overridden per device by $RTC_WAKEUP_TIMEOUT)",
    )
    p_alarm.set_defaults(func=cmd_alarm)

    p_clock = sub.add_parser("clock", help="Check RTC clock is in sync")
    p_clock.add_argument("--rtc", default=default_rtc)
    p_clock.add_argument("--tolerance", type=int, default=5)
    p_clock.set_defaults(func=cmd_clock)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    func: Callable[[argparse.Namespace], int] = args.func
    return func(args)


if __name__ == "__main__":
    sys.exit(main())
