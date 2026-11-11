#!/usr/bin/env python3

import os
from subprocess import DEVNULL, check_output, run


def get_blacklist():
    # Please include a comment as to why something is globally blacklisted
    global_blacklist = [
        # We are unable to get these services fixed after years of trying
        "plymouth-start.service",
        "plymouth-show-run.service",
    ]
    blacklist = (
        global_blacklist + os.getenv("IGNORED_SERVICES_FAILING", "").split()
    )
    return blacklist


def filter_blacklisted(failed_units: list) -> list:
    blacklist = get_blacklist()
    print("Blacklisted services:")
    print("-", "\n- ".join(blacklist))
    print()
    to_r = []
    ignored = []
    for failed_unit in failed_units:
        if any(blacklisted in failed_unit for blacklisted in blacklist):
            ignored.append(failed_unit)
        else:
            to_r.append(failed_unit)
    if ignored:
        print("Ignoring failing services (blacklisted): ")
        print("-", "\n- ".join(ignored))
        print()
    return to_r


def main():
    failed_units = check_output(
        [
            "systemctl",
            "--system",
            "--no-ask-password",
            "--no-pager",
            "--no-legend",
            "list-units",
            "--state=failed",
            "--plain",
        ],
        universal_newlines=True,
    )
    failed_units = filter_blacklisted(failed_units.splitlines())
    count = len(failed_units)
    print(f"Found {count} failed units")
    if count == 0:
        raise SystemExit()

    print("\nFailed units:")
    print("-", "\n- ".join(failed_units))
    for unit in failed_units:
        service = unit.split()[0]
        print(f"\nLogs for {service}:")
        run(
            ["journalctl", "--no-pager", "-n", "50", "-u", service],
            stdin=DEVNULL,
        )
    raise SystemExit(1)


if __name__ == "__main__":
    main()
