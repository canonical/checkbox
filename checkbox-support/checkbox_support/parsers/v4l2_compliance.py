#! /usr/bin/python3

import re
from shutil import which
import subprocess as sp
import typing as T


def get_test_name_from_line(line: str) -> str:
    assert line.startswith("test"), "This line doesn't describe a test output"
    return line.split("test ", maxsplit=1)[1].split(": ", maxsplit=1)[0]


# see the summary dict literal for actual keys
Summary = T.Dict[str, T.Union[int, str]]
# see the details dict literal for actual keys
Details = T.Dict[str, T.List[str]]


def parse_v4l2_compliance(device="/dev/video0") -> T.Tuple[Summary, Details]:
    assert which("v4l2-compliance")
    out = sp.run(
        ["v4l2-compliance", "-d", device, "-C", "never"],
        universal_newlines=True,
        stdout=sp.PIPE,
    )

    lines = []  # type: list[str]
    for line in out.stdout.splitlines():
        clean_line = line.strip()
        if clean_line != "":
            lines.append(clean_line)

    pattern = (
        r"Total for (.*): (.*), Succeeded: (.*), Failed: (.*), Warnings: (.*)"
    )
    match_output = re.match(pattern, lines[-1])

    summary = {}
    if match_output:
        summary = {
            "device_name": match_output.group(1),
            "total": int(match_output.group(2)),
            "succeeded": int(match_output.group(3)),
            "failed": int(match_output.group(4)),
            "warnings": int(match_output.group(5)),
        }

    details = {
        "succeeded": [],
        "failed": [],
        "not_supported": [],
    }  # type: dict[str, list[str]]

    for line in lines:
        if line.endswith(": OK"):
            details["succeeded"].append(get_test_name_from_line(line))
        elif line.endswith(": OK (Not Supported)"):
            details["not_supported"].append(get_test_name_from_line(line))
        elif line.endswith(": FAIL"):
            details["failed"].append(get_test_name_from_line(line))

    assert (
        len(details["succeeded"]) + len(details["not_supported"])
        == summary["succeeded"]
    )
    assert len(details["failed"]) == summary["failed"]

    return summary, details


if __name__ == "__main__":
    summary, details = parse_v4l2_compliance()
    print(summary)
    for k, v in details.items():
        print(k, len(v))
        print("\t", v)
