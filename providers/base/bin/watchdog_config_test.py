#!/usr/bin/env python3
# Copyright 2021 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Vic Liu <vic.liu@canonical.com>
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

import subprocess

from checkbox_support.snap_utils.system import on_ubuntucore
from checkbox_support.snap_utils.system import get_series


def get_systemd_wdt_usec():
    """
    Return value of systemd-watchdog RuntimeWatchdogUSec
    """
    cmd = ['systemctl', 'show', '-p', 'RuntimeWatchdogUSec']
    try:
        result = subprocess.check_output(cmd, universal_newlines=True)
    except Exception as err:
        raise SystemExit("Error: {}".format(err))

    if result:
        runtime_watchdog_usec = result.split("=")[1].strip()
        return runtime_watchdog_usec
    else:
        raise SystemExit(
            "Unexpected failure occurred when executing: {}".format(cmd))


def watchdog_service_check():
    """
    Check if the watchdog service is configured correctly
    """
    cmd = ['systemctl', 'is-active', 'watchdog.service', '--quiet']
    try:
        return not subprocess.run(cmd).returncode
    except Exception as err:
        raise SystemExit("Error: {}".format(err))


def main():
    runtime_watchdog_usec = get_systemd_wdt_usec()
    systemd_wdt_configured = (runtime_watchdog_usec != "0")
    wdt_service_configured = watchdog_service_check()
    ubuntu_version = int(get_series().split(".")[0])
    watchdog_config_ready = True

    if (ubuntu_version >= 20) or (on_ubuntucore()):
        if not systemd_wdt_configured:
            print("systemd watchdog should be enabled but reset timeout: "
                  "{}".format(runtime_watchdog_usec))
            watchdog_config_ready = False
        if wdt_service_configured:
            print("found unexpected active watchdog.service unit")
            watchdog_config_ready = False
        if watchdog_config_ready:
            print("systemd watchdog enabled, reset timeout: {}".format(
                runtime_watchdog_usec))
            print("watchdog.service is not active")
    else:
        if systemd_wdt_configured:
            print("systemd watchdog should not be enabled but reset timeout: "
                  "{}".format(runtime_watchdog_usec))
            watchdog_config_ready = False
        if not wdt_service_configured:
            print("watchdog.service unit does not report as active")
            watchdog_config_ready = False
        if watchdog_config_ready:
            print("systemd watchdog disabled")
            print("watchdog.service active")

    raise SystemExit(not watchdog_config_ready)


if __name__ == "__main__":
    main()
