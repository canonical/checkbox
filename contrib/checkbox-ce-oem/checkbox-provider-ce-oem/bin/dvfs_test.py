#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.

"""
DVFS (Dynamic Voltage and Frequency Scaling) helper for Checkbox.

The processor(s) to exercise are described by a per-platform JSON file
(see data/dynamic-voltage-and-frequency-scaling/*.json and its schema)
pointed at by the DVFS_PROCESSORS_FILE_PATH environment variable. When
that variable isn't set, every devfreq processor found under
/sys/class/devfreq/ is used instead, with its type defaulting to
"other".

Subcommands:
  resource  Emit one resource record per (processor, governor) pair
            for the selected processor(s), used to generate the
            per-processor, per-governor test jobs via the
            "ce-oem-dvfs/dvfs_resource" template.
  test      Switch a single DVFS processor to the given governor and
            verify the switch took effect, restoring the original
            state afterwards.
"""

import argparse
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

from general_utils import load_json_file

logger = logging.getLogger(__name__)

DEVFREQ_ROOT = Path("/sys/class/devfreq")

# Environment variable pointing at the JSON processor map to use.
# Relative paths are resolved under PLAINBOX_PROVIDER_DATA by
# general_utils.load_json_file().
DVFS_PROCESSORS_FILE_PATH = os.environ.get("DVFS_PROCESSORS_FILE_PATH", "").strip()

# Available processor types are gpu, vpu and npu now. A processor is classified
# as "other" if it doesn't match any of these types in the JSON allowlist.
DEFAULT_PROCESSOR_TYPE = "other"


# Polling defaults used while waiting for a governor/frequency change
# requested through sysfs to take effect.
POLL_TIMEOUT_S = 2.0
POLL_INTERVAL_S = 0.05


def _read_node(path: Path) -> Optional[str]:
    """Read and strip a sysfs node, returning None if it doesn't exist."""
    if not path.exists():
        return None
    return path.read_text().strip()


def _write_node(path: Path, value) -> bool:
    """Write a value to a sysfs node, returning False on any OS error."""
    try:
        path.write_text(str(value))
        return True
    except OSError as exc:
        logger.error(f"write {path}={value} failed: {exc}")
        return False


def _poll_until(read_fn, is_done) -> Optional[str]:
    """Poll ``read_fn`` until ``is_done(value)`` or a timeout elapses.

    This replaces a fixed sleep-then-read with a bounded poll loop, so
    that fast hardware doesn't pay a needless fixed delay and slow
    hardware still gets a chance to settle within POLL_TIMEOUT_S.
    """
    deadline = time.monotonic() + POLL_TIMEOUT_S
    value = read_fn()
    while not is_done(value) and time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_S)
        value = read_fn()
    return value


def list_devfreq_processors() -> List[str]:
    """Return the sorted list of device names under /sys/class/devfreq/.

    Only entries that actually expose a "governor" node are considered
    valid devfreq devices. This is only used as the fallback when
    DVFS_PROCESSORS_FILE_PATH isn't set.
    """
    if not DEVFREQ_ROOT.is_dir():
        return []

    devices = [
        entry.name
        for entry in DEVFREQ_ROOT.iterdir()
        if entry.is_dir() and (entry / "governor").exists()
    ]
    return sorted(devices)


def get_available_governors(dev_path: Path) -> List[str]:
    raw = _read_node(dev_path / "available_governors")
    return raw.split() if raw else []


def get_available_frequencies(dev_path: Path) -> List[int]:
    raw = _read_node(dev_path / "available_frequencies")
    if not raw:
        return []
    if not all(token.isdigit() for token in raw.split()):
        logger.warning(f"unexpected available_frequencies content: {raw!r}")
        return []
    return [int(token) for token in raw.split()]


def resolve_dvfs_processors() -> Dict[str, Dict]:
    """Return {processor_name: {"path", "type", "governors"}} for every
    processor to use.

    If DVFS_PROCESSORS_FILE_PATH is set, its "allowlist" (minus any
    "denylist" entries) is the sole source of truth for which
    processor(s) to use, their type, and their expected governors.
    Otherwise, fall back to every devfreq device found under the
    default /sys/class/devfreq root, with type defaulting to "other"
    and its expected governors taken from the live
    available_governors sysfs value.
    """
    config = load_json_file(DVFS_PROCESSORS_FILE_PATH, enable_logger=True)
    if not config:
        return {
            name: {
                "path": DEVFREQ_ROOT / name,
                "type": DEFAULT_PROCESSOR_TYPE,
                "governors": get_available_governors(DEVFREQ_ROOT / name),
            }
            for name in list_devfreq_processors()
        }

    denylist = set(config.get("denylist", []))
    processors = {}
    for entry in config.get("allowlist", []):
        name = entry["device_name"]
        if name in denylist:
            logger.info(f"skip denylisted processor {name!r}")
            continue
        sysfs_path = entry.get("sysfs_path")
        dev_path = Path(sysfs_path) if sysfs_path else DEVFREQ_ROOT / name
        processors[name] = {
            "path": dev_path,
            "type": entry.get("type", DEFAULT_PROCESSOR_TYPE),
            "governors": entry.get("governors", []),
        }
    return processors


def do_check() -> None:
    """
    Detect and check the DVFS processors.

    Check Scenarios:
    1. If DVFS_PROCESSORS_FILE_PATH is not set, check if there's any
       DVFS devices under the /sys/class/devfreq/ path.
    2. If DVFS_PROCESSORS_FILE_PATH is set, check if the specified DVFS
       processors exist and their governors match exactly.
    """
    errors = []

    if not DVFS_PROCESSORS_FILE_PATH:
        if not list_devfreq_processors():
            err_msg = f"no DVFS processors found under {DEVFREQ_ROOT}"
            logger.error(err_msg)
            errors.append(err_msg)
    else:
        for name, info in sorted(resolve_dvfs_processors().items()):
            dev_path = info["path"]
            if not (dev_path / "governor").exists():
                err_msg = f"processor {name!r} not found at {dev_path}"
                logger.error(err_msg)
                errors.append(err_msg)
                continue
            expected_governors = set(info["governors"])
            actual_governors = set(get_available_governors(dev_path))
            if actual_governors != expected_governors:
                err_msg = (f"processor {name!r} governors mismatch: "
                           f"expected={sorted(expected_governors)} "
                           f"actual={sorted(actual_governors)}")
                logger.error(err_msg)
                errors.append(err_msg)

    if errors:
        raise SystemExit(1)
    logger.info("DVFS processor check passed")


def cmd_resource() -> None:
    """
    Print the DVFS processor and governor resource records for every
    selected processor.
    """
    for name, info in sorted(resolve_dvfs_processors().items()):
        dev_path = info["path"]
        for governor in get_available_governors(dev_path):
            print(f"dvfs_processor_name: {name}")
            print(f"dvfs_processor_type: {info['type']}")
            print(f"sysfs_path: {dev_path}")
            print(f"governor: {governor}")
            print()


def _userspace_freq_node(dev_path: Path, cur_freq_node: Path) -> Path:
    """Return the node to write to request a frequency under 'userspace'.

    Some MediaTek kernels expose a dedicated userspace/set_freq node
    instead of accepting writes directly to cur_freq.
    """
    mtk_node = dev_path / "userspace" / "set_freq"
    return mtk_node if mtk_node.exists() else cur_freq_node


@contextmanager
def _dvfs_state_guard(
    dev_path: Path, gov_node: Path, cur_freq_node: Path
) -> Generator[Tuple[Optional[str], Optional[str]], None, None]:
    """Back up a device's governor/frequency and restore them on exit.

    The original state is restored even if the code inside the ``with``
    block raises, so callers never need to remember to clean up.
    """
    orig_gov = _read_node(gov_node)
    orig_freq = _read_node(cur_freq_node)
    logger.info(
        f"backup {dev_path.name} -> governor={orig_gov} freq={orig_freq}"
    )
    try:
        yield orig_gov, orig_freq
    finally:
        if orig_gov:
            if orig_gov == "userspace" and orig_freq:
                _write_node(gov_node, "userspace")
                freq_node = _userspace_freq_node(dev_path, cur_freq_node)
                _write_node(freq_node, orig_freq)
                _poll_until(
                    lambda: _read_node(cur_freq_node),
                    lambda v: v == orig_freq,
                )
            else:
                _write_node(gov_node, orig_gov)
                _poll_until(
                    lambda: _read_node(gov_node), lambda v: v == orig_gov
                )
        restored_gov = _read_node(gov_node)
        restored_freq = _read_node(cur_freq_node)
        logger.info(
            f"restored {dev_path.name} -> governor={restored_gov} "
            f"freq={restored_freq}"
        )


def cmd_test(
    dvfs_processor: str,
    dvfs_processor_type: str,
    sysfs_path: str,
    governor: str,
) -> None:
    """
    Switch the given DVFS processor to the given governor and verify
    the change actually took effect, adjusting (and checking)
    frequency as appropriate for that governor:
      * performance -> cur_freq must settle at max(available_frequencies).
      * powersave   -> cur_freq must settle at min(available_frequencies).
      * userspace   -> every entry of available_frequencies is written in
                       turn and cur_freq must match each one.
      * any other governor (e.g. simple_ondemand) -> only the governor
        switch itself is verified.
    The processor's original governor/frequency is always restored,
    even if a check fails. ``sysfs_path`` is the processor's devfreq
    directory as resolved by the "ce-oem-dvfs/dvfs_resource" job
    (falling back to /sys/class/devfreq/<dvfs_processor> when not
    given), since jobs only pass the processor name, type and sysfs
    path on the command line.
    """
    dev_path = (
        Path(sysfs_path) if sysfs_path else DEVFREQ_ROOT / dvfs_processor
    )
    gov_node = dev_path / "governor"
    cur_freq_node = dev_path / "cur_freq"

    logger.info(
        f"testing processor={dvfs_processor} type={dvfs_processor_type} "
        f"path={dev_path} governor={governor}"
    )

    if not gov_node.exists():
        raise SystemExit(
            f"DVFS processor {dvfs_processor!r} not found at {dev_path}"
        )

    available_governors = get_available_governors(dev_path)
    if governor not in available_governors:
        joined_governors = ",".join(available_governors)
        raise SystemExit(
            f"governor {governor!r} not in available_governors "
            f"({joined_governors}) for processor {dvfs_processor!r}"
        )

    errors = []
    with _dvfs_state_guard(dev_path, gov_node, cur_freq_node):
        if not _write_node(gov_node, governor):
            raise SystemExit(f"write governor={governor} rejected by kernel")

        cur_gov = _poll_until(
            lambda: _read_node(gov_node), lambda v: v == governor
        )
        if cur_gov != governor:
            errors.append(
                f"governor switch failed: expected={governor} "
                f"actual={cur_gov}"
            )

        available_freqs = get_available_frequencies(dev_path)
        if not available_freqs:
            raise SystemExit(
                f"no available_frequencies for processor {dvfs_processor!r}"
            )

        if governor in ("performance", "powersave"):
            expected_freq = str(
                max(available_freqs)
                if governor == "performance"
                else min(available_freqs)
            )
            cur_freq = _poll_until(
                lambda: _read_node(cur_freq_node),
                lambda v: v == expected_freq,
            )
            logger.info(
                f"governor={governor} -> expect cur_freq={expected_freq} "
                f"actual={cur_freq}"
            )
            if cur_freq != expected_freq:
                errors.append(
                    f"governor={governor} -> expect "
                    f"cur_freq={expected_freq} actual={cur_freq}"
                )
        elif governor == "userspace":
            freq_node = _userspace_freq_node(dev_path, cur_freq_node)
            for freq in available_freqs:
                _write_node(freq_node, freq)
                cur_freq = _poll_until(
                    lambda: _read_node(cur_freq_node),
                    lambda v: v == str(freq),
                )
                passed = cur_freq == str(freq)
                status = "PASS" if passed else "FAIL"
                logger.info(
                    f"frequency={freq} -> {status} (cur_freq={cur_freq})"
                )
                if not passed:
                    errors.append(
                        f"frequency={freq} -> FAIL (cur_freq={cur_freq})"
                    )
        else:
            status = "PASS" if cur_gov == governor else "FAIL"
            logger.info(
                f"governor={governor} -> {status} (governor={cur_gov})"
            )

    if errors:
        raise SystemExit("\n".join(errors))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)

    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--debug",
        action="store_true",
        help="enable debug logging",
    )

    subparsers.add_parser("resource", parents=[common_parser])

    test_parser = subparsers.add_parser("test", parents=[common_parser])
    test_parser.add_argument(
        "-p",
        "--sysfs-path",
        dest="sysfs_path",
        default="",
        help=(
            "Absolute sysfs path to the DVFS processor's devfreq "
            "directory (defaults to /sys/class/devfreq/<processor>)"
        ),
    )
    test_parser.add_argument(
        "-t",
        "--dvfs-processor-type",
        default=DEFAULT_PROCESSOR_TYPE,
        choices=["gpu", "npu", "vpu", "other"],
        help="DVFS processor type",
    )
    test_parser.add_argument(
        "-d",
        "--dvfs-processor",
        required=True,
        help="DVFS processor name",
    )
    test_parser.add_argument(
        "-g",
        "--governor",
        required=True,
        help="DVFS processor governor",
    )

    return parser


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-8s - %(module)-10s: %(funcName)s "
        "%(lineno)-4d - %(message)s",
    )

    parser = build_parser()
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.action == "resource":
        if args.debug:
            do_check()
        cmd_resource()
    elif args.action == "test":
        cmd_test(
            dvfs_processor=args.dvfs_processor,
            dvfs_processor_type=args.dvfs_processor_type,
            sysfs_path=args.sysfs_path,
            governor=args.governor,
        )


if __name__ == "__main__":
    main()
