#!/usr/bin/env python3

import subprocess


def runcmd(command):
    ret = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        timeout=1,
    )
    return ret


def main():
    fwts_ret = runcmd(["fwts --ebbr --show-tests"])
    fwts_line_split = fwts_ret.stdout.split("\n")
    ebbr_tests_idx = fwts_line_split.index("EBBR tests:")

    for i in range(ebbr_tests_idx + 1, len(fwts_line_split)):
        line = fwts_line_split[i]
        if line == "":
            return
        c = line.split()
        case_name = c[0]
        description = " ".join(c[1:-1])
        print(f"case: {case_name}")
        print(f"description: {description}\n")


if __name__ == "__main__":
    main()
