#!/usr/bin/env python3
# RTC (Real Time Clock) test utility for Checkbox.
#
# Consolidates the shell logic previously embedded in the
# rtc/battery, rtc/rtc_number, rtc_list, rtc/rtc_read_{rtc},
# rtc/rtc_alarm_{rtc} and rtc/rtc_clock_{rtc} jobs into a single
# script with subcommands, following the argparse + dispatch-table
# pattern used by other checkbox-support scripts.

import argparse
import glob
import os
import subprocess
import sys
import time


def find_rtc_devices():
    """Return a sorted list of rtc device names under /dev, e.g. ['rtc0']."""
    return sorted(os.path.basename(p) for p in glob.glob("/dev/rtc[0-9]*"))


def _can_read(path):
    try:
        with open(path) as f:
            f.read()
        return True
    except OSError:
        return False


def cmd_list(args):
    """Resource job: emit one record per RTC device found."""
    for rtc in find_rtc_devices():
        print("rtc: {}".format(rtc))
        print()
    return 0


def cmd_number(args):
    """Check that the number of RTC devices matches the expected count."""
    expected = args.total
    if expected is None:
        env_val = os.environ.get("TOTAL_RTC_NUM")
        if env_val:
            expected = int(env_val)
        else:
            print("TOTAL_RTC_NUM not defined, defaulting to 1")
            expected = 1

    found = find_rtc_devices()
    print("TOTAL_RTC_NUM: {}".format(expected))
    print("Number of RTC devices found in sysfs: {}".format(len(found)))

    if len(found) != expected:
        print("RTC number mismatch")
        return 1
    print("RTC number matched")
    return 0


def cmd_read(args):
    """Check /sys/class/rtc/<rtc>/since_epoch is readable; sync via hwclock if not."""
    rtc = args.rtc
    since_epoch_path = "/sys/class/rtc/{}/since_epoch".format(rtc)

    if _can_read(since_epoch_path):
        return 0

    print("Warning: Unable to read {}.".format(since_epoch_path))

    hwclock_cmd = ["hwclock", "--systohc", "--utc", "--rtc=/dev/{}".format(rtc)]
    result = subprocess.run(hwclock_cmd)
    if result.returncode != 0:
        print("Error: hwclock sync failed.")
        return 1

    if not _can_read(since_epoch_path):
        print("Error: RTC is still not readable after hwclock sync.")
        return 1

    return 0


def cmd_alarm(args):
    """Check that the RTC's wakealarm works via rtcwake, with a timeout guard."""
    rtc = args.rtc
    wakealarm_path = "/sys/class/rtc/{}/wakealarm".format(rtc)

    if not os.path.isfile(wakealarm_path):
        print("{} does not support wakealarm".format(rtc))
        return 1

    cmd = ["rtcwake", "-d", rtc, "-v", "-m", "on", "-s", str(args.seconds)]
    try:
        subprocess.run(cmd, timeout=args.timeout, check=True)
    except subprocess.TimeoutExpired:
        print("Error: rtcwake timed out!")
        return 1
    except subprocess.CalledProcessError as exc:
        print("Error: rtcwake failed with exit code {}".format(exc.returncode))
        return 1

    return 0


def cmd_clock(args):
    """Check that the RTC clock is synchronized with the system clock."""
    rtc = args.rtc
    since_epoch_path = "/sys/class/rtc/{}/since_epoch".format(rtc)

    with open(since_epoch_path) as f:
        rtc_time = int(f.read().strip())
    sys_time = int(time.time())
    diff = sys_time - rtc_time

    if diff <= args.tolerance:
        print("{} Clock synchronized with System Clock".format(rtc))
        print("RTC clock= {}".format(rtc_time))
        return 0

    print("{} Clock not synchronized with System Clock".format(rtc))
    print("System clock= {}".format(sys_time))
    print("RTC clock= {}".format(rtc_time))
    return 1


def cmd_battery(args):
    """Disable any pending wakealarm, then power off with a wake scheduled
    in N seconds. On success this powers the machine off, so the process
    will not return control to the caller (mirrors the job's `noreturn`
    flag)."""
    rtc = args.rtc
    subprocess.run(["rtcwake", "-v", "-d", rtc, "-m", "disable"], check=False)
    result = subprocess.run(
        ["rtcwake", "-v", "-d", rtc, "-m", "off", "-s", str(args.seconds)]
    )
    return result.returncode


def build_parser():
    parser = argparse.ArgumentParser(description="RTC test utility")
    sub = parser.add_subparsers(dest="action", required=True)

    default_rtc = os.environ.get("RTC_DEVICE_FILE", "rtc0")

    p_list = sub.add_parser("list", help="List RTC devices (resource job)")
    p_list.set_defaults(func=cmd_list)

    p_number = sub.add_parser("number", help="Check RTC device count")
    p_number.add_argument(
        "--total", type=int, default=None,
        help="Expected RTC count (falls back to $TOTAL_RTC_NUM, then 1)",
    )
    p_number.set_defaults(func=cmd_number)

    p_read = sub.add_parser("read", help="Check RTC is readable")
    p_read.add_argument("--rtc", default=default_rtc)
    p_read.set_defaults(func=cmd_read)

    p_alarm = sub.add_parser("alarm", help="Check RTC wakealarm")
    p_alarm.add_argument("--rtc", default=default_rtc)
    p_alarm.add_argument("--seconds", type=int, default=30)
    p_alarm.add_argument("--timeout", type=int, default=60)
    p_alarm.set_defaults(func=cmd_alarm)

    p_clock = sub.add_parser("clock", help="Check RTC clock is in sync")
    p_clock.add_argument("--rtc", default=default_rtc)
    p_clock.add_argument("--tolerance", type=int, default=5)
    p_clock.set_defaults(func=cmd_clock)

    p_battery = sub.add_parser("battery", help="RTC battery wake-from-poweroff test")
    p_battery.add_argument("--rtc", default=default_rtc)
    p_battery.add_argument("--seconds", type=int, default=30)
    p_battery.set_defaults(func=cmd_battery)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
