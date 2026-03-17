#!/usr/bin/env python3
import argparse
import json
import platform
import subprocess

from checkbox_ng.support.release_info import get_release_info
from checkbox_ng.support.parsers.meminfo import MeminfoParser
from checkbox_ng.support.parsers.udevadm import parse_udevadm_output
from checkbox_ng.support.parsers import _json_fallback
from checkbox_ng.support.snap_utils.snapd import Snapd

"""
Device Information Collector

Script that collects information about the device under test and returns it
as JSON.
"""


def get_kernel_cmdline(cmdline_path="/proc/cmdline") -> str:
    with open(cmdline_path) as fp:
        cmdline = fp.read().strip()
    return cmdline


def get_devices():
    cmd = ["udevadm", "info", "--export-db"]
    udevadm_output = subprocess.check_output(cmd, universal_newlines=True)
    devices = parse_udevadm_output(udevadm_output)
    return devices


def get_debian_packages():
    cmd = ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n"]
    output = subprocess.check_output(cmd, universal_newlines=True)
    packages = []
    for line in output.splitlines():
        name, version, arch = line.split("\t")
        pkg = {"name": name, "version": version, "architecture": arch}
        packages.append(pkg)
    return packages


def get_meminfo():
    return MeminfoParser().run()


def get_snap_packages():
    return Snapd().list()


def get_uname():
    return {
        "system": platform.system(),
        "node": platform.node(),
        "kernel": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Collect device information as JSON"
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True
    subparsers.add_parser(
        "kernel_cmdline", help="Return kernel command line information"
    )
    subparsers.add_parser(
        "devices", help="Return devices found by the udeadvm parser"
    )
    subparsers.add_parser(
        "debian_packages", help="Return installed package information"
    )
    subparsers.add_parser(
        "distribution",
        help="Return information about the Linux distribution being used",
    )
    subparsers.add_parser("memory", help="Return memory information")
    subparsers.add_parser(
        "snaps", help="Return information about installed Snaps"
    )
    subparsers.add_parser("uname", help="Return uname information")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    command_map = {
        "distribution": get_release_info,
        "kernel_cmdline": get_kernel_cmdline,
        "devices": get_devices,
        "debian_packages": get_debian_packages,
        "memory": get_meminfo,
        "snaps": get_snap_packages,
        "uname": get_uname,
    }

    if args.command:
        getter = command_map[args.command]
        print(
            json.dumps(
                getter(), indent=4, sort_keys=True, default=_json_fallback
            )
        )


if __name__ == "__main__":
    main()
