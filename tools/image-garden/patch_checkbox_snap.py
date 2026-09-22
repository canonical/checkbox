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

METABOX_PROVIDER = (
    "metabox/metabox/metabox-provider",
    "metabox",
)
METABOX_PROVIDER_EXTRA = Path(__file__).resolve().parent / "metabox_provider"


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
    for provider_dir in sorted((repo / "providers").iterdir()):
        destination = snap_root / f"providers/checkbox-provider-{provider_dir.name}"
        if provider_dir.is_dir() and destination.is_dir():
            targets.append((provider_dir, destination))

    metabox_source, metabox_name = METABOX_PROVIDER
    targets.append(
        (
            repo / metabox_source,
            snap_root / f"providers/checkbox-provider-{metabox_name}",
        )
    )
    return targets


def sync_dirs(repo, snap_root):
    targets = python_package_targets(repo, snap_root) + provider_targets(
        repo, snap_root
    )
    for source, destination in targets:
        sync_dir(source, destination)

    metabox_dir = snap_root / "providers/checkbox-provider-metabox"
    sync_dir(METABOX_PROVIDER_EXTRA, metabox_dir)
    return [destination for _, destination in targets]


def repo_root(path):
    # Prefer the git top-level, so this can be invoked from any
    # subdirectory of a checkout. Spread syncs the repo without ".git",
    # so fall back to using the given path directly in that case.
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return Path(output.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return path.resolve()


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


def unsquash(snap_file, output_dir):
    subprocess.run(
        ["unsquashfs", "-d", str(output_dir), str(snap_file)],
        check=True,
    )


def patch_snap(
    *,
    snap=None,
    series=None,
    channel="edge",
    snap_file=None,
    output_dir=None,
    force=False,
    repo_root_path=None,
):
    repo = repo_root(repo_root_path or Path.cwd())
    name = snap or f"checkbox{series}"
    output_dir = (output_dir or Path(name)).resolve()

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
        unsquash(snap_file.resolve(), output_dir)
    else:
        with tempfile.TemporaryDirectory() as work_dir:
            downloaded = download_snap(name, channel, Path(work_dir))
            unsquash(downloaded, output_dir)

    synced = sync_dirs(repo, output_dir)

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
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
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
        repo_root_path=parsed.repo_root,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
