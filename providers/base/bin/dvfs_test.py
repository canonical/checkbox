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

Subcommands:
  detect    Fail if no /sys/class/devfreq device is available. If the
            EXPECTED_DVFS_DEVICES environment variable is set, also check
            that every listed device (and its governors) is present.
  resource  Emit one resource record per (device, governor) pair found
            under /sys/class/devfreq/, used to generate the per-device,
            per-governor test jobs via the "dvfs/dvfs_resource" template.
  test      Switch a single DVFS device to the given governor and verify
            the switch took effect, restoring the original state
            afterwards.
"""

import argparse
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEVFREQ_ROOT = Path("/sys/class/devfreq")

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
        logger.debug("write {}={} failed: {}".format(path, value, exc))
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
    valid devfreq devices.
    """
    if not DEVFREQ_ROOT.is_dir():
        return []

    devices = [
        entry.name
        for entry in DEVFREQ_ROOT.iterdir()
        if entry.is_dir() and (entry / "governor").exists()
    ]
    return sorted(devices)


def get_available_governors(dvfs_device: str) -> List[str]:
    dev_path = DEVFREQ_ROOT / dvfs_device
    raw = _read_node(dev_path / "available_governors")
    return raw.split() if raw else []


def get_available_frequencies(dvfs_device: str) -> List[int]:
    dev_path = DEVFREQ_ROOT / dvfs_device
    raw = _read_node(dev_path / "available_frequencies")
    if not raw:
        return []
    if not all(token.isdigit() for token in raw.split()):
        print("unexpected available_frequencies content: {!r}".format(raw))
        return []
    return [int(token) for token in raw.split()]


def parse_expected_dvfs_devices(spec: str) -> Dict[str, List[str]]:
    """Parse an EXPECTED_DVFS_DEVICES string into {device: [governors]}.

    Format: "<dev>|<gov1>,<gov2>,... [<dev2>|<gov1>,... ...]", e.g.
    "13000000.gpu|userspace,powersave,performance,simple_ondemand
    soc:vpu_devfreq|userspace,powersave"
    """
    expected = {}
    for entry in spec.split():
        name, _, governors = entry.partition("|")
        if not name or not governors:
            raise SystemExit(
                "invalid EXPECTED_DVFS_DEVICES entry: {!r}".format(entry)
            )
        expected[name] = [g for g in governors.split(",") if g]
    return expected


def cmd_detect() -> None:
    """
    Detect DVFS devices under /sys/class/devfreq.

    If no DVFS device is available, the test will fail.
    If DVFS devices are available, the test will pass.
    If EXPECTED_DVFS_DEVICES environment variable is set, the test will
    check if the expected devices and their governors are matched against
    the actual available DVFS devices.
    """
    devices = list_devfreq_devices()
    if not devices:
        raise SystemExit("No DVFS device found under {}".format(DEVFREQ_ROOT))

    print("Detected {} DVFS device(s):".format(len(devices)))
    for dev in devices:
        governors = get_available_governors(dev)
        print("  {}: {}".format(dev, ",".join(governors)))

    expected_spec = os.environ.get("EXPECTED_DVFS_DEVICES", "").strip()
    if not expected_spec:
        return

    print("EXPECTED_DVFS_DEVICES={!r}".format(expected_spec))
    expected = parse_expected_dvfs_devices(expected_spec)

    errors = []
    for name, expected_governors in expected.items():
        if name not in devices:
            errors.append("expected DVFS device {!r} not found".format(name))
            continue
        actual_governors = get_available_governors(name)
        if set(actual_governors) != set(expected_governors):
            errors.append(
                "device {!r} governor mismatch: expected={} actual={}".format(
                    name,
                    sorted(expected_governors),
                    sorted(actual_governors),
                )
            )

    if errors:
        raise SystemExit("\n".join(errors))


def cmd_resource() -> None:
    """
    Print the DVFS device and governor resource records from the
    /sys/class/devfreq/ system path.

    Always return 0 even there's no DVFS resource available.
    """
    for dev in list_devfreq_devices():
        for governor in get_available_governors(dev):
            print("dvfs_device_name: {}".format(dev))
            print("governor: {}".format(governor))
            print("")


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
) -> Iterator[Tuple[Optional[str], Optional[str]]]:
    """Back up a device's governor/frequency and restore them on exit.

    The original state is restored even if the code inside the ``with``
    block raises, so callers never need to remember to clean up.
    """
    orig_gov = _read_node(gov_node)
    orig_freq = _read_node(cur_freq_node)
    print(
        "backup {} -> governor={} freq={}".format(
            dev_path.name, orig_gov, orig_freq
        )
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
        print(
            "restored {} -> governor={} freq={}".format(
                dev_path.name,
                _read_node(gov_node),
                _read_node(cur_freq_node),
            )
        )


def cmd_test(dvfs_device: str, governor: str) -> None:
    """
    Switch the given DVFS device to the given governor and verify the
    change actually took effect, adjusting (and checking) frequency as
    appropriate for that governor:
      * performance -> cur_freq must settle at max(available_frequencies).
      * powersave   -> cur_freq must settle at min(available_frequencies).
      * userspace   -> every entry of available_frequencies is written in
                       turn and cur_freq must match each one.
      * any other governor (e.g. simple_ondemand) -> only the governor
        switch itself is verified.
    The device's original governor/frequency is always restored, even if
    a check fails.
    """
    dev_path = DEVFREQ_ROOT / dvfs_device
    gov_node = dev_path / "governor"
    cur_freq_node = dev_path / "cur_freq"

    if not gov_node.exists():
        raise SystemExit(
            "DVFS device {!r} not found under {}".format(
                dvfs_device, DEVFREQ_ROOT
            )
        )

    available_governors = get_available_governors(dvfs_device)
    if governor not in available_governors:
        msg = "governor {!r} not in available_governors ({}) for device {!r}"
        raise SystemExit(
            msg.format(governor, ",".join(available_governors), dvfs_device)
        )

    errors = []
    with _dvfs_state_guard(dev_path, gov_node, cur_freq_node):
        if not _write_node(gov_node, governor):
            raise SystemExit(
                "write governor={} rejected by kernel".format(governor)
            )

        cur_gov = _poll_until(
            lambda: _read_node(gov_node), lambda v: v == governor
        )
        if cur_gov != governor:
            errors.append(
                "governor switch failed: expected={} actual={}".format(
                    governor, cur_gov
                )
            )

        available_freqs = get_available_frequencies(dvfs_device)
        if not available_freqs:
            raise SystemExit(
                "no available_frequencies for device {!r}".format(dvfs_device)
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
            print(
                "governor={} -> expect cur_freq={} actual={}".format(
                    governor, expected_freq, cur_freq
                )
            )
            if cur_freq != expected_freq:
                errors.append(
                    "governor={} -> expect cur_freq={} actual={}".format(
                        governor, expected_freq, cur_freq
                    )
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
                print(
                    "frequency={} -> {} (cur_freq={})".format(
                        freq, "PASS" if passed else "FAIL", cur_freq
                    )
                )
                if not passed:
                    errors.append(
                        "frequency={} -> FAIL (cur_freq={})".format(
                            freq, cur_freq
                        )
                    )
        else:
            print(
                "governor={} -> {} (governor={})".format(
                    governor,
                    "PASS" if cur_gov == governor else "FAIL",
                    cur_gov,
                )
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
        help="DVFS device name",
    )
    test_parser.add_argument(
        "-g",
        "--governor",
        required=True,
        help="DVFS device governor",
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
