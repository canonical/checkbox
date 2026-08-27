#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Isaac Yang <isaac.yang@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
"""Discover and run prebuilt NVIDIA cuda-samples binaries.

This tool is prebuilt-only: it never clones or builds cuda-samples.
The tree is expected to be cloned at the tag matching the installed
CUDA version and built BEFORE Checkbox runs (by provisioning on
classic, or shipped inside a snap on Ubuntu Core).  See the suite
README in units/cuda/ for the setup contract.

Subcommands:
  list       print one Checkbox resource record per sample
             (category/name/path/skip/skip_reason)
  readiness  verify the tree exists, is built, and its git tag is the
             newest cuda-samples tag <= the nvidia-smi CUDA version
  run        run a single sample binary with a timeout
"""

import argparse
import glob
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile

DEFAULT_TIMEOUT = 300.0
CLASSIC_DEFAULT_ROOT = "/opt/nvidia/cuda-samples"
# Layout contract for the Ubuntu Core cuda-samples snap (OEMQA-6850):
# the snap must expose the prebuilt tree at <snap>/cuda-samples.
SNAP_ROOT_GLOB = "/snap/*/current/cuda-samples"


def candidate_roots():
    """Return cuda-samples root candidates in resolution order.

    An explicitly configured root (CUDA_SAMPLES_PATH) is authoritative:
    it is the only candidate, so a wrong path fails loudly instead of
    silently testing another tree.
    """
    env_root = os.environ.get("CUDA_SAMPLES_PATH")
    if env_root:
        return [env_root]
    return [CLASSIC_DEFAULT_ROOT] + sorted(glob.glob(SNAP_ROOT_GLOB))


def resolve_root(path=None):
    """Return the first candidate containing a Samples/ directory."""
    candidates = [path] if path else candidate_roots()
    for candidate in candidates:
        if os.path.isdir(os.path.join(candidate, "Samples")):
            return os.path.realpath(candidate)
    raise SystemExit(
        "No cuda-samples tree found (tried: {}). This suite is "
        "prebuilt-only: clone and build cuda-samples before running "
        "Checkbox, or point CUDA_SAMPLES_PATH at the tree.".format(
            ", ".join(candidates)
        )
    )


# Sample directory names are plain identifiers; anything else is build
# machinery (an in-source cmake build drops CMakeFiles/ into every
# category) or would break the generated job ids and requires
# expressions.
_SAMPLE_NAME_RE = re.compile(r"^[A-Za-z0-9_+-]+$")


def _is_sample_dir(name):
    return name != "CMakeFiles" and _SAMPLE_NAME_RE.match(name)


# This category nests samples one level deeper, per platform:
# Samples/8_Platform_Specific/Tegra/<sample> (upstream layout since the
# cmake era).  Such samples get "8_Platform_Specific/Tegra" as their
# category.
NESTED_CATEGORY = "8_Platform_Specific"


def _sample_dirs(parent):
    for name in sorted(os.listdir(parent)):
        if os.path.isdir(os.path.join(parent, name)) and _is_sample_dir(name):
            yield name


def discover_samples(root):
    """Yield (category, name) for every sample source directory."""
    samples_dir = os.path.join(root, "Samples")
    for category in _sample_dirs(samples_dir):
        category_dir = os.path.join(samples_dir, category)
        if category == NESTED_CATEGORY:
            for platform_dir in _sample_dirs(category_dir):
                nested = os.path.join(category_dir, platform_dir)
                for name in _sample_dirs(nested):
                    yield "{}/{}".format(category, platform_dir), name
        else:
            for name in _sample_dirs(category_dir):
                yield category, name


def binary_candidates(root, category, name):
    """Possible binary locations, covering both cuda-samples eras."""
    arch = platform.machine()
    return [
        # Makefile era (<= v12.5): binary built in the sample dir...
        os.path.join(root, "Samples", category, name, name),
        # ...and copied to the flat release dir.
        os.path.join(root, "bin", arch, "linux", "release", name),
        # cmake era (>= v13.0).
        os.path.join(root, "build", "Samples", category, name, name),
    ]


def find_binary(root, category, name):
    """Return the first existing executable for a sample, or None."""
    for candidate in binary_candidates(root, category, name):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _data_dir_path(name, context):
    """Resolve a bare list name in the provider data dir, or fail."""
    data_dir = os.environ.get("PLAINBOX_PROVIDER_DATA")
    if not data_dir:
        raise SystemExit(
            "{}={!r} is a bare name but PLAINBOX_PROVIDER_DATA is "
            "not set".format(context, name)
        )
    return os.path.join(data_dir, "cuda", name)


def _read_exclude_file(path):
    """Parse and validate one exclude-jobs JSON file into its dict."""
    try:
        with open(path) as stream:
            data = json.load(stream)
    except (OSError, ValueError) as exc:
        raise SystemExit("Cannot read exclude file {}: {}".format(path, exc))
    if not isinstance(data, dict) or not isinstance(
        data.get("excludes"), list
    ):
        raise SystemExit(
            "{}: expected an object with an 'excludes' list "
            "(see exclude_jobs.schema.json)".format(path)
        )
    unknown = set(data) - {"$schema", "excludes", "include"}
    if unknown:
        raise SystemExit(
            "{}: unknown top-level keys {} (allowed: excludes, "
            "include)".format(path, sorted(unknown))
        )
    for entry in data["excludes"]:
        if not isinstance(entry, dict):
            raise SystemExit(
                "{}: every exclude must be an object "
                "(bad entry: {!r})".format(path, entry)
            )
        unknown = set(entry) - {"name", "category", "reason"}
        if unknown:
            raise SystemExit(
                "{}: unknown exclude keys {} (bad entry: {!r})".format(
                    path, sorted(unknown), entry
                )
            )
        for key in ("name", "reason"):
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise SystemExit(
                    "{}: every exclude needs a non-empty string "
                    "'name' and 'reason' (bad entry: {!r})".format(path, entry)
                )
        if "category" in entry and (
            not isinstance(entry["category"], str) or not entry["category"]
        ):
            raise SystemExit(
                "{}: 'category' must be a non-empty string "
                "(bad entry: {!r})".format(path, entry)
            )
    return data


def _merge_include(path, data):
    """Return the file's entries with its single include merged in.

    The contract is deliberately small: 'include' is ONE bare file
    name, resolved only in the provider data dir; the included file
    must not include anything itself; a name+category present in both
    files is an error (no overwrite semantics).
    """
    own = data["excludes"]
    include = data.get("include")
    if include is None:
        return own
    if not isinstance(include, str) or not include or os.sep in include:
        raise SystemExit(
            "{}: 'include' must be the bare name of a list in the "
            "provider data dir (got {!r})".format(path, include)
        )
    included_path = _data_dir_path(include, "{}: include".format(path))
    included = _read_exclude_file(included_path)
    if "include" in included:
        raise SystemExit(
            "{}: nested include is not supported ('include' found in "
            "the included file). Put the entries directly in this "
            "file, or include the other list from your top-level "
            "file.".format(included_path)
        )
    keys = {
        (entry["name"], entry.get("category"))
        for entry in included["excludes"]
    }
    for entry in own:
        if (entry["name"], entry.get("category")) in keys:
            raise SystemExit(
                "{}: entry {!r} is already defined in the included "
                "file {} (duplicates are not allowed)".format(
                    path, entry["name"], included_path
                )
            )
    return included["excludes"] + own


def load_excludes():
    """Return the exclude entries from the exclude-jobs JSON file.

    The file defaults to $PLAINBOX_PROVIDER_DATA/cuda/exclude_jobs.json
    and can be overridden (e.g. per project) via
    CUDA_SAMPLES_EXCLUDE_FILE — either an absolute path, or the bare
    name of a list shipped in the provider data dir (e.g.
    exclude_jobs.jetson.json).  An explicitly configured file must
    exist; a missing default just means no excludes.  A file may pull
    in one shipped base list via its 'include' key.
    """
    path = os.environ.get("CUDA_SAMPLES_EXCLUDE_FILE")
    if path and os.sep not in path:
        path = _data_dir_path(path, "CUDA_SAMPLES_EXCLUDE_FILE")
    if not path:
        data_dir = os.environ.get("PLAINBOX_PROVIDER_DATA")
        if not data_dir:
            print(
                "PLAINBOX_PROVIDER_DATA not set: no exclude list loaded",
                file=sys.stderr,
            )
            return []
        path = os.path.join(data_dir, "cuda", "exclude_jobs.json")
        if not os.path.exists(path):
            return []
    return _merge_include(path, _read_exclude_file(path))


def exclude_reason(excludes, category, name):
    """Return the exclude reason for a sample, or None."""
    for entry in excludes:
        if entry["name"] == name and entry.get("category") in (
            None,
            category,
        ):
            return entry["reason"]
    return None


def cuda_version():
    """Return the CUDA version reported by nvidia-smi as (major, minor)."""
    try:
        output = subprocess.check_output(
            ["nvidia-smi"], universal_newlines=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit("Cannot run nvidia-smi: {}".format(exc))
    match = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", output)
    if not match:
        raise SystemExit("Cannot find 'CUDA Version:' in nvidia-smi output")
    return (int(match.group(1)), int(match.group(2)))


def parse_tag(tag):
    """Parse a cuda-samples tag like 'v12.5' into (12, 5), else None."""
    match = re.match(r"v?(\d+)\.(\d+)", tag)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)))


def _git(root, *args):
    # -c safe.directory: provisioning may have cloned the tree as a
    # different user, which git otherwise rejects as dubious ownership.
    try:
        proc = subprocess.run(
            ["git", "-c", "safe.directory={}".format(root), "-C", root]
            + list(args),
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise RuntimeError(str(exc))
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git failed")
    return proc.stdout.strip()


def checkout_tag_versions(root):
    """Return (current, expected_pool) tag versions of a git checkout.

    current is the parsed version of the tag the tree is checked out
    at; expected_pool is the set of parsed versions of all tags in the
    repository.  Returns a string explaining why the check cannot run
    when the tree is not a usable git checkout (e.g. shipped inside a
    snap, where the version match is guaranteed at snap build time
    instead).
    """
    try:
        described = _git(root, "describe", "--tags")
        tags = _git(root, "tag", "-l").splitlines()
    except RuntimeError as exc:
        return "git: {}".format(exc)
    current = parse_tag(described)
    pool = {
        version
        for version in (parse_tag(tag) for tag in tags)
        if version is not None
    }
    if current is None or not pool:
        return "no parseable release tags (describe: {!r})".format(described)
    return current, pool


def check_version_match(root):
    """Fail if the checkout tag is not the newest tag <= CUDA version."""
    versions = checkout_tag_versions(root)
    if isinstance(versions, str):
        if os.path.exists(os.path.join(root, ".git")):
            # A tree WITH git metadata must support the check; a
            # broken or tag-less checkout is a provisioning bug, not
            # a snap-style tree.
            raise SystemExit(
                "{} looks like a git checkout but the version match "
                "check cannot run ({}); re-clone the tree at the "
                "right tag with its tags intact".format(root, versions)
            )
        print(
            "{}: skipping the version match check ({}); a snap-shipped "
            "tree is version-matched at build time".format(root, versions)
        )
        return
    current, pool = versions
    cuda = cuda_version()
    matching = [version for version in pool if version <= cuda]
    if not matching:
        raise SystemExit(
            "No cuda-samples tag is <= CUDA version {}.{}".format(*cuda)
        )
    expected = max(matching)
    print(
        "CUDA version {}.{}, checkout tag v{}.{}, "
        "expected tag v{}.{}".format(*(cuda + current + expected))
    )
    if current == max(pool) and current < cuda:
        # A tag-incomplete clone (e.g. --single-branch at the tag)
        # cannot prove a newer matching tag does not exist upstream.
        print(
            "note: the checkout tag is the newest tag in this clone "
            "but older than the CUDA version; if the clone is not "
            "tag-complete this check is inconclusive"
        )
    if current != expected:
        raise SystemExit(
            "cuda-samples checkout v{}.{} does not match the newest "
            "tag <= CUDA version {}.{} (expected v{}.{}); re-clone the "
            "tree at the right tag".format(*(current + cuda + expected))
        )


def run_timeout():
    """Per-sample timeout in seconds (CUDA_SAMPLES_TIMEOUT override)."""
    raw = os.environ.get("CUDA_SAMPLES_TIMEOUT")
    if not raw:
        return DEFAULT_TIMEOUT
    try:
        return float(raw)
    except ValueError:
        raise SystemExit(
            "CUDA_SAMPLES_TIMEOUT is not a number: {!r}".format(raw)
        )


def cmd_list(args):
    root = resolve_root(args.path)
    excludes = load_excludes()
    for category, name in discover_samples(root):
        binary = find_binary(root, category, name)
        # An exclude reason wins; otherwise an unbuilt sample is a
        # visible skip too — `make -k` legitimately skips samples whose
        # platform dependencies are missing, so a red job would be
        # noise, but the sample must still show up as skipped.
        reason = exclude_reason(excludes, category, name)
        if reason is None and binary is None:
            reason = "not built"
        print("category: {}".format(category))
        print("name: {}".format(name))
        print("path: {}".format(binary or ""))
        print("skip: {}".format(reason is not None))
        print("skip_reason: {}".format(reason or ""))
        print()
    return 0


def cmd_readiness(args):
    root = resolve_root(args.path)
    print("cuda-samples tree: {}".format(root))
    excludes = load_excludes()
    samples = list(discover_samples(root))
    built = unbuilt = 0
    for category, name in samples:
        if find_binary(root, category, name):
            built += 1
        elif exclude_reason(excludes, category, name) is None:
            unbuilt += 1
    if not built:
        raise SystemExit(
            "No built sample binaries found under {}. This suite is "
            "prebuilt-only: build cuda-samples before running "
            "Checkbox.".format(root)
        )
    print("built samples: {}".format(built))
    print("unbuilt samples (become visible skips): {}".format(unbuilt))
    if unbuilt > built:
        raise SystemExit(
            "More unbuilt than built samples ({} vs {}): the tree "
            "looks partially built; rebuild it before running "
            "Checkbox.".format(unbuilt, built)
        )
    check_version_match(root)
    print("exclude entries: {}".format(len(excludes)))
    absent = [
        entry["name"]
        for entry in excludes
        if not any(
            entry["name"] == name and entry.get("category") in (None, category)
            for category, name in samples
        )
    ]
    if absent:
        # Informational: entries may be for samples that only exist at
        # other cuda-samples versions — but a typo would show up here.
        print(
            "exclude entries not present in this tree (version-"
            "specific, or a typo): {}".format(", ".join(absent))
        )
    return 0


def make_sandbox(root, category, name):
    """Create a disposable run directory mirroring the tree layout.

    Samples read their inputs relative to the working directory
    (including climbs up to <root>/Common/data) and write output files
    into it — but the provisioned tree may be root-owned and must
    never be modified by a test run.  Copy the sample's own directory
    into a temporary tree with the same nesting and symlink Common
    beside it (inputs only, read-only is fine).

    Returns (sandbox_root, run_dir); the caller removes sandbox_root.
    """
    source_dir = os.path.join(root, "Samples", category, name)
    sandbox = tempfile.mkdtemp(prefix="cuda-sample-")
    run_dir = os.path.join(sandbox, "Samples", category, name)
    if os.path.isdir(source_dir):
        shutil.copytree(source_dir, run_dir)
    else:
        os.makedirs(run_dir)
    common = os.path.join(root, "Common")
    if os.path.isdir(common):
        os.symlink(common, os.path.join(sandbox, "Common"))
    return sandbox, run_dir


def cmd_run(args):
    root = resolve_root(args.path)
    binary = find_binary(root, args.category, args.name)
    if binary is None:
        raise SystemExit(
            "No built binary for {}/{} (tried: {})".format(
                args.category,
                args.name,
                ", ".join(binary_candidates(root, args.category, args.name)),
            )
        )
    timeout = run_timeout()
    sandbox, run_dir = make_sandbox(root, args.category, args.name)
    print("** Executing {} (timeout {:g}s)".format(binary, timeout))
    sys.stdout.flush()
    try:
        # start_new_session: a hanging sample (e.g. an EGL render loop
        # on a headless system) may spawn helpers; kill the whole
        # process group or an orphan keeps the job's output pipe open
        # forever.
        try:
            proc = subprocess.Popen(
                [binary], cwd=run_dir, start_new_session=True
            )
        except OSError as exc:
            raise SystemExit("Cannot execute {}: {}".format(binary, exc))
        try:
            return proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                # Bounded: a process stuck in uninterruptible sleep
                # (e.g. a wedged device ioctl) survives SIGKILL and
                # must not block the job forever.
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            print(
                "{}/{} timed out after {:g}s".format(
                    args.category, args.name, timeout
                ),
                file=sys.stderr,
            )
            return 1
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        help="cuda-samples tree root (default: CUDA_SAMPLES_PATH, "
        "then {}, then {})".format(CLASSIC_DEFAULT_ROOT, SNAP_ROOT_GLOB),
    )
    # required= for add_subparsers needs Python 3.7; enforce below.
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "list", help="print one resource record per sample"
    ).set_defaults(func=cmd_list)
    subparsers.add_parser(
        "readiness",
        help="verify the tree is present, built and " "version-matched",
    ).set_defaults(func=cmd_readiness)
    run_parser = subparsers.add_parser("run", help="run a single sample")
    run_parser.add_argument("category", help="samples category directory")
    run_parser.add_argument("name", help="sample name")
    run_parser.set_defaults(func=cmd_run)
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.error("a subcommand is required: list, readiness or run")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
