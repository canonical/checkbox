#!/usr/bin/env python3

from look_up_xtest import look_up_app
from subprocess import run, CalledProcessError
import glob
import os


def run_command(cmd, capture_output=True, text=True, check=True):
    try:
        result = run(
            cmd, capture_output=capture_output, text=text, check=check
        )
        return result.stdout.strip() if capture_output else None
    except CalledProcessError as e:
        raise SystemExit("Error: {}".format(e))


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
    cmd = ["timeout", "30", xtest, "--install-ta", path]
    print("Attempting to install TA...", flush=True)
    run_command(cmd)
    print("TA install succeeded!", flush=True)


def main():
    xtest = look_up_app("xtest", os.environ.get("XTEST"))
    ta_path = find_ta_path()
    install_ta(xtest, ta_path)


if __name__ == "__main__":
    main()
