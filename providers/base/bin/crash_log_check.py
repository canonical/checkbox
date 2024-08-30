from datetime import datetime
import os
from subprocess import run, PIPE
import sys
import typing as T


def get_boot_time() -> datetime:
    return datetime.strptime(
        run(["uptime", "-s"], stdout=PIPE, encoding="utf-8").stdout.strip(),
        "%Y-%m-%d %H:%M:%S",
    )


def get_crash_logs() -> T.List[str]:
    boot_time = get_boot_time()
    crash_files_of_this_boot = []

    for crash_file in os.listdir("/var/crash"):
        print(crash_file)
        file_stats = os.stat("/var/crash/{}".format(crash_file))
        last_modified_time = max(
            file_stats.st_atime, file_stats.st_mtime, file_stats.st_ctime
        )  # whichever timestamp is the latest

        if datetime.fromtimestamp(last_modified_time) >= boot_time:
            crash_files_of_this_boot.append(crash_file)

    return crash_files_of_this_boot


def main():
    crash_files = get_crash_logs()

    if len(crash_files) == 0:
        print("[ OK ] No crash files found in /var/crash")
        return 0

    print(
        "[ ERROR ] Found the following crash files of this boot",
        file=sys.stderr,
    )
    for file in crash_files:
        print(file, file=sys.stderr)

    return 1


if __name__ == "__main__":
    exit(main())
