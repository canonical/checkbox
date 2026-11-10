#!/usr/bin/env python3

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import patch_checkbox_snap

PROJECT_DIR = Path(".")
SUPPORTED_SERIES = ("18", "20", "22", "24", "26")


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("launcher", type=Path)
    parser.add_argument("--series", choices=SUPPORTED_SERIES, default="24")
    parser.add_argument("--channel", default="edge")
    parser.add_argument("--snap-file", type=Path)
    return parser


def run(args):
    if not args.launcher.is_file():
        raise FileNotFoundError(f"launcher does not exist: {args.launcher}")

    if args.series not in SUPPORTED_SERIES:
        raise ValueError(f"invalid Ubuntu Core series: {args.series}")

    if args.snap_file and not args.snap_file.is_file():
        raise FileNotFoundError(f"snap file does not exist: {args.snap_file}")

    checkbox = f"checkbox{args.series}"
    run_dir = PROJECT_DIR / f"local_run_{args.series}"
    patched_snap = run_dir / checkbox
    staged_launcher = run_dir / "launcher.conf"
    artifacts_dir = run_dir / "artifacts"

    shutil.rmtree(artifacts_dir, ignore_errors=True)
    staged_launcher.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.launcher, staged_launcher)

    patch_checkbox_snap.main(
        snap=checkbox,
        channel=args.channel,
        output_dir=patched_snap,
        force=True,
        snap_file=args.snap_file,
    )

    # Run Image Garden from run_dir so its VM state (images, logs,
    # locks) is written under local_run_<series>/ instead of here.
    shutil.copy2(PROJECT_DIR / "spread.yaml", run_dir / "spread.yaml")
    shutil.copytree(
        PROJECT_DIR / "tests", run_dir / "tests", dirs_exist_ok=True
    )

    subprocess.run(
        [
            "image-garden.spread",
            "-vv",
            "-artifacts=artifacts",
            f"garden:ubuntu-core-{args.series}:tests/run-patched-snap",
        ],
        cwd=run_dir,
        check=True,
    )


def main(argv=None):
    run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
