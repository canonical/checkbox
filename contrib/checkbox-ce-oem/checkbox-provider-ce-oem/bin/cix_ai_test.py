#!/usr/bin/env python3

# Copyright 2026 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Run the CIX NOE tools shipped in the cix-ai-test package.

The tools often exit with 0 even when they fail, so the result is decided
from their output and not only from the return code.

Background and the scope of the supported tools: Jira CIXEE-186
(https://warthogs.atlassian.net/browse/CIXEE-186).
"""

import argparse
import contextlib
import os
import subprocess
import tempfile
from pathlib import Path

BIN_DIR = Path("/usr/share/cix/bin")
LIB_DIR = Path("/usr/share/cix/lib")
TESTDATA_DIR = Path("/usr/share/cix/testdata/npu/onnx_resnet50_3core")
DEVFREQ_GOVERNOR = Path("/sys/class/devfreq/CIXH4000:00/governor")
PASS_LINE = "Test Result Check PASS"

TOOLS = (
    "benchmark",
    "batch",
    "dfs",
    "flush_job",
    "mthread",
    "multi_model",
    "profiler",
    "time_cost",
)

# Lines that must be present in the output, besides the PASS_LINE count.
EXPECTED_LINES = {
    "profiler": ["get profiler tensor success"],
}
# Tools that do not print PASS_LINE at all.
NO_PASS_LINE = ("flush_job", "multi_model", "profiler", "time_cost")


def check_env(tool: str, testdata: Path) -> Path:
    binary = BIN_DIR / f"noe_{tool}"
    if not binary.is_file():
        raise SystemExit(
            f"ENV ERROR: {binary} not found, install the cix-ai-test package"
        )
    for name in ("noe.cix", "input0.bin", "output.bin"):
        if not (testdata / name).is_file():
            raise SystemExit(f"ENV ERROR: {testdata / name} not found")
    return binary


def build_command(
    binary: Path, args: argparse.Namespace, dump_dir: Path
) -> "list[str]":
    testdata = Path(args.testdata)
    command = [
        str(binary),
        "-b",
        str(testdata / "noe.cix"),
        "-i",
        str(testdata / "input0.bin"),
        "-c",
        str(testdata / "output.bin"),
        "-d",
        str(dump_dir),
    ]
    if args.tool == "benchmark":
        command += ["-m", str(args.frames)]
    return command


def verify(
    tool: str, output: str, returncode: int, frames: int
) -> "list[str]":
    """Return the list of problems found, empty if the run is good."""
    problems = []
    if returncode != 0:
        problems.append(f"exit code is {returncode}")
    for line in output.splitlines():
        if "[Err]" in line or "FAIL" in line:
            problems.append(f"error in output: {line.strip()}")
    for expected in EXPECTED_LINES.get(tool, []):
        if expected not in output:
            problems.append(f"missing expected line: '{expected}'")
    passes = output.count(PASS_LINE)
    if tool not in NO_PASS_LINE and passes == 0:
        problems.append(f"'{PASS_LINE}' not found")
    if tool == "benchmark" and passes != frames:
        problems.append(f"{passes} frames passed, expected {frames}")
    return problems


@contextlib.contextmanager
def restore_governor():
    """noe_dfs needs the 'userspace' governor, put the original back after."""
    original = DEVFREQ_GOVERNOR.read_text().strip()
    print(f"Original devfreq governor: {original}")
    try:
        DEVFREQ_GOVERNOR.write_text("userspace")
        yield
    finally:
        DEVFREQ_GOVERNOR.write_text(original)
        print(f"Restored devfreq governor to: {original}")


def build_env() -> "dict[str, str]":
    """Prepend CIX_NOE_LIB_DIR (default LIB_DIR) to LD_LIBRARY_PATH."""
    lib_dir = os.environ.get("CIX_NOE_LIB_DIR") or str(LIB_DIR)
    paths = [lib_dir]
    if os.environ.get("LD_LIBRARY_PATH"):
        paths.append(os.environ["LD_LIBRARY_PATH"])
    return {**os.environ, "LD_LIBRARY_PATH": ":".join(paths)}


def run_tool(args: argparse.Namespace) -> None:
    testdata = Path(args.testdata)
    print(f"tool: noe_{args.tool}")
    print(f"testdata: {testdata}")
    print(f"frames: {args.frames}")
    binary = check_env(args.tool, testdata)
    if args.tool == "dfs" and os.geteuid() != 0:
        raise SystemExit("ENV ERROR: noe_dfs must run as root")
    env = build_env()
    print(f"LD_LIBRARY_PATH: {env['LD_LIBRARY_PATH']}")
    with contextlib.ExitStack() as stack:
        dump_dir = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        if args.tool == "dfs":
            stack.enter_context(restore_governor())
        command = build_command(binary, args, dump_dir)
        print(f"command: {' '.join(command)}", flush=True)
        try:
            result = subprocess.run(
                command,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                timeout=args.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            print(exc.stdout or "")
            raise SystemExit(
                f"noe_{args.tool} timed out after {args.timeout}s"
            )
    print(result.stdout)
    problems = verify(args.tool, result.stdout, result.returncode, args.frames)
    if problems:
        raise SystemExit(
            f"noe_{args.tool} FAILED:\n"
            + "\n".join(f"- {p}" for p in problems)
        )
    print(f"noe_{args.tool} PASSED")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=TOOLS)
    parser.add_argument("--testdata", default=str(TESTDATA_DIR))
    parser.add_argument("--frames", type=int, default=1000)
    parser.add_argument("--timeout", type=int, default=600)
    run_tool(parser.parse_args())


if __name__ == "__main__":
    main()
