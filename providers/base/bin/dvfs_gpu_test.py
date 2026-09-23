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
DVFS (Dynamic Voltage and Frequency Scaling) GPU helper for Checkbox.

This script only deals with GPU devfreq devices. By default it looks for
them under /sys/class/devfreq/, exactly like any other devfreq device.
Some GPU drivers (e.g. proprietary Mali/Verisilicon stacks) instead
expose their devfreq node under a different sysfs path (for example
/sys/class/misc/mali0/device/devfreq/<name>); the DVFS_GPU_DEVICES
environment variable lets the board configuration point at the right
place, and/or restrict which device(s) are exercised, and/or assert
which governors are expected to be available.

Subcommands:
  detect    Fail if no DVFS GPU device is available. If the
            DVFS_GPU_DEVICES environment variable is set, also check
            that every listed device (and its governors) is present.
  resource  Emit one resource record per (device, governor) pair for the
            GPU device(s) selected by DVFS_GPU_DEVICES (or every devfreq
            device under /sys/class/devfreq/ if it isn't set), used to
            generate the per-device, per-governor test jobs via the
            "dvfs/dvfs_gpu_resource" template.
  test      Switch a single DVFS GPU device to the given governor and
            verify the switch took effect, restoring the original state
            afterwards.
"""

import argparse
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEVFREQ_ROOT = Path("/sys/class/devfreq")

# Environment variable used to select/describe the GPU devfreq device(s),
# see the module docstring and parse_dvfs_gpu_devices() for its format.
DVFS_GPU_DEVICES = "DVFS_GPU_DEVICES"

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
        logger.debug(f"write {path}={value} failed: {exc}")
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


def list_devfreq_devices() -> List[str]:
    """Return the sorted list of device names under /sys/class/devfreq/.

    Only entries that actually expose a "governor" node are considered
    valid devfreq devices. This is only used as the fallback when
    DVFS_GPU_DEVICES isn't set; see resolve_dvfs_gpu_devices().
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


def parse_dvfs_gpu_devices(spec: str) -> Dict[str, Dict]:
    """Parse the DVFS_GPU_DEVICES environment variable.

    Each whitespace-separated entry describes one GPU devfreq device:
        <name-or-absolute-path>[|<governor1>,<governor2>,...]

    - If the identifier starts with "/", it is an absolute path to the
      device's devfreq directory (e.g.
      /sys/class/misc/mali0/device/devfreq/13000000.gpu), used when the
      GPU driver doesn't expose its node under /sys/class/devfreq/. The
      device's name is taken from the last path component.
    - Otherwise, it is a device name resolved under the default
      /sys/class/devfreq/<name> directory.
    - The optional "|<governors>" suffix lists the governors expected to
      be available for that device; it is only used by the "detect"
      check (resource/test always read the live available_governors).

    Returns {name: {"path": Path, "governors": [str, ...]}}.
    """
    devices = {}
    for entry in spec.split():
        identifier, _, governors_part = entry.partition("|")
        if not identifier:
            raise SystemExit(
                f"invalid {DVFS_GPU_DEVICES} entry: {entry!r}"
            )
        if identifier.startswith("/"):
            dev_path = Path(identifier)
            name = dev_path.name
        else:
            name = identifier
            dev_path = DEVFREQ_ROOT / name
        governors = [g for g in governors_part.split(",") if g]
        devices[name] = {"path": dev_path, "governors": governors}
    return devices


def resolve_dvfs_gpu_devices() -> Dict[str, Path]:
    """Return {device_name: device_path} for the GPU device(s) to use.

    If DVFS_GPU_DEVICES is set, it is the sole source of truth for which
    device(s) to use and where to find them. Otherwise, fall back to
    every devfreq device found under the default /sys/class/devfreq
    root.
    """
    spec = os.environ.get(DVFS_GPU_DEVICES, "").strip()
    if spec:
        return {
            name: info["path"]
            for name, info in parse_dvfs_gpu_devices(spec).items()
        }
    return {name: DEVFREQ_ROOT / name for name in list_devfreq_devices()}


def cmd_detect() -> None:
    """
    Detect DVFS GPU devices.

    If no DVFS GPU device is available, the test will fail.
    If DVFS GPU devices are available, the test will pass.
    If DVFS_GPU_DEVICES environment variable is set, the test will check
    if the expected devices and their governors are matched against the
    actual available DVFS GPU devices.
    """
    spec = os.environ.get(DVFS_GPU_DEVICES, "").strip()
    if spec:
        logger.info(f"{DVFS_GPU_DEVICES}={spec!r}")

    devices = resolve_dvfs_gpu_devices()
    if not devices:
        raise SystemExit(f"No DVFS GPU device found under {DEVFREQ_ROOT}")

    errors = []
    logger.info(f"Detected {len(devices)} DVFS device(s):")
    for name, dev_path in sorted(devices.items()):
        if not (dev_path / "governor").exists():
            errors.append(
                f"expected DVFS GPU device {name!r} not found at {dev_path}"
            )
            continue
        governors = get_available_governors(dev_path)
        logger.info(f"  {name} ({dev_path}): {','.join(governors)}")

    if spec:
        expected = parse_dvfs_gpu_devices(spec)
        for name, info in expected.items():
            if not info["governors"] or name not in devices:
                continue
            actual_governors = get_available_governors(devices[name])
            if set(actual_governors) != set(info["governors"]):
                expected_governors = sorted(info["governors"])
                actual_sorted = sorted(actual_governors)
                errors.append(
                    f"device {name!r} governor mismatch: "
                    f"expected={expected_governors} actual={actual_sorted}"
                )

    if errors:
        raise SystemExit("\n".join(errors))


def cmd_resource() -> None:
    """
    Print the DVFS GPU device and governor resource records for the
    device(s) selected by DVFS_GPU_DEVICES (or every devfreq device
    under /sys/class/devfreq/ if it isn't set).

    Always return 0 even there's no DVFS GPU resource available.

    Note: these records are printed to stdout (not logged) because
    Checkbox parses a resource job's stdout as RFC822 key: value
    records; logging them would corrupt the format with timestamps and
    log levels.
    """
    for name, dev_path in sorted(resolve_dvfs_gpu_devices().items()):
        if not (dev_path / "governor").exists():
            continue
        for governor in get_available_governors(dev_path):
            print(f"dvfs_device_name: {name}")
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


def cmd_test(dvfs_device: str, governor: str) -> None:
    """
    Switch the given DVFS GPU device to the given governor and verify
    the change actually took effect, adjusting (and checking) frequency
    as appropriate for that governor:
      * performance -> cur_freq must settle at max(available_frequencies).
      * powersave   -> cur_freq must settle at min(available_frequencies).
      * userspace   -> every entry of available_frequencies is written in
                       turn and cur_freq must match each one.
      * any other governor (e.g. simple_ondemand) -> only the governor
        switch itself is verified.
    The device's original governor/frequency is always restored, even if
    a check fails. The device's location is resolved via
    DVFS_GPU_DEVICES if set (falling back to /sys/class/devfreq/<name>
    otherwise), since jobs only pass the device name on the command
    line.
    """
    dev_path = resolve_dvfs_gpu_devices().get(
        dvfs_device, DEVFREQ_ROOT / dvfs_device
    )
    gov_node = dev_path / "governor"
    cur_freq_node = dev_path / "cur_freq"

    if not gov_node.exists():
        raise SystemExit(
            f"DVFS GPU device {dvfs_device!r} not found at {dev_path}"
        )

    available_governors = get_available_governors(dev_path)
    if governor not in available_governors:
        joined_governors = ",".join(available_governors)
        raise SystemExit(
            f"governor {governor!r} not in available_governors "
            f"({joined_governors}) for device {dvfs_device!r}"
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
                f"no available_frequencies for device {dvfs_device!r}"
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

    subparsers.add_parser("detect", parents=[common_parser])

    subparsers.add_parser("resource", parents=[common_parser])

    test_parser = subparsers.add_parser("test", parents=[common_parser])
    test_parser.add_argument(
        "-d",
        "--dvfs-device",
        required=True,
        help="DVFS GPU device name",
    )
    test_parser.add_argument(
        "-g",
        "--governor",
        required=True,
        help="DVFS GPU device governor",
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

    if args.action == "detect":
        cmd_detect()
    elif args.action == "resource":
        cmd_resource()
    elif args.action == "test":
        cmd_test(dvfs_device=args.dvfs_device, governor=args.governor)


if __name__ == "__main__":
    main()
