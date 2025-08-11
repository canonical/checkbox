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
import re
import shutil
import subprocess
import sys
import time

from abc import ABC, abstractmethod
from configparser import ConfigParser
from contextlib import contextmanager
from pathlib import Path

from checkbox_support.snap_utils.system import on_ubuntucore
from checkbox_support.snap_utils.system import get_series


WATCHDOG_LOG_FILE = "watchdog_test.log"
MAX_WATCHDOG_TIMEOUT = 30
USAGE = """
Watchdog Testing Tool - A tool to help you perform the watchdog testing

Usage:
  watchdog.py detect [--module MODULE] [--identity ID]
  watchdog.py trigger-reset [--module MODULE] [--identity ID] [--timeout SECONDS] [--log-dir DIR]
  watchdog.py post-check [--log-dir DIR]

Commands:
  detect         Detect whether a watchdog device is available on the system
  trigger-reset  Trigger kernel panic and system should be restarted by watchdog
  post-check     Perform post-check and restore systemd watchdog config

Options:
  --module MODULE      Watchdog kernel module being probed during testing (optional)
  --identity ID        Watchdog identity value (optional)
  --timeout SECONDS    Watchdog timeout duration in seconds (default: MAX_WATCHDOG_TIMEOUT)
  --log-dir DIR        Directory to store logs and backup configuration (default: current directory)
  -h, --help           Show this help message and exit

Examples:
  watchdog.py detect --module iTCO_wdt
  watchdog.py trigger-reset --module iTCO_wdt --identity "Intel WDT" --timeout 30 --log-dir /tmp/wdt
  watchdog.py post-check --log-dir /tmp/wdt
"""  # noqa: E501


class WatchdogConfigHandler(ABC):

    config_filename = ""
    config_path = ""
    timeout_pattern = ""

    @classmethod
    def backup_config(cls, backup_dir) -> None:
        shutil.copy(
            os.path.join(cls.config_path, cls.config_filename), backup_dir
        )

    @classmethod
    @abstractmethod
    def update_config(cls):
        "update watchdog device and timeout"
        return NotImplemented

    @classmethod
    def restore_config(cls, backup_dir) -> None:
        backup_file = os.path.join(backup_dir, cls.config_filename)
        shutil.copy(backup_file, cls.config_path)

    @classmethod
    def dump_watchdog_config(self) -> None:
        print("# Dump configuration")
        print(
            Path(self.config_path).joinpath(self.config_filename).read_text()
        )


class WatchdogServiceHandler(WatchdogConfigHandler):
    config_filename = "watchdog.conf"
    config_path = "/etc"
    timeout_pattern = "watchdog-timeout"

    @classmethod
    def update_config(cls, dev, timeout):
        """
        update the watchdog.conf under /etc/ and reload watchdog service.
        only watchdog-timeout would be modified.

        Args:
            dev (str): the watchdog dev node (not use for now)
            timeout (str): the timeout value for watchdog-timeout

        Returns:
            timeout (str): the timeout value for watchdog
        """
        conf_file = Path(cls.config_path).joinpath(cls.config_filename)
        conf_data = conf_file.read_text()
        match = re.search(
            r"^{}[ ]*=[ ]*([0-9]*)".format(cls.timeout_pattern),
            conf_data,
            re.MULTILINE,
        )
        if match is None:
            conf_data += "\n{}  = {}".format(cls.timeout_pattern, timeout)
            conf_file.write_text(conf_data)
        else:
            timeout = match.group(1)
            print(
                "the watchdog timeout been set to {} before testing".format(
                    timeout
                )
            )

        cls.dump_watchdog_config()
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        return timeout


class SystemdWatchdogHandler(WatchdogConfigHandler):
    config_filename = "system.conf"
    config_path = "/etc/systemd"
    timeout_pattern = "RuntimeWatchdogSec"
    dev_pattern = "WatchdogDevice"

    @classmethod
    def update_config(cls, dev, timeout):
        """
        update the system.conf under /etc/systemd and reload daemon.
        both RuntimeWatchdogSec and WatchdogDevice would be modified.

        Args:
            dev (str):     the watchdog device name
            timeout (str): the timeout value for RuntimeWatchdogSec

        Returns:
            timeout (str): the timeout value for watchdog
        """
        filename = Path(cls.config_path).joinpath(cls.config_filename)

        parser = ConfigParser()
        parser.optionxform = lambda option: option
        parser.read(filename)

        watchdog_devstr = "/dev/{}".format(dev)

        cur_watchdog = parser.get("Manager", cls.dev_pattern, fallback=None)
        if cur_watchdog != watchdog_devstr:
            parser.set("Manager", cls.dev_pattern, watchdog_devstr)

        cur_timeout = parser.get("Manager", cls.timeout_pattern, fallback=None)
        if not cur_timeout:
            parser.set("Manager", cls.timeout_pattern, timeout)
        else:
            timeout = cur_timeout
            print(
                "the watchdog timeout been set to {} before testing".format(
                    timeout
                )
            )

        with open(filename, "w") as fp:
            parser.write(fp)
        cls.dump_watchdog_config()
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        return timeout


def _get_watchdog_handler():
    ubuntu_version = int(get_series().split(".")[0])
    if ubuntu_version >= 20 or on_ubuntucore():
        return SystemdWatchdogHandler
    else:
        return WatchdogServiceHandler


def watchdog_argparse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="watchdog.py",
        epilog=USAGE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub_parsers = parser.add_subparsers(dest="method")

    detection_parser = sub_parsers.add_parser(
        "detect",
        help="Detect whether a watchdog device is available on the system",
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
        help="the directory to store logs and the backup configuration",
    )

    post_check_parser = sub_parsers.add_parser(
        "post-check", help="post-check and restore systemd config"
    )
    post_check_parser.add_argument(
        "--log-dir",
        type=str,
        default=os.getcwd(),
        help="the directory to store logs and the backup configuration",
    )

    return parser.parse_args()


@contextmanager
def probe_watchdog_module(kernel_module):
    """
    a context manager function to load/unload watchdog kernel module

    Args:
        kernel_module (str): watchdog kernel module

    Raises:
        SystemExit: when no watchdog device available
    """
    ret = None
    print("probe {} kernel module ..".format(kernel_module))
    ret = subprocess.run(["modprobe", kernel_module])
    time.sleep(2)
    try:
        yield
    except Exception as err:
        print(err)
    finally:
        if ret and ret.returncode == 0:
            subprocess.run(["modprobe", "-r", kernel_module])


def collect_hardware_watchdogs(watchdog_identity: str = "") -> dict:
    """
    Collect hardware watchdog under /sys/class/watchdog/.

    This function iterates over watchdog devices under /sys/class/watchdog,
    it will collect all hardware watchdog when no watchdog_identity provided.

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
            link = str(p_node.resolve())
            identity = p_node.joinpath("identity").read_text().strip()
            print("- {}: {}".format(p_node.name, identity))
            if watchdog_identity and identity == watchdog_identity:
                hardware_watchdogs[p_node.name] = identity
                continue

            if "devices/virtual" in link:
                print(
                    "# Ignore {} because it's a software watchdog".format(
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


def watchdog_test_timestamp(log_dir):
    """
    Log the timestamp before perform watchdog reset test

    Args:
        log_dir (str): the directory where log file will be saved
    """
    log_file = Path(log_dir).joinpath(WATCHDOG_LOG_FILE)
    log_file.write_text(str(time.time()))


def trigger_system_reset(backup_dir, watchdog_dev, watchdog_timeout) -> None:
    """
    This function will backup/modify the watchdog config in system.conf,
    then trigger kernel panic

    Args:
        log_dir: the directory where watchdog configuration and log file will be saved
        watchdog_dev: watchdog device
        watchdog_timeout: the timeout value for the watchdog
    """  # noqa: E501
    print("Update the watchdog configuration if needed")
    watchdog_test_timestamp(backup_dir)

    watchdog_handler = _get_watchdog_handler()
    watchdog_handler.backup_config(backup_dir)
    real_timeout = watchdog_handler.update_config(
        watchdog_dev, str(watchdog_timeout)
    )

    print("Triggering kernel panic {} seconds later".format(real_timeout))
    subprocess.run(["sync"])
    time.sleep(10)
    Path("/proc/sys/kernel/sysrq").write_text("1")
    Path("/proc/sys/kernel/panic").write_text("0")
    Path("/proc/sysrq-trigger").write_text("c")


def watchdog_detection_test(watchdog_module, watchdog_identity) -> None:
    """
    Detects watchdog under /sys/class/watchdog/.

    It then iterates over the watchdog devices under "/sys/class/watchdog/",
    verifies their identities to ensure it's not a software watchdog.

    Notes:
        - This script will load the kernel module only if watchdog_module is specified.
        - Some watchdogs provided by the EC may be recognized as software watchdogs; in such cases, specify the expected watchdog identity.
        - Do not provide a kernel module if the watchdog is expected to be enabled by default.

    Args:
        kernel_module: watchdog kernel module to be probe
        watchdog_identity: expected identity string of the watchdog device

    Raises:
        SystemExit: Raised if no watchdog device is detected
    """  # noqa: E501
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
    perform a watchdog reset test
    Note: if no kernel panic, this scripts would trigger a system reset using systemctl command

    Args:
        kernel_module: watchdog kernel module to be probe
        watchdog_identity: expected identity string of the watchdog device
        log_dir: the directory where watchdog configuration and log file will be saved
        watchdog_timeout: the timeout value for the watchdog
    """  # noqa: E501
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
        subprocess.run(["sync"])
        subprocess.run(["systemctl", "reboot"])


def post_check_test(log_dir):
    """
    Restore the watchdog settings and
    verify from logs that no reset occurred due to scripts or user activity.

    Args:
        log_dir: directory to store watchdog config and log file

    Raises:
        SystemExit: system been reset due to scripts or user activity.
    """
    print("# Post check test")
    _get_watchdog_handler().restore_config(log_dir)

    if Path(log_dir).joinpath("watchdog_manual_reset.log").exists():
        raise SystemExit("Error: System reset by scripts, not watchdog")

    start_time = Path(log_dir).joinpath(WATCHDOG_LOG_FILE).read_text()
    system_uptime = float(Path("/proc/uptime").read_text().split(" ")[0])
    time_diff = time.time() - system_uptime - float(start_time)
    if time_diff > 300:
        raise SystemExit(
            "Error: Reset duration exceeded 300 seconds, "
            "potentially caused by user interaction."
        )

    print("Passed: system reset by watchdog")


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
