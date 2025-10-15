# This file is part of Checkbox.
#
# Copyright 2017-2025 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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
"""
This module provides functions to handle sudo password handling.
The password stored by this module is not encrypted in any way and may be
transmitted over network in plaintext, so it's up to the operator to use
secure connection.
"""

import gc
import getpass
import hashlib
import logging
import os
import sys

from plainbox.i18n import gettext as _
from subprocess import (
    check_output,
    check_call,
    CalledProcessError,
    STDOUT,
    DEVNULL,
    SubprocessError,
)


logger = logging.getLogger("sudo_broker")


def is_passwordless_sudo():
    """
    Check if system can run sudo without pass.
    """
    # this command fails if passowrdless sudo is not configured because
    # --reset-timestamp will trigger re-authentication
    # --non-interactive will make the command fail if user interaction is due
    # We no longer use `-A` (ASKPASS) because sudo-rs doesn't currently support
    # it
    check_passwordless_sudo_cmd = [
        "sudo",
        "--non-interactive",
        "--reset-timestamp",
        "true",
    ]
    if os.geteuid() == 0:
        # even though we run as root, we still may need to use sudo to switch
        # to a normal user for jobs not requiring root, so let's see if sudo
        # actually works.
        try:
            check_output(
                check_passwordless_sudo_cmd,
                stderr=STDOUT,
                universal_newlines=True,
            )
        except (SubprocessError, OSError) as exc:
            try:
                print(exc.output)
            except AttributeError:
                pass
            raise SystemExit("Checkbox is unable to run sudo: {}".format(exc))
        return True
    try:
        check_output(check_passwordless_sudo_cmd, stderr=STDOUT)
    except CalledProcessError:
        return False
    return True


def validate_pass(password):
    cmd = [
        "sudo",
        "--prompt=",
        "--reset-timestamp",
        "--stdin",
        "--user",
        "root",
        "true",
    ]
    r, w = os.pipe()
    os.write(w, password + b"\n")
    os.close(w)
    try:
        check_call(cmd, stdin=r, stdout=DEVNULL, stderr=DEVNULL)
        return True
    except CalledProcessError:
        return False


class SudoPasswordProvider:
    def __init__(self):
        self._sudo_password = None
        self._already_checked = False
        self._is_passwordless = False

    @property
    def is_passwordless(self):
        if not self._already_checked:
            self._is_passwordless = is_passwordless_sudo()
            self._already_checked = True
        return self._is_passwordless

    def get_sudo_password(self):
        if self.is_passwordless:
            return None
        if self._sudo_password:
            return self._sudo_password
        pass_is_correct = False
        while not pass_is_correct:
            prompt = "Enter sudo password:\n"
            password = getpass.getpass(prompt).encode(sys.stdin.encoding)
            pass_is_correct = validate_pass(password)
            if not pass_is_correct:
                print("Sorry, try again.")
        self._sudo_password = password
        return password


sudo_password_provider = SudoPasswordProvider()
