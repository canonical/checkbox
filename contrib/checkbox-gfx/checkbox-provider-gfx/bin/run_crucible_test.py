#!/usr/bin/env python3
"""
Run a Crucible test string and evaluate pass/fail based on stdout.
"""

import argparse
import os
import subprocess
from pathlib import Path

SUCCESS_MARKER = "crucible: info   : fail 0"


def run_crucible(
    test_string: str,
    crucible_dir: Path = Path("/usr/local/checkbox-gfx/crucible"),
    xdg_runtime_dir: str = "/run/user/1000",
    use_fork: bool = True,
):
    cmd = ["./bin/crucible", "run"]
    if use_fork:
        cmd.append("--fork")
    cmd.append(test_string)

    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = xdg_runtime_dir

    output = ""
    try:
        output = subprocess.check_output(cmd, cwd=str(crucible_dir), env=env, text=True)

        print(output)
    except subprocess.CalledProcessError as e:
        print("Command failed with code", e.returncode)
        print("Failure output:\n", e.output)

    # Determine pass/fail by presence of the exact success marker
    if SUCCESS_MARKER in output:
        print("The test indicates no test failures. Passing test!")
    else:
        print("Non-zero test failure value. Test failed!", file=os.sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Crucible tests with pass/fail parsing."
    )
    parser.add_argument("test_string", help="Test string to pass to `crucible run`.")
    parser.add_argument(
        "--no-fork",
        action="store_true",
        help="Run without --fork (for debugging).",
    )
    parser.add_argument(
        "--crucible-dir",
        type=Path,
        default=Path("/usr/local/checkbox-gfx/crucible"),
        help="Directory containing ./bin/crucible.",
    )
    parser.add_argument(
        "--xdg-runtime-dir",
        default="/run/user/1000",
        help="Value for XDG_RUNTIME_DIR.",
    )
    args = parser.parse_args()

    run_crucible(
        args.test_string,
        crucible_dir=args.crucible_dir,
        xdg_runtime_dir=args.xdg_runtime_dir,
        use_fork=not args.no_fork,
    )
