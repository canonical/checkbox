#!/usr/bin/env python3
import json
import platform
import subprocess

from checkbox_ng.support.release_info import get_release_info
from checkbox_ng.support.parsers.meminfo import MeminfoParser
from checkbox_ng.support.parsers.udevadm import parse_udevadm_output
from checkbox_ng.support.parsers import _json_fallback


"""
Device Information Collector

This script aggregates system metadata (OS release, kernel parameters,
hardware via udev and installed packages) into a single JSON object.
"""


def get_kernel_cmdline(cmdline_path="/proc/cmdline"):
    with open(cmdline_path) as fp:
        cmdline = fp.read().strip()
    return cmdline


def get_udevadm_db():
    cmd = ["udevadm", "info", "--export-db"]
    return subprocess.check_output(cmd, universal_newlines=True)


def get_packages():
    cmd = ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n"]
    output = subprocess.check_output(cmd, universal_newlines=True)
    packages = []
    for line in output.splitlines():
        name, version, arch = line.split("\t")
        pkg = {"name": name, "version": version, "architecture": arch}
        packages.append(pkg)
    return packages


def main():
    mem_info = MeminfoParser().run()
    udevadm_output = get_udevadm_db()
    device_info = {
        "distribution": get_release_info(),
        "uname": {
            "system": platform.system(),
            "node": platform.node(),
            "kernel": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine(),
        },
        "memory": mem_info,
        "kernel_cmdline": get_kernel_cmdline(),
        "devices": parse_udevadm_output(udevadm_output),
        "packages": get_packages()
    }
    print(json.dumps(
                     device_info,
                     indent=4,
                     sort_keys=True,
                     default=_json_fallback
                 )
      )


if __name__ == "__main__":
    main()
