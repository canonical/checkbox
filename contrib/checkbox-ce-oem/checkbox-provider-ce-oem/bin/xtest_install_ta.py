#!/usr/bin/env python3

import look_up_xtest
from subprocess import run, CalledProcessError


def run_command(cmd, capture_output=True, text=True, check=True):
    try:
        result = run(
            cmd, capture_output=capture_output, text=text, check=check
        )
        return result.stdout.strip() if capture_output else None
    except CalledProcessError as e:
        raise SystemExit("Error: {}".format(e))


def find_ta_path():
    print("Looking for TA path...", flush=True)
    cmd = ["find", "/var/snap", "-wholename", "*/lib/optee_armtz"]
    path = run_command(cmd)
    if path:
        print("Found TA file in {}".format(path))
    return path


def install_ta(xtest, path):
    cmd = [xtest, "--install-ta", path]
    print("Attempting to install TA...", flush=True)
    run_command(cmd)
    print("TA install succeeded!", flush=True)


def find_tee_supplicant():
    cmd = ["pgrep", "-f", "tee-supplicant"]
    return run_command(cmd)


def enable_tee_supplicant(tee):
    print("Looking for tee-supplicant process...", flush=True)
    output = find_tee_supplicant()
    if not output:
        print("Not found tee-supplicant process...", flush=True)
        print("Attempting to start tee-supplicant...", flush=True)
        cmd = ["snap", "start", tee]
        run_command(cmd)
    print(
        "tee-supplicant started, and PID is {}...".format(
            find_tee_supplicant()
        ),
        flush=True,
    )


def main():
    xtest = look_up_xtest.main()
    enable_tee_supplicant(xtest["tee"])
    ta_path = find_ta_path()
    install_ta(xtest["xtest"], ta_path)


if __name__ == "__main__":
    main()
