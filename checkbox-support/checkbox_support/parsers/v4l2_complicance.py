#! /usr/bin/python3

import re
from shutil import which
import subprocess as s
from typing import Dict, Tuple, Union


def get_test_name_from_line(line: str) -> str:
    assert line.startswith("test"), "This line doesn't describe a test output"
    return line.split("test ", maxsplit=1)[1].split(": ", maxsplit=1)[0]


def parse_v4l2_compliance() -> Union[Tuple[Dict, Dict], None]:
    if not which("v4l2-compliance"):
        return None
    out = s.run(["v4l2-compliance"], stdout=s.PIPE)

    lines = []  # type: list[str]
    for line in out.stdout.decode().splitlines():
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
        print(summary)

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
