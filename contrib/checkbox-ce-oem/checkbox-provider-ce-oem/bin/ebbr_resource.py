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


def parse_show_tests(output, header):
    """Return (name, description) of the tests listed under header."""
    lines = output.split("\n")
    if header not in lines:
        return []
    tests = []
    for line in lines[lines.index(header) + 1 :]:
        if line == "":
            break
        c = line.split()
        tests.append((c[0], " ".join(c[1:-1])))
    return tests


def main():
    fwts_ret = runcmd(["fwts --ebbr --show-tests"])
    ebbr_tests = parse_show_tests(fwts_ret.stdout, "EBBR tests:")
    if not ebbr_tests:
        raise SystemExit(
            "No EBBR tests found in 'fwts --ebbr --show-tests' output:\n"
            + fwts_ret.stdout
            + fwts_ret.stderr
        )
    # Utilities print no test summary, so their log can't be checked
    utilities = {
        name
        for name, _ in parse_show_tests(
            runcmd(["fwts --utils --show-tests"]).stdout, "Utilities:"
        )
    }
    for case_name, description in ebbr_tests:
        fwts_type = "Utilities" if case_name in utilities else "EBBR"
        print(f"case: {case_name}")
        print(f"description: {description}")
        print(f"fwts_type: {fwts_type}\n")


if __name__ == "__main__":
    main()
