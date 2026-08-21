#!/usr/bin/env python3

from look_up_xtest import look_up_app
from subprocess import run
import glob
import os


def find_ta_path():
    dir = "/var/snap/**/optee_armtz"
    print("Looking for TA path...", flush=True)
    ta_folder = glob.glob(dir, recursive=True)
    if not ta_folder:
        raise SystemError("Not able to find TA in the system!")
    elif len(ta_folder) > 1:
        raise SystemError(
            "Found multiple TA sources."
            "Please make sure only one exist in the system!"
        )
    return ta_folder[0]


def install_ta(xtest, path):
    """Install every TA under path into OP-TEE secure storage, one file at
    a time: xtest stops at the first TA the TEE rejects (subkey-signed
    TAs fail the secure-storage bootstrap with TEEC_ERROR_SECURITY), so a
    whole-directory install would leave the remaining TAs uninstalled.
    Returns the rejected TA file names.
    """
    print("Attempting to install TA...", flush=True)
    rejected = []
    for ta in sorted(glob.glob(os.path.join(path, "*.ta"))):
        result = run(
            ["timeout", "30", xtest, "--install-ta", ta],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            rejected.append(os.path.basename(ta))
            print(
                "Rejected {}: {}".format(
                    os.path.basename(ta), result.stderr.strip()
                ),
                flush=True,
            )
    print(
        "TA install done, {} rejected: {}".format(
            len(rejected), " ".join(rejected) or "-"
        ),
        flush=True,
    )
    return rejected


def main():
    xtest = look_up_app("xtest", os.environ.get("XTEST"))
    ta_path = find_ta_path()
    install_ta(xtest, ta_path)


if __name__ == "__main__":
    main()
