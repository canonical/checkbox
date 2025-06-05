#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Stanley Huang <stanley.huang@canonical.com>
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
import os
import shlex
import shutil
import subprocess
import sys
import time

from configparser import ConfigParser
from contextlib import contextmanager
from pathlib import Path


WATCHDOG_CONFIG_FILE = "/etc/systemd/system.conf"
WATCHDOG_DEV_PATTERN = "WatchdogDevice"
WATCHDOG_TIMEOUT_PATTERN = "RuntimeWatchdogSec"
WATCHDOG_LOG_FILE = "watchdog_test.log"
MAX_WATCHDOG_TIMEOUT = 30


def watchdog_argparse() -> argparse.Namespace:
    """
    Parse command line arguments and return the parsed arguments.

    This function parses the command line arguments and returns the parsed
    arguments. The arguments are parsed using the `argparse` module. The
    function takes no parameters.

    Returns:
        argparse.Namespace: The parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        prog="Watchdog Testing Tool",
        description="This is a tool to help you perform the watchdog testing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sub_parsers = parser.add_subparsers(dest="method")

    detection_parser = sub_parsers.add_parser(
        "detect",
        help="Check if watchdog service timeout is configured correctly",
    )
    detection_parser.add_argument(
        "--module",
        type=str,
        default="",
        help="watchdog kernel module being probe during testing",
    )
    detection_parser.add_argument(
        "--identity", type=str, default="", help="watchdog identity value"
    )

    system_reset_parser = sub_parsers.add_parser(
        "trigger-reset",
        help="Trigger kernel panic and system should be restart by watchdog",
    )
    system_reset_parser.add_argument(
        "--module",
        type=str,
        default="",
        help="watchdog kernel module being probe during testing",
    )
    system_reset_parser.add_argument(
        "--identity", type=str, default="", help="watchdog identity value"
    )
    system_reset_parser.add_argument(
        "--timeout",
        type=int,
        default=MAX_WATCHDOG_TIMEOUT,
        help="WatchdogRuntimeSec",
    )
    system_reset_parser.add_argument(
        "--log-dir",
        type=str,
        default=os.getcwd(),
        help="the directory to store logs and to store backup configuration",
    )

    post_check_parser = sub_parsers.add_parser(
        "post-check", help="post-check and restore systemd config"
    )
    post_check_parser.add_argument(
        "--log-dir",
        type=str,
        default=os.getcwd(),
        help="the directory to store logs and to store backup configuration",
    )

    return parser.parse_args()


@contextmanager
def probe_watchdog_module(kernel_module):
    """
    a context manager function to load and unload watchdog kernel module

    Args:
        kernel_module:
            watchdog kernel module

    Raises:
        SystemExit: when no watchdog device available
    """
    ret = None
    # probe watchdog kernel module if it's not exists
    ret = subprocess.run(shlex.split("modprobe {}".format(kernel_module)))
    time.sleep(2)
    try:
        yield
    except Exception as err:
        print(err)
    finally:
        if ret and ret.returncode == 0:
            cmd = "modprobe -r {}".format(kernel_module)
            subprocess.run(shlex.split(cmd))


def collect_hardware_watchdogs(watchdog_identity: str = "") -> dict:
    """
    Collect hardware watchdog under /sys/class/watchdog/.

    This function iterates over the watchdog devices under
    /sys/class/watchdog, collect all hardware watchdog when
    if watchdog_identity is not provided.

    Args:
        watchdog_identity (str): expected identity string of watchdog device

    Returns:
        hardware_watchdogs (dict): watchdog devices in dictionary format
                                   key is watchdog device, value is identity
    """
    hardware_watchdogs = {}

    fs_wtdgs = glob.glob("/sys/class/watchdog/watchdog*")
    print("\ncollect watchdog devices..")
    for node in fs_wtdgs:
        try:
            p_node = Path(node)
            link = str(p_node.readlink())
            identity = p_node.joinpath("identity").read_text().strip()
            print("- {}: {}".format(p_node.name, identity))
            if watchdog_identity and identity == watchdog_identity:
                # include watchdog dev
                # when watchdog_identify is provided and the match identity
                hardware_watchdogs[p_node.name] = identity
                continue

            if "devices/virtual" in link:
                # Filter the software watchdog
                print(
                    "# Ignore {} due to it's a software watchdog".format(
                        p_node.name
                    ),
                    file=sys.stderr,
                )
                continue

            hardware_watchdogs[p_node.name] = identity
        except Exception as err:
            print("Unable to collect watchdog information", file=sys.stderr)
            print(err)

    return hardware_watchdogs


def backup_systemd_config(backup_dir) -> None:
    shutil.copy(WATCHDOG_CONFIG_FILE, backup_dir)


def restore_systemd_config(backup_dir) -> None:
    backup_file = Path(backup_dir).joinpath("system.conf")
    shutil.copy(backup_file, WATCHDOG_CONFIG_FILE)


def dump_watchdog_config() -> None:
    print("# Dump systemd.conf")
    print(Path(WATCHDOG_CONFIG_FILE).read_text())


def configure_watchdog_config(dev, timeout) -> None:
    """
    update the system.conf under /etc/systemd and reload daemon.
    this function update RuntimeWatchdogSec and WatchdogDevice in system.conf

    Args:
        watchdog_dev:

    Raises:
        SystemExit: when no watchdog device available
    """
    parser = ConfigParser()
    parser.optionxform = lambda option: option
    parser.read(WATCHDOG_CONFIG_FILE)

    watchdog_devstr = "/dev/{}".format(dev)

    # Update watchdog device if needed
    cur_watchdog = parser.get("Manager", WATCHDOG_DEV_PATTERN, fallback=None)
    if cur_watchdog != watchdog_devstr:
        parser.set("Manager", WATCHDOG_DEV_PATTERN, watchdog_devstr)

    # Update watchdog timeout to 30s
    parser.set("Manager", WATCHDOG_TIMEOUT_PATTERN, timeout)

    with open(WATCHDOG_CONFIG_FILE, "w") as fp:
        parser.write(fp)
    dump_watchdog_config()
    subprocess.run(shlex.split("systemctl daemon-reload"), check=True)


def watchdog_test_timestamp(log_dir):
    """
    Log the timestamp before perform watchdog reset test

    Args:
        log_dir (str): the directory to store WATCHDOG_LOG_FILE
    """
    # Add a watchdog test timestamp
    log_file = Path(log_dir).joinpath(WATCHDOG_LOG_FILE)
    log_file.write_text(str(time.time()))


def trigger_system_reset(backup_dir, watchdog_dev, watchdog_timeout) -> None:
    """
    Trigger kernel panic and system shall recover by watchdog device

    This function will backup/modify the watchdog config in system.conf,
    then trigger kernel panic

    Args:
        backup_dir: directory to store system.conf and log file
        watchdog_dev: watchdog device
        watchdog_timeout: watchdog timeout

    Raises:
        SystemExit: when no watchdog device available
    """
    print(
        "Trigger kernel panic and system shall recover by {} device".format(
            watchdog_dev
        )
    )
    watchdog_test_timestamp(backup_dir)
    backup_systemd_config(backup_dir)
    configure_watchdog_config(watchdog_dev, str(watchdog_timeout))
    subprocess.run(shlex.split("sync"))
    subprocess.run(shlex.split("sleep 5"))
    Path("/proc/sys/kernel/sysrq").write_text("1")
    Path("/proc/sys/kernel/panic").write_text("0")
    Path("/proc/sysrq-trigger").write_text("c")


def watchdog_detection_test(watchdog_module, watchdog_identity) -> None:
    """
    Detects watchdog under /sys/class/watchdog/.

    This function executes the watchdog detection process. It then iterates
    over the watchdog devices under "/sys/class/watchdog/", verifies their
    identities to ensure it's not a software watchdog.

    additional information
    - load the module if expected hardware watchdog is not enabled by default.
    - filter watchdog if watchdog_identity is provided.

    Args:
        watchdog_module:
            probe module when watchdog kernel module is not probe by default
            DO NOT provide kernel module
                if a watchdog expected to be enable by default
        watchdog_identity: expected identity string of watchdog device

    Raises:
        SystemExit: when no watchdog device available
    """
    print("# Perform watchdog detection test")
    if watchdog_identity and watchdog_module:
        try:
            with probe_watchdog_module(watchdog_module):
                if collect_hardware_watchdogs(watchdog_identity):
                    print(
                        "\nPassed: {} watchdog detected".format(
                            watchdog_identity
                        )
                    )
                    return
        except subprocess.CalledProcessError as err:
            print(err, file=sys.stderr)
        raise SystemExit("Error: No expected hardware watchdog been detected")
    else:
        if collect_hardware_watchdogs(watchdog_identity):
            print("\nPassed: hardware watchdog detected")
            return
        raise SystemExit("Error: No hardware watchdog available")


def watchdog_reset_test(
    kernel_module, watchdog_identity, log_dir, watchdog_timeout
) -> None:
    """
    perform watchdog reset test
    this scripts would reset system by systemctl command when no kernel panic

    Args:
        kernel_module: watchdog kernel module
        watchdog_identity: expected identity string of watchdog device
        log_dir: directory to store system.conf and log file
        watchdog_timeout: watchdog timeout

    Raises:
        SystemExit: when no watchdog device available
    """
    print("# Perform watchdog reset test")
    try:
        watchdog_dev = collect_hardware_watchdogs(watchdog_identity)
        if watchdog_dev:
            trigger_system_reset(
                log_dir, next(iter(watchdog_dev)), watchdog_timeout
            )
        else:
            with probe_watchdog_module(kernel_module):
                watchdog_dev = collect_hardware_watchdogs(watchdog_identity)
                if watchdog_dev:
                    trigger_system_reset(
                        log_dir, next(iter(watchdog_dev)), watchdog_timeout
                    )
    except subprocess.CalledProcessError as err:
        print(err, file=sys.stderr)
    except Exception as err:
        # bypass all exceptions as this is a no return job in checkbox
        print(err, file=sys.stderr)
    finally:
        # Reboot system manually due to the system is not restart by watchdog
        # When this file exists, it means test failed
        time.sleep(60)
        log_file = Path(log_dir).joinpath("watchdog_manual_reset.log")
        log_file.write_text("system reset by watchdog")
        subprocess.run(shlex.split("sync"))
        subprocess.run(shlex.split("systemctl reboot"))


def post_check_test(log_dir):
    """
    post watchdog check test

    Args:
        log_dir: directory to store system.conf and log file

    Raises:
        SystemExit: when no watchdog device available
    """
    print("# Post check test")
    restore_systemd_config(log_dir)
    if Path(log_dir).joinpath("watchdog_manual_reset.log").exists():
        raise SystemExit("Error: System reset by scripts, not watchdog")

    start_time = Path(log_dir).joinpath(WATCHDOG_LOG_FILE).read_text()
    system_uptime = float(Path("/proc/uptime").read_text().split(" ")[0])
    time_diff = time.time() - system_uptime - float(start_time)
    if time_diff > 300:
        raise SystemExit(
            "Error: system reset take more than 300 seconds, "
            "this may be caused by reseting by user interaction"
        )

    print("Passed: system been reset by watchdog")


def main():
    args = watchdog_argparse()
    if args.method == "detect":
        watchdog_detection_test(args.module, args.identity)
    elif args.method == "trigger-reset":
        watchdog_reset_test(
            args.module,
            args.identity,
            args.log_dir,
            max(args.timeout, MAX_WATCHDOG_TIMEOUT),
        )
    elif args.method == "post-check":
        post_check_test(args.log_dir)
    else:
        raise SystemExit("Unexpected arguments")


if __name__ == "__main__":
    main()
