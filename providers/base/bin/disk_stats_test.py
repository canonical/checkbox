#!/usr/bin/env python3
"""
Simple script to gather some data about a disk to verify it's seen by the OS
and is properly represented.
"""

import argparse
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "disk",
        nargs="?",
        default="sda",
        help="disk name to test (default: %(default)s)",
    )
    args = parser.parse_args()
    disk = args.disk
    partitions_path = Path("/proc/partitions")
    diskstats_path = Path("/proc/diskstats")
    block_path = Path("/sys/block") / disk
    stat_path = block_path / "stat"

    partitions = partitions_path.read_text(encoding="utf-8").splitlines()
    if not any(disk in line.split() for line in partitions):
        raise SystemExit(f"ERROR: Disk {disk} not found in /proc/partitions")

    diskstats = diskstats_path.read_text(encoding="utf-8").splitlines()
    try:
        proc_stat_begin = next(
            line.strip() for line in diskstats if disk in line.split()
        )
    except StopIteration:
        raise SystemExit(f"ERROR: Disk {disk} not found in /proc/diskstats")

    if not block_path.exists():
        raise SystemExit(f"ERROR: Disk {disk} not found in /sys/block")

    if not stat_path.is_file() or stat_path.stat().st_size == 0:
        raise SystemExit(
            "ERROR: stat is either empty or "
            f"nonexistent in /sys/block/{disk}/"
        )

    sys_stat_begin = stat_path.read_text(encoding="utf-8").strip()

    # This is just to generate some disk activity
    subprocess.run(
        ["hdparm", "-t", f"/dev/{disk}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    time.sleep(5)

    diskstats = diskstats_path.read_text(encoding="utf-8").splitlines()
    try:
        proc_stat_end = next(
            line.strip() for line in diskstats if disk in line.split()
        )
    except StopIteration:
        raise SystemExit("ERROR: Disk went missing from /proc/diskstats")
    sys_stat_end = stat_path.read_text(encoding="utf-8").strip()

    if proc_stat_begin == proc_stat_end:
        raise SystemExit(
            "ERROR: Stats in /proc/diskstats did not change\n"
            f"output: {proc_stat_begin}\n"
            f"output: {proc_stat_end}"
        )

    if sys_stat_begin == sys_stat_end:
        raise SystemExit(
            f"ERROR: Stats in /sys/block/{disk}/stat did not change\n"
            f"output: {sys_stat_begin}\noutput: {sys_stat_end}"
        )

    print(f"PASS: Finished testing stats for {disk}")


if __name__ == "__main__":
    main()
