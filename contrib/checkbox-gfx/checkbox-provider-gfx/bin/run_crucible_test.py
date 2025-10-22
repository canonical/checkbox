#!/usr/bin/env python3
"""
Run a Crucible test string and evaluate pass/fail based on stdout.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Optional


SUCCESS_MARKER = "crucible: info   : fail 0"


def run_crucible(
    test_string: str,
    *,
    crucible_dir: Path = Path("/usr/local/checkbox-gfx/crucible"),
    xdg_runtime_dir: str = "/run/user/1000",
    out_path: Path = Path("/tmp/crucible_out.txt"),
    use_fork: bool = True,
) -> bool:
    """
    Execute crucible with the given test string, capture stdout to out_path,
    print it to stdout, then return True if success marker is present.
    """
    cmd = ["./bin/crucible", "run"]
    if use_fork:
        cmd.append("--fork")
    cmd.append(test_string)

    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = xdg_runtime_dir

    completed: Optional[subprocess.CompletedProcess[str]] = None
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(crucible_dir),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

        # Write to file
        out_path.write_text(completed.stdout, encoding="utf-8")

        print(out_path.read_text(encoding="utf-8"), end="")

        # Determine pass/fail by presence of the exact success marker
        passed = SUCCESS_MARKER in completed.stdout
        return passed

    finally:
        # cleanup
        try:
            if out_path.exists():
                out_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Crucible tests with pass/fail parsing."
    )
    parser.add_argument(
        "test_string", help="Test string to pass to `crucible run`."
    )
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
    parser.add_argument(
        "--out-path",
        type=Path,
        default=Path("/tmp/crucible_out.txt"),
        help="Path to write temporary crucible output.",
    )
    args = parser.parse_args()

    passed = run_crucible(
        args.test_string,
        crucible_dir=args.crucible_dir,
        xdg_runtime_dir=args.xdg_runtime_dir,
        out_path=args.out_path,
        use_fork=not args.no_fork,
    )

    if passed:
        print("The test indicates no test failures. Passing test!")
        raise SystemExit(0)
    else:
        print("Non-zero test failure value. Test failed!", file=os.sys.stderr)
        raise SystemExit(1)
