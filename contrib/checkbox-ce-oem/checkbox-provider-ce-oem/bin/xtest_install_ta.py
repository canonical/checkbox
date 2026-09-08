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


def find_ta_path(snap_name):
    # TAs may also be bundled by other snaps (e.g. the board's gadget
    # snap), so only look inside the xtest snap's own directory to
    # avoid picking up unrelated duplicates.
    dir = "/var/snap/{}/**/optee_armtz".format(snap_name)
    print("Looking for TA path...", flush=True)
    ta_folder = glob.glob(dir, recursive=True)
    if not ta_folder:
        raise SystemError(
            "Not able to find TA in the {} snap!".format(snap_name)
        )
    elif len(ta_folder) > 1:
        raise SystemError(
            "Found multiple TA sources in the {} snap."
            "Please make sure only one exist in the system!".format(snap_name)
        )
    return ta_folder[0]


def install_ta(xtest, path):
    cmd = ["timeout", "30", xtest, "--install-ta", path]
    print("Attempting to install TA...", flush=True)
    run_command(cmd)
    print("TA install succeeded!", flush=True)


def main():
    xtest = look_up_app("xtest", os.environ.get("XTEST"))
    # xtest is returned as "<snap_name>.xtest"
    snap_name = xtest.rsplit(".", 1)[0]
    ta_path = find_ta_path(snap_name)
    install_ta(xtest, ta_path)


if __name__ == "__main__":
    main()
