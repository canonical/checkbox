#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys


def main():
    if len(sys.argv) < 2:
        print(sys.argv[0] + " [interface]")
        return 0

    kernel_version = subprocess.getoutput("uname -r").split(".")
    if int(kernel_version[0]) > 5 or int(kernel_version[1]) > 15:
        return 0

    _6g_start = 5945
    _6g_end = 7125

    data = subprocess.run(
        ["iw", sys.argv[1], "info"], capture_output=True, encoding="utf-8"
    )
    if data.returncode:
        print(sys.argv[1] + " is not valid wireless interface")
        return 0
    index = data.stdout[data.stdout.find("wiphy") + 6]
    data = subprocess.getoutput("iw phy" + index + " info").splitlines()
    for i, line in enumerate(data):
        if "Frequencies" in line:
            while data[i + 1].startswith("\t\t\t"):
                if "disabled" not in (data[i + 1]):
                    freq = int(data[i + 1].split()[1])
                    if freq > _6g_start and freq < _6g_end:
                        raise SystemExit(
                            "Contain 6Ghz band and Kernel not over 5.15"
                        )  # noqa: E501
                i = i + 1
    return 0


if __name__ == "__main__":
    main()
