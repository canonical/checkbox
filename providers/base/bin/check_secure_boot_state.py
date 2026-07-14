#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Isaac Yang    <isaac.yang@canonical.com>
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
Check that the secure boot state matches the expected state.

On UEFI systems (x86 and ARM EBBR alike) the state is read directly from
the SecureBoot EFI variable — the same source mokutil parses — so no
external tool is needed.

On non-UEFI systems (e.g. ARM boards booting a u-boot FIT image) the
booted FIT kernel image is inspected with dumpimage: a signed image
indicates a verified-boot setup, an unsigned one indicates secure boot
is not in use.  Note this checks signature presence, not that the
bootloader actually enforces verification.
"""

import argparse
import glob
import logging
import re
import subprocess
import sys
from pathlib import Path

from checkbox_support.snap_utils.system import (
    add_hostfs_prefix,
    get_kernel_snap,
    on_ubuntucore,
)

EFI_DIR = "/sys/firmware/efi"
EFIVARS_DIR = EFI_DIR + "/efivars"
# Same variable (and GUID) that boot_mode_test.py and mokutil read
SECUREBOOT_VAR = (
    EFIVARS_DIR + "/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
)
FIT_IMAGE_GLOBS = [
    "/boot/*.itb",
    "/boot/*.fit",
    "/boot/kernel.img",
    "/boot/uboot/*/kernel.img",
]


def get_uefi_state():
    """Read the secure boot state from the SecureBoot EFI variable."""
    if not Path(EFIVARS_DIR).is_dir():
        raise SystemExit(
            "System booted in EFI mode but {} is not available; "
            "cannot read the SecureBoot variable".format(EFIVARS_DIR)
        )
    var = Path(SECUREBOOT_VAR)
    if not var.is_file():
        logging.debug("%s not present", SECUREBOOT_VAR)
        # No SecureBoot variable: the firmware does not implement
        # secure boot, so it cannot be enforced.
        return "disabled"
    try:
        data = var.read_bytes()
    except OSError as err:
        raise SystemExit("Cannot read {}: {}".format(SECUREBOOT_VAR, err))
    # EFI variable layout: 4 attribute bytes followed by the value
    if len(data) < 5:
        raise SystemExit(
            "Unexpected SecureBoot variable content: {!r}".format(data)
        )
    logging.debug("SecureBoot variable value byte: %d", data[4])
    return "enabled" if data[4] == 1 else "disabled"


def find_fit_image():
    """Locate the booted FIT kernel image."""
    if on_ubuntucore():
        kernel = get_kernel_snap()
        if kernel:
            path = add_hostfs_prefix(
                "/snap/{}/current/kernel.img".format(kernel)
            )
            if Path(path).is_file():
                logging.debug("Using kernel snap image: %s", path)
                return path
    patterns = [add_hostfs_prefix(pattern) for pattern in FIT_IMAGE_GLOBS]
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            logging.debug("Using FIT image: %s", matches[0])
            return matches[0]
    raise SystemExit(
        "No FIT kernel image found (searched: {})".format(", ".join(patterns))
    )


def get_fit_state(image_path):
    """Derive the secure boot state from a FIT image's signatures."""
    try:
        output = subprocess.check_output(
            ["dumpimage", "-l", image_path],
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise SystemExit(
            "dumpimage not found - install u-boot-tools to check "
            "FIT image signatures"
        )
    except subprocess.CalledProcessError as err:
        raise SystemExit(
            "dumpimage failed on {}: {}".format(image_path, err.output)
        )
    except subprocess.TimeoutExpired:
        raise SystemExit("dumpimage timed out on {}".format(image_path))
    if not output.startswith("FIT description"):
        raise SystemExit(
            "{} is not a FIT image:\n{}".format(image_path, output)
        )
    logging.debug("dumpimage output:\n%s", output)
    if re.search(r"^\s*Sign value\s*:", output, re.M):
        return "enabled"
    return "disabled"


def get_secure_boot_state():
    """Detect the platform type and return the secure boot state."""
    if Path(EFI_DIR).is_dir():
        logging.debug("UEFI system, reading the SecureBoot EFI variable")
        return get_uefi_state()
    logging.info("Non-UEFI system, checking the FIT image signature")
    return get_fit_state(find_fit_image())


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "expected",
        choices=["enabled", "disabled"],
        help="the expected secure boot state",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="enable debug output",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    state = get_secure_boot_state()
    print("Secure boot state: {}".format(state))
    if state != args.expected:
        raise SystemExit(
            "FAIL: expected secure boot to be {}, found {}".format(
                args.expected, state
            )
        )
    print("PASS: secure boot is {}".format(state))
    return 0


if __name__ == "__main__":
    sys.exit(main())
