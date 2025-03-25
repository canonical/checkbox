#!/usr/bin/env python3

import json
import os
import subprocess


def get_boot_ids():
    cmd = ["journalctl", "--list-boots", "--output", "json"]
    boots = json.loads(subprocess.check_output(cmd, universal_newlines=True))
    boot_ids = [boot["boot_id"] for boot in boots]
    return boot_ids


def get_kernel_version_from_journal(boot_id):
    # Capture first line of journal (info about booted Linux kernel)
    cmd = ["journalctl", "-k", "-b", boot_id, "-n", "+1", "--output", "json"]
    journalctl_log = json.loads(
        subprocess.check_output(cmd, universal_newlines=True)
    )
    linux_line = journalctl_log["MESSAGE"]
    # "Linux version 6.11.0-19-generic ..."
    linux_version = linux_line.split()[2]
    return linux_version


def check_error(boot_id, error="Microcode SW error detected"):
    journal = subprocess.check_output(["journalctl", "-k", "-b", boot_id], universal_newlines=True)
    for line in journal.splitlines():
        if error in line:
            raise SystemExit("Microcode software error detected during boot {}.".format(boot_id))


def main(current_linux_version):
    boot_ids = get_boot_ids()
    for boot_id in boot_ids:
        linux_version = get_kernel_version_from_journal(boot_id)
        if linux_version == current_linux_version:
            check_error(boot_id)
    print("No microcode software errors detected.")


if __name__ == "__main__":
    current_linux_version = os.uname().release
    main(current_linux_version)
