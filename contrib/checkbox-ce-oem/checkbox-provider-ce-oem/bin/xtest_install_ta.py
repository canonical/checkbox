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
    # avoid picking up unrelated duplicates. Restrict the search to
    # the snap's currently active revision (the "current" symlink
    # snapd maintains) rather than the whole snap root: a stale
    # optee_armtz left behind in an older, still-retained revision
    # would otherwise be picked up too and falsely reported as a
    # duplicate.
    current_revision = os.path.join("/var/snap", snap_name, "current")
    print("Looking for TA path...", flush=True)
    ta_folders = [
        os.path.join(dirpath, "optee_armtz")
        for dirpath, dirnames, _ in os.walk(current_revision)
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
