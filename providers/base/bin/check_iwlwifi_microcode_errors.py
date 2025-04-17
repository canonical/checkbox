#!/usr/bin/env python3

import json
import itertools
import subprocess


def text_fallback_boots_parser(boots_txt):
    boots_lines = boots_txt.splitlines()
    boots_lines_items = map(str.split, boots_lines)
    # for malformed lines with just one item, lets set the boot id to none
    boots_lines_items = (
        itertools.chain(x, [None, None]) for x in boots_lines_items
    )
    return [
        {"boot_id": boot_id}
        for (boot_number, boot_id, *_) in boots_lines_items
        if boot_id
    ]


def get_boot_ids():
    cmd = ["journalctl", "--list-boots", "--output", "json"]
    boots_txt = subprocess.check_output(cmd, universal_newlines=True)
    try:
        boots = json.loads(boots_txt)
    except json.decoder.JSONDecodeError:
        # some ancient versions of journalctl ignore the --output flag
        # See: https://github.com/canonical/checkbox/issues/1875
        boots = text_fallback_boots_parser(boots_txt)
    boot_ids = [boot["boot_id"] for boot in boots]
    return boot_ids


def get_kernel_version_from_journal(boot_id):
    """
    Return the first occurence of the Linux version in journal from boot
    ``boot_id``, or None if nothing was found.
    """
    cmd = ["journalctl", "-k", "-b", boot_id, "--output", "json"]
    journalctl_log = subprocess.check_output(cmd, universal_newlines=True)
    journalctl_lines = journalctl_log.splitlines()
    for line in journalctl_lines:
        j = json.loads(line)
        msg = j.get("MESSAGE")
        # "Linux version 6.11.0-19-generic ..."
        if msg.startswith("Linux version"):
            return msg.split()[2]
    return None


def check_error(boot_id, error="Microcode SW error detected"):
    journal = subprocess.check_output(
        ["journalctl", "-k", "-b", boot_id], universal_newlines=True
    )
    for line in journal.splitlines():
        if error in line:
            raise SystemExit(
                "Microcode software error detected during boot {}.".format(
                    boot_id
                )
            )


def main():
    boot_ids = get_boot_ids()
    current_linux_version = get_kernel_version_from_journal(boot_ids[-1])
    for boot_id in boot_ids:
        linux_version = get_kernel_version_from_journal(boot_id)
        if linux_version == current_linux_version:
            check_error(boot_id)
    print("No microcode software errors detected.")


if __name__ == "__main__":
    main()
