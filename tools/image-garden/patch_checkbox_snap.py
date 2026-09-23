#!/usr/bin/env python3

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PYTHON_PACKAGES = {
    "checkbox-ng/checkbox_ng": "checkbox_ng",
    "checkbox-ng/plainbox": "plainbox",
    "checkbox-support/checkbox_support": "checkbox_support",
}

# This script lives at "<repo>/tools/image-garden/patch_checkbox_snap.py",
# both in a real checkout and in a Spread-synced guest copy, so the repo
# root can always be derived from the script's own location.
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent


def sync_dir(source, destination):
    """Overlay source files on destination."""
    shutil.copytree(source, destination, dirs_exist_ok=True)


def python_package_targets(repo, snap_root):
    targets = []
    for source, name in PYTHON_PACKAGES.items():
        # Make sure the source directory exists in the repository
        source_dir = repo / source
        if not source_dir.is_dir():
            raise FileNotFoundError(source_dir)
        # Get the destination directories in the snap
        matches = list(snap_root.rglob(name))
        if not matches:
            raise ValueError(f"no {name} found in {snap_root}")
        targets += [(source_dir, match) for match in matches]
    return targets


def provider_targets(repo, snap_root):
    targets = []
    # Get the list of providers
    for provider_dir in sorted((repo / "providers").iterdir()):
        dest = snap_root / f"providers/checkbox-provider-{provider_dir.name}"
        if provider_dir.is_dir() and dest.is_dir():
            targets.append((provider_dir, dest))

    # Append also the metabox provider
    targets.append(
        (
            repo / "metabox/metabox/metabox-provider",
            snap_root / "providers/checkbox-provider-metabox",
        )
    )
    return targets


def sync_dirs(repo, snap_root):
    targets = python_package_targets(repo, snap_root) + provider_targets(
        repo, snap_root
    )
    for source, destination in targets:
        sync_dir(source, destination)

    metabox_src = SCRIPT_DIR / "metabox_provider"
    metabox_dest = snap_root / "providers/checkbox-provider-metabox"
    sync_dir(metabox_src, metabox_dest)
    return [destination for _, destination in targets]


def download_snap(name, channel, work_dir):
    basename = f"{name}-{channel.replace('/', '-')}"
    snap_file = work_dir / (basename + ".snap")
    subprocess.run(
        [
            "snap",
            "download",
            name,
            f"--channel={channel}",
            f"--basename={basename}",
        ],
        cwd=work_dir,
        check=True,
    )
    return snap_file


def patch_snap(
    *,
    snap=None,
    series=None,
    channel="edge",
    snap_file=None,
    output_dir=None,
    force=False,
):
    name = snap or f"checkbox{series}"
    output_dir = output_dir or Path(name)

    # Create the output directory if it doesn't exist. Only remove it if
    # --force is specified.
    if output_dir.exists():
        if not force:
            raise FileExistsError(
                f"{output_dir} already exists, use --force to replace it"
            )
        shutil.rmtree(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    # Unsquash the snap into the output directory.
    if snap_file:
        source = snap_file
        subprocess.run(
            ["unsquashfs", "-d", str(output_dir), str(source)],
            check=True,
        )
    else:
        with tempfile.TemporaryDirectory() as work_dir:
            source = download_snap(name, channel, Path(work_dir))
            subprocess.run(
                ["unsquashfs", "-d", str(output_dir), str(source)],
                check=True,
            )

    synced = sync_dirs(REPO_ROOT, output_dir)

    print(f"Patched {output_dir}")
    print(f"Synced directories: {len(synced)}")
    for path in synced:
        print(f"  + {path.relative_to(output_dir)}")


def build_parser():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--snap", help="Runtime snap name, e.g. checkbox24.")
    group.add_argument("--series", help="Ubuntu Core series, e.g. 24.")
    parser.add_argument("--channel", default="edge")
    parser.add_argument(
        "--snap-file",
        type=Path,
        help="Use this local .snap file instead of downloading one.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Where to unsquash the patched snap. Defaults to ./<snap-name>.",
    )
    parser.add_argument("--force", action="store_true")
    return parser


def main(args=None, **kwargs):
    if kwargs:
        if args is not None:
            raise ValueError("pass either args or keyword arguments, not both")
        patch_snap(**kwargs)
        return

    parser = build_parser()
    parsed = parser.parse_args(args)
    patch_snap(
        snap=parsed.snap,
        series=parsed.series,
        channel=parsed.channel,
        snap_file=parsed.snap_file,
        output_dir=parsed.output_dir,
        force=parsed.force,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
