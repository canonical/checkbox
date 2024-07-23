#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Authors:
#   Patrick Chang <patrick.chang@canonical.com>
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
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
import subprocess
import os


def runcmd(command):
    ret = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
    )
    return ret


def test_uart_by_serialcheck(soc):
    base_path = os.environ.get("PLAINBOX_SESSION_SHARE", "/tmp")
    file_path = "{}/binary".format(base_path)
    runcmd(["dd if=/dev/urandom of={} count=1 bs=4096".format(file_path)])

    golden_msg = (
        "cts: 0 dsr: 0 rng: 0 dcd: 0 rx: 12288"
        " tx: 12288 frame 0 ovr 0 par: 0 brk: 0 buf_ovrr: 0"
    )
    print("Golden Sample:")
    print(golden_msg)

    tty_node = "ttyS1" if soc == "mt8395" else "ttyS2"
    cmd = "genio-test-tool.serialcheck -d /dev/{} -f {} -m d -l 3 -b {}"

    available_baudrate = [
        3000000,
        2000000,
        921600,
        576000,
        460800,
        230400,
        115200,
        57600,
        38400,
        19200,
        9600,
        4800,
        2400,
        1200,
        600,
        300,
        110,
    ]

    fail = False
    for br in available_baudrate:
        print("\n" + "*" * 80)
        print("Testing baudrate: {}\n".format(br))
        ret = runcmd([cmd.format(tty_node, file_path, br)])
        print(ret.stdout)
        if ret.returncode != 0 or ret.stdout.split("\n")[-2] != golden_msg:
            fail = True
            print("Fail: the output doesn't match the golden sample")

    if fail:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "soc",
        help="SoC type. e.g mt8395",
        choices=["mt8395", "mt8390", "mt8365"],
    )
    args = parser.parse_args()
    test_uart_by_serialcheck(args.soc)


if __name__ == "__main__":
    main()
