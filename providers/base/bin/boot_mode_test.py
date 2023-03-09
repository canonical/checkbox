#!/usr/bin/env python3
"""
Test that the computer booted in EFI mode, with Secure Boot active.

Copyright (C) 2016 Canonical Ltd.

Authors:
  Rod Smith <rod.smith@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import sys
import logging
from argparse import ArgumentParser


def do_tests(check):
    """Dispatcher for the requested tests.

    :returns:
        return code from requested check.
    """
    if check == 'efi':
        return efi_boot_check()
    elif check == 'reboot_firmware':
        return reboot_to_firmware_check()
    else:
        return secure_boot_check()


def efi_boot_check():
    """Test that the computer booted in EFI mode

    :returns:
        0 if /sys/firmware/efivars exists meaning booted in EFI mode
        1 if booted in BIOS mode
    """
    efi_dir = "/sys/firmware/efi/"
    if os.path.isdir(efi_dir):
        logging.info("PASS: System booted in EFI mode")
        return 0
    else:
        logging.error("FAIL: System did not boot in EFI mode")
        return 1


def reboot_to_firmware_check():
    """Test that the computer supports the reboot-to-firmware feature.

    :returns:
        0 if the feature IS supported (pass)
        1 if the feature is NOT supported (fail)
    """
    osis_dir = "/sys/firmware/efi/efivars/"
    osis_var = osis_dir + \
        "OsIndicationsSupported-8be4df61-93ca-11d2-aa0d-00e098032b8c"
    if os.path.isdir(osis_dir):
        if os.path.isfile(osis_var):
            with open(osis_var) as fh:
                try:
                    fw_info = fh.read()
                except IOError:
                    logging.error("FAIL: I/O error reading EFI data")
                    return 1
            if ord(fw_info[4]) & 1:
                logging.info("PASS: Reboot-to-firmware feature is present.")
                return 0
            else:
                logging.error("FAIL: Reboot-to-firmware feature is missing.")
                return 1
        else:
            logging.info("FAIL: OsIndicationsSupported variable not present.")
            return 1
    else:
        logging.info("FAIL: System did NOT boot in EFI mode.")
        return 1


def secure_boot_check():
    """Test that the computer booted with Secure Boot active.

    :returns:
        0 if Secure Boot is active
        1 if Secure Boot is inactive (could be disabled, not supported,
          or not booted in EFI mode)
    """
    sb_dir = "/sys/firmware/efi/efivars/"
    sb_var = sb_dir + "SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
    if os.path.isdir(sb_dir):
        if os.path.isfile(sb_var):
            with open(sb_var) as fh:
                try:
                    sb_info = fh.read()
                except IOError:
                    logging.error("FAIL: I/O error reading EFI data")
                    return 1
            if ord(sb_info[4]) == 1:
                logging.info("PASS: System booted with Secure Boot active.")
                return 0
            else:
                logging.error("FAIL: System booted with "
                              "Secure Boot available but inactive.")
                return 1
        else:
            # NOTE: Normally, lack of sb_var indicates that the system
            # doesn't support SB, as on many pre-Windows 8 UEFI systems.
            # Below is therefore a bit harsh, but is done to ensure that
            # no system slips through because it supports Secure Boot but
            # does not create the sb_var when SB is inactive or has never
            # been activated.
            logging.error("FAIL: System does not appear to support "
                          "Secure Boot.")
            return 1
    else:
        logging.info("FAIL: System did NOT boot in EFI mode.")
        return 1


def main():
    parser = ArgumentParser()
    parser.add_argument('check',
                        choices=['efi', 'secureboot', 'reboot_firmware'],
                        help='The type of check to perform')
    args = parser.parse_args()

    FORMAT = '%(levelname)s: %(message)s'
    logging.basicConfig(level=logging.INFO, format=FORMAT)
    return do_tests(args.check)


if __name__ == '__main__':
    sys.exit(main())
