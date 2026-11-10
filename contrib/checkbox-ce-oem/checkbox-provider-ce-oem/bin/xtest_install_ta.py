#!/usr/bin/env python3

from look_up_xtest import look_up_app
from subprocess import run, CalledProcessError
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
    # avoid picking up unrelated duplicates. On real devices the TA
    # lives directly under the snap's persistent common data dir, e.g.
    # /var/snap/<snap_name>/common/lib/optee_armtz — a sibling of
    # "current"/the numbered revision dirs, not nested under them — so
    # the search root here is the whole snap dir, not ".../current".
    # followlinks is left at its default (False): "current" (and any
    # other numbered revision dir) is a symlink to a revision dir, so
    # not following it avoids walking that same revision data twice
    # (once under its real numbered name, once via "current") and
    # falsely reporting duplicate TA sources.
    snap_root = os.path.join("/var/snap", snap_name)
    print("Looking for TA path...", flush=True)
    ta_folders = [
        os.path.join(dirpath, "optee_armtz")
        for dirpath, dirnames, _ in os.walk(snap_root)
        if "optee_armtz" in dirnames
    ]
    if not ta_folders:
        raise SystemError(
            "Not able to find TA in the {} snap!".format(snap_name)
        )
    elif len(ta_folders) > 1:
        raise SystemError(
            "Found multiple TA sources in the {} snap."
            "Please make sure only one exist in the system!".format(snap_name)
        )
    return ta_folders[0]


def install_ta(xtest, path):
    cmd = ["timeout", "30", xtest, "--install-ta", path]
    print("Attempting to install TA...", flush=True)
    run_command(cmd)
    print("TA install succeeded!", flush=True)


def main():
    # XTEST is a required environ for this job and always points to the
    # xtest snap's own name, so it can be used directly as the snap name.
    snap_name = os.environ["XTEST"]
    xtest = look_up_app("xtest", snap_name)
    ta_path = find_ta_path(snap_name)
    install_ta(xtest, ta_path)


if __name__ == "__main__":
    main()
