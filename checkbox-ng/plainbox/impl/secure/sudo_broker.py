# This file is part of Checkbox.
#
# Copyright 2017-2019 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
This module provides means for transmitting and storing password securely.
It's meant to be used for remote sessions talking over an insecure channel.

'Master key' in context of this module is the key pair used to encrypt/decrypt
the sudo password transmitted.  'Master passphrase' is the passphrase used to
export/import the master to/from the outside world.

Clients of this module have to pass messages between the broker and provider
- this decoupling relieves some complexity of the RPC solutions using this
module.
"""

import gc
import getpass
import hashlib
import logging
import os
import sys

from Crypto.PublicKey import RSA
from plainbox.i18n import gettext as _
from subprocess import check_call, CalledProcessError, DEVNULL, SubprocessError


logger = logging.getLogger("sudo_broker")


class EphemeralKey():
    """
    One-time asymetric encryption helper.
    Use it to get passhprase for the master key.

    This is provided, so that users of the SudoBroker/SudoProvider classes
    don't have to import Crypto themselves (making the cryptography backend
    more interchangeable)
    """

    def __init__(self):
        self._key = RSA.generate(2048)

    @property
    def public_key(self):
        if not self._key:
            raise Exception("Key already used up!")
        return self._key.publickey().exportKey()

    def decrypt(self, ciphertext):
        if not self._key:
            raise Exception("Key already used up!")
        plaintext = self._key.decrypt(ciphertext)
        self._key = None
        return plaintext


class SudoBroker():
    """
    Instances of this class should be used by pieces of code that need the
    password. E.g. ExecutionController classes.
    """
    def __init__(self, master_pem=None, master_passphrase=None):
        if master_pem:
            self._master_key = RSA.importKey(master_pem, master_passphrase)
        else:
            self._master_key = RSA.generate(2048)

    def get_master_pem(self, passphrase):
        """Return Master Key in PEM format encrypted with passphrase."""
        return self._master_key.exportKey('PEM', passphrase)

    @property
    def master_public(self):
        """Public key for the SudoProvider to use."""
        return self._master_key.publickey().exportKey()

    def decrypt_password(self, ciphertext):
        """
        Get plaintext version of the password.

        :param ciphertext:
            Bytes sequence, as returned by the SudoProvider.encrypted_password.
        :returns:
            Bytes with plaintext password.
        """
        return self._master_key.decrypt(ciphertext)

    def export_key(self, passphrase):
        """
        Export key for long-term storage.

        :param passphrase:
            Bytes sequence that will be used to encrypt the key.
        :returns:
            Bytes with a private key in PEM format.
        """
        return self._master_key.exportKey(passphrase=passphrase)


class SudoProvider():
    """
    This is the user-facing part of the duo.
    Its main purpose is to ask user for password.
    """

    DEFAULT_PROMPT = 'Enter sudo password:\n'

    def __init__(self, master_pub_key, prompt=DEFAULT_PROMPT):
        self._master_pub_key = RSA.importKey(master_pub_key)
        self._prompt = prompt
        self._encrypted_pass = None
        self._master_passphrase = None

    def ask_for_password(self):
        """
        The password that's taken from the user serves two purposes:
        1) being sent back to the SudoBroker, encrypted with the master key
        2) its hash, for bringing back master_key in a new SudoBroker instance
        """
        password = getpass.getpass(self._prompt).encode(sys.stdin.encoding)
        self._master_passphrase = hashlib.sha512(password).hexdigest()
        self._encrypted_pass = self._master_pub_key.encrypt(password, '_')

        # pseudo-security overkill follows
        del password
        gc.collect()

    @property
    def encrypted_password(self):
        if not self._encrypted_pass:
            self.ask_for_password()
        return self._encrypted_pass

    def clear_password(self):
        self._encrypted_pass = None

    def get_master_passphrase(self, temp_key):
        """
        Get passphrase to decrypt the master key.

        :param temp_key:
            Bytes sequence with a public part of one-time ephemeral key,
            that will be used to encrypt the passphrase
        :returns:
            Bytes sequence with encrypted master passphrase.
        """
        key = RSA.importKey(temp_key)
        return key.encrypt(self._master_passphrase.encode('utf-8'), '_')

def is_passwordless_sudo():
    """
    Check if system can run sudo without pass.
    """
    if os.geteuid() == 0:
        # even though we run as root, we still may need to use sudo to switch
        # to a normal user for jobs not requiring root, so let's see if sudo
        # actually works.
        try:
            check_call(['sudo', '-A', '-k', 'true'], stdout=DEVNULL, stderr=DEVNULL)
        except (SubprocessError, OSError)  as exc:
            logger.error(_("Unable to run sudo %s"), exc)
            raise SystemExit(1)
        return True
    # running sudo with -A will try using ASKPASS envvar that should specify
    # the program to use when asking for password
    # If the system is configured to not ask for password, this will silently
    # succeed. If the pass is required, it'll return 1 and not ask for pass,
    # as the askpass program is not provided
    try:
        check_call(['sudo', '-A', '-k', 'true'], stdout=DEVNULL, stderr=DEVNULL)
    except CalledProcessError:
        return False
    return True


def validate_pass(password):
    cmd = ['sudo', '--prompt=', '--reset-timestamp', '--stdin',
           '--user', 'root', 'true']
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
            prompt = 'Enter sudo password:\n'
            password = getpass.getpass(prompt).encode(sys.stdin.encoding)
            pass_is_correct = validate_pass(password)
            if not pass_is_correct:
                print('Sorry, try again.')
        self._sudo_password = password
        return password

sudo_password_provider = SudoPasswordProvider()
