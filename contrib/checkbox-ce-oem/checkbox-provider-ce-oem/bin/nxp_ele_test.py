#!/usr/bin/env python3
"""Checkbox helper for NXP ELE TV discovery and execution."""

import argparse
import os
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Tuple

ELE_HSM_TEST_COMMAND_CANDIDATES = [
    "oem-imx-secure-enclave.ele-hsm-test",
    "ele_hsm_test",
]
ELE_HSM_PERF_TEST_COMMAND_CANDIDATES = [
    "oem-imx-secure-enclave.ele-hsm-perf-test",
    "ele_hsm_perf_test",
]
NVM_DAEMON_SERVICE_CANDIDATES = [
    "nvm_daemon.service",
    "nvm_daemon",
    "snap.oem-imx-secure-enclave.nvm-daemon.service",
]
NVM_DATA_DIRECTORIES = [Path("/etc/ele"), Path("/var/lib/se")]
TV_EXTENSIONS = {".tv", ".txt", ".json", ".bin"}
CANDIDATE_DIRECTORIES = [
    Path("/var/snap/oem-imx-secure-enclave/common"),
    Path("/snap/oem-imx-secure-enclave/current"),
    Path("/usr/share/oem-imx-secure-enclave"),
    Path("/usr/share/se/test_vectors"),
]


def eprint(message: str) -> None:
    """Print to stderr."""
    print(message, file=sys.stderr)


def resolve_command(candidates: List[str], command_label: str) -> str:
    """
    Resolve the first available executable command from a candidate list.
    """
    for candidate in candidates:
        if shutil.which(candidate) is not None:
            return candidate
    raise RuntimeError(
        "[NXP_ELE] Required command for {} not found. Tried: {}".format(
            command_label,
            ", ".join(candidates),
        )
    )


def ensure_systemctl_available() -> None:
    """Ensure systemctl is available for daemon lifecycle management."""
    if shutil.which("systemctl") is None:
        raise RuntimeError(
            "[NXP_ELE] Required command 'systemctl' was not found in PATH."
        )


def run_with_optional_sudo(
    command: List[str], allow_failure: bool = False
) -> int:
    """Run command directly as root or through sudo when needed."""
    final_command = list(command)
    if os.geteuid() != 0:
        sudo_path = shutil.which("sudo")
        if sudo_path is None:
            raise RuntimeError(
                "Root privileges are required and 'sudo' is not available."
            )
        final_command = [sudo_path] + final_command

    print("[NXP_ELE] Running command: {}".format(" ".join(final_command)))
    result = subprocess.run(final_command, check=False)
    if result.returncode != 0 and not allow_failure:
        raise RuntimeError(
            "[NXP_ELE] Command failed with exit code {}: {}".format(
                result.returncode, " ".join(final_command)
            )
        )
    return result.returncode


def resolve_nvm_daemon_service_name() -> str:
    """Resolve the available NVM daemon systemd unit name."""
    list_units_cmd = [
        "systemctl",
        "list-unit-files",
        "--type=service",
        "--no-legend",
    ]
    result = subprocess.run(
        list_units_cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "[NXP_ELE] Failed to query systemd unit files via {}".format(
                " ".join(list_units_cmd)
            )
        )

    available_units = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        unit_name = line.split()[0]
        available_units.add(unit_name)

    for candidate in NVM_DAEMON_SERVICE_CANDIDATES:
        if candidate in available_units:
            return candidate
        if (
            candidate.endswith(".service")
            and candidate[:-8] in available_units
        ):
            return candidate[:-8]

    raise RuntimeError(
        "Could not find supported NVM daemon service. Tried: {}".format(
            ", ".join(NVM_DAEMON_SERVICE_CANDIDATES)
        )
    )


def set_nvm_daemon_state(action: str, service_name: str) -> None:
    """Start or stop the NVM daemon service."""
    if action not in ("start", "stop"):
        raise RuntimeError("Unsupported daemon action: {}".format(action))
    run_with_optional_sudo(["systemctl", action, service_name])


def cleanup_nvm_data() -> None:
    """Delete NVM test data directories content when present."""
    for directory in NVM_DATA_DIRECTORIES:
        if not directory.exists():
            print("# Cleanup skipped (not found): {}".format(directory))
            continue

        print("# Cleaning directory: {}".format(directory))
        for child in directory.iterdir():
            if child.is_dir() and not child.is_symlink():
                run_with_optional_sudo(["rm", "-rf", str(child)])
            else:
                run_with_optional_sudo(["rm", "-f", str(child)])


def sanitize_name(name: str) -> str:
    """Convert a file stem into a Checkbox-id-friendly token."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "tv"


def parse_tv_metadata(tv_file: Path) -> Tuple[str, str]:
    """
    Parse category and variant from a TV filename stem.

    Example:
      test_vectors_set0_kgen_persistent_ap ->
        category=set0_kgen, variant=persistent_ap
    """
    stem = tv_file.stem
    prefix = "test_vectors_"
    raw = stem[len(prefix) :] if stem.startswith(prefix) else stem

    variant_candidates = ("persistent_ap", "volatile_ap", "ap", "n", "p")
    for variant in variant_candidates:
        suffix = "_{}".format(variant)
        if raw.endswith(suffix):
            category = raw[: -len(suffix)]
            if category:
                return sanitize_name(category), sanitize_name(variant)
            break

    return sanitize_name(raw), "generic"


def get_candidate_directories() -> List[Path]:
    """Build candidate TV directories, including snap revision paths."""
    candidates = list(CANDIDATE_DIRECTORIES)
    snap_root = Path("/snap/oem-imx-secure-enclave")
    if snap_root.is_dir():
        for revision_dir in sorted(
            snap_root.iterdir(), key=lambda path: path.name
        ):
            if not revision_dir.is_dir():
                continue
            candidates.append(revision_dir / "usr/share/se/test_vectors")
            candidates.append(revision_dir / "usr/share/se/test_vectors/psa")
            candidates.append(
                revision_dir / "usr/share/oem-imx-secure-enclave"
            )

    return candidates


def discover_tv_files() -> List[Path]:
    """Discover test vector files from candidate directories."""
    found = set()
    results = []

    all_candidates = get_candidate_directories()
    existing_dirs = [
        directory for directory in all_candidates if directory.is_dir()
    ]
    if not existing_dirs:
        candidates = ", ".join(str(path) for path in all_candidates)
        raise RuntimeError(
            "[NXP_ELE] No candidate TV directories found. Checked: {}".format(
                candidates
            )
        )

    for root in existing_dirs:
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                file_path = Path(dirpath) / filename
                if file_path.suffix.lower() not in TV_EXTENSIONS:
                    continue
                normalized = str(file_path.resolve())
                if normalized in found:
                    continue
                found.add(normalized)
                results.append(Path(normalized))

    results.sort(key=lambda path: str(path))
    return results


def build_tv_records(tv_files: List[Path]) -> List[Dict[str, str]]:
    """
    Build tv records for Checkbox resource output.

    Each record contains:
      - tv_file: full path
      - tv_name: unique, id-friendly identifier
      - tv_category: parsed functional category (e.g. set1_cipher)
      - tv_variant: parsed profile/variant (e.g. ap, p, n, persistent_ap)
    """
    records = []
    used_names = {}

    for tv_file in tv_files:
        base_name = sanitize_name(tv_file.stem)
        tv_category, tv_variant = parse_tv_metadata(tv_file)
        sequence = used_names.get(base_name, 0)
        used_names[base_name] = sequence + 1
        if sequence > 0:
            tv_name = "{}_{}".format(base_name, sequence + 1)
        else:
            tv_name = base_name

        records.append(
            {
                "tv_file": str(tv_file),
                "tv_name": tv_name,
                "tv_category": tv_category,
                "tv_variant": tv_variant,
            }
        )

    return records


def list_tv_records() -> int:
    """List TV records in key=value format for Checkbox resource plugin."""
    tv_files = discover_tv_files()
    if not tv_files:
        eprint(
            "[NXP_ELE] No test vector files found with extensions: "
            + ", ".join(sorted(TV_EXTENSIONS))
        )
        return 1

    for record in build_tv_records(tv_files):
        print("tv_file: {}".format(record["tv_file"]))
        print("tv_name: {}".format(record["tv_name"]))
        print("tv_category: {}".format(record["tv_category"]))
        print("tv_variant: {}".format(record["tv_variant"]))
        print()

    return 0


@contextmanager
def nvm_daemon_lifecycle():
    """Context manager for NVM daemon lifecycle around test execution."""
    ensure_systemctl_available()
    service_name = resolve_nvm_daemon_service_name()
    is_started = False

    try:
        print("[NXP_ELE] Stopping {} before cleanup".format(service_name))
        set_nvm_daemon_state("stop", service_name)

        cleanup_nvm_data()

        print("[NXP_ELE] Starting {} for test execution".format(service_name))
        set_nvm_daemon_state("start", service_name)
        is_started = True

        yield
    finally:
        if is_started:
            print("[NXP_ELE] Stopping {} after test".format(service_name))
            try:
                set_nvm_daemon_state("stop", service_name)
            except RuntimeError as exc:
                eprint(str(exc))


def run_with_nvm_lifecycle(test_command: List[str], test_label: str) -> int:
    """
    Execute one test command with the NVM daemon lifecycle.
    """
    test_exit = 1
    try:
        with nvm_daemon_lifecycle():
            test_exit = run_with_optional_sudo(
                test_command, allow_failure=True
            )
            if test_exit != 0:
                eprint(
                    "[NXP_ELE] {} failed with exit code {}".format(
                        test_label, test_exit
                    )
                )
                return test_exit

            print("[NXP_ELE] PASS: {} execution succeeded".format(test_label))
            return 0
    except RuntimeError as exc:
        eprint("[NXP_ELE] Error during {}: {}".format(test_label, str(exc)))
        return 1


def run_tv_file(tv_file: str) -> int:
    """
    Run one TV file with required daemon stop/cleanup/start/stop lifecycle.
    """
    test_command_bin = resolve_command(
        ELE_HSM_TEST_COMMAND_CANDIDATES, "ele_hsm_test"
    )
    file_path = Path(tv_file).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        eprint("[NXP_ELE] TV file does not exist: {}".format(file_path))
        return 1

    return run_with_nvm_lifecycle(
        [test_command_bin, str(file_path)],
        "TV execution",
    )


def run_perf_test() -> int:
    """Run ELE HSM performance test with required daemon lifecycle."""
    perf_command_bin = resolve_command(
        ELE_HSM_PERF_TEST_COMMAND_CANDIDATES, "ele_hsm_perf_test"
    )
    return run_with_nvm_lifecycle(
        [perf_command_bin],
        "Performance test",
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "List NXP ELE test vectors or execute ELE HSM tests "
            "with NVM daemon setup."
        ),
    )
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--list-tv",
        action="store_true",
        help=(
            "List discovered TV files as Checkbox resource records"
            " (key=value)."
        ),
    )
    action_group.add_argument(
        "--run-tv",
        metavar="PATH",
        help=(
            "Run one TV file via: "
            "[sudo] oem-imx-secure-enclave.ele-hsm-test <PATH>, "
            "including nvm_daemon stop/cleanup/start/stop."
        ),
    )
    action_group.add_argument(
        "--run-perf",
        action="store_true",
        help=(
            "Run ELE HSM performance test via: "
            "[sudo] oem-imx-secure-enclave.ele-hsm-perf-test, "
            "including nvm_daemon stop/cleanup/start/stop."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """Program entry point."""
    try:
        args = parse_args()
        if args.list_tv:
            return list_tv_records()
        if args.run_perf:
            return run_perf_test()
        if args.run_tv is None:
            eprint("[NXP_ELE] --run-tv requires a path argument.")
            return 1
        return run_tv_file(args.run_tv)
    except RuntimeError as exc:
        eprint(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
