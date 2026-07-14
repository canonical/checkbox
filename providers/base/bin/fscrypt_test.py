#!/usr/bin/env python3
"""
script to test fscrypt support

Copyright (C) 2025 Canonical Ltd.

Authors
  Alexis Cellier <alexis.cellier@canonical.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3,
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

The purpose of this script is to make a small fscrypt test on a generated
ext4 disk image to validate the filesystem encryption support.
"""

import os
import subprocess
import tempfile
import re
from pathlib import Path


def main():
    """
    Create an ext4 disk image, mount it, setup fscrypt and use it with a simple
    file
    """
    with tempfile.TemporaryDirectory() as tmp_path:
        tmp = Path(tmp_path)
        mnt = tmp / "mnt"
        img = tmp / "fs.img"
        key_file = tmp / "key"
        test_dir = mnt / "test"
        test_file = test_dir / "test.txt"
        test_content = "test"
        fscrypt_config = Path("/etc/fscrypt.conf")
        fscrypt_setup = fscrypt_config.exists()

        # Create a 50MB file
        subprocess.check_call(["truncate", "-s", "50M", str(img)])

        mnt.mkdir(parents=True, exist_ok=True)

        # Make ext4 image with encryption support
        subprocess.check_call(
            ["mkfs.ext4", "-F", "-O", "encrypt,stable_inodes", str(img)]
        )

        # Mount it
        subprocess.check_call(["mount", str(img), str(mnt)])

        try:
            # Setup fscrypt
            print("Setup fscrupt")
            if not fscrypt_setup:
                subprocess.run(
                    ["fscrypt", "setup", "--force"],
                    input="n\n",
                    text=True,
                    check=True,
                )
            subprocess.run(
                ["fscrypt", "setup", "--force", str(mnt)],
                input="n\n",
                text=True,
                check=True,
            )

            # Confirm fscrypt is enabled
            output = subprocess.check_output(
                ["fscrypt", "status"],
                text=True,
            )
            found = False
            pattern = re.compile(
                "^{}.*supported\\s*Yes$".format(re.escape(str(mnt)))
            )
            for line in output.splitlines():
                if pattern.match(line):
                    found = True
                    break
            if not found:
                raise SystemExit("Failed to setup fscrypt")

            # Write random key
            with key_file.open("wb") as f:
                f.write(os.urandom(32))

            # Make test directory
            test_dir.mkdir(parents=True, exist_ok=True)

            # Encrypt directory
            subprocess.check_call(
                [
                    "fscrypt",
                    "encrypt",
                    "--quiet",
                    "--source=raw_key",
                    "--name=test_key",
                    "--key={}".format(str(key_file)),
                    str(test_dir),
                ]
            )

            # Write a file inside
            with test_file.open("w") as f:
                f.write(test_content)

            # Lock the directory
            subprocess.check_call(["fscrypt", "lock", str(test_dir)])

            # Should not be able to list the file
            if test_file.exists():
                raise SystemExit("File should not be accessible when locked")
            print("File correctly inaccessible when locked")

            # Unlock the directory
            subprocess.check_call(
                [
                    "fscrypt",
                    "unlock",
                    "--key={}".format(str(key_file)),
                    str(test_dir),
                ]
            )

            with test_file.open("r") as f:
                content = f.read().strip()
            if content != test_content:
                print("Expected: {} / Got: {}".format(test_content, content))
                raise SystemExit("File contents not correct after unlock")
            print("File is accessible and content is correct after unlock")
        finally:
            subprocess.check_call(["umount", str(mnt)])
            if not fscrypt_setup and fscrypt_config.exists():
                fscrypt_config.unlink()


if __name__ == "__main__":
    main()
