#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Philip Meulengracht <philip.meulengracht@canonical.com>

import os
import sys
import platform
import subprocess
from urllib.request import urlretrieve


def get_platform():
    plt = platform.platform()
    if "raspi-aarch64" in plt:
        return "pi-arm64"
    elif "raspi" in plt:
        return "pi-armhf"
    elif "x86_64" in plt:
        return "amd64"
    raise Exception(f"unrecognized platform {plt}")


def resolve_target_remodel():
    runtime = os.getenv("CHECKBOX_RUNTIME", "/snap/checkbox/current")
    if "checkbox20" in runtime:
        return "uc22"
    elif "checkbox22" in runtime:
        return "uc24"
    raise Exception(f"unsupported version for remodel: {runtime}")


def resolve_model(uc_ver):
    base_uri = "https://raw.githubusercontent.com/canonical/models/"
    branch = "refs/heads/master/"
    model = f"ubuntu-core-{uc_ver}-{get_platform()}-dangerous.model"
    print(f"resolving model for remodeling: {base_uri + branch + model}")
    path, _ = urlretrieve(base_uri + branch + model, f"uc-{uc_ver}.model")
    return path


def resolve_snaps(uc_ver):
    subprocess.run(
        ["snap", "download", f"core{uc_ver}", f"--basename=core{uc_ver}"]
    )
    # for the kernel snap use beta
    if "pi" in get_platform():
        subprocess.run(
            [
                "snap",
                "download",
                "pi",
                f"--channel={uc_ver}/edge",
                "--basename=gadget",
            ]
        )
        subprocess.run(
            [
                "snap",
                "download",
                "pi-kernel",
                f"--channel={uc_ver}/beta",
                "--basename=kernel",
            ]
        )
    else:
        subprocess.run(
            [
                "snap",
                "download",
                "pc",
                f"--channel={uc_ver}/edge",
                "--basename=gadget",
            ]
        )
        subprocess.run(
            [
                "snap",
                "download",
                "pc-kernel",
                f"--channel={uc_ver}/beta",
                "--basename=kernel",
            ]
        )


def main():
    """Run remodel of an Ubuntu Core host."""

    uc_ver = ""
    if len(sys.argv) > 1:
        uc_ver = sys.argv[1]
    else:
        uc_ver = resolve_target_remodel()

    # resolve the model for the current platform
    model_path = resolve_model(uc_ver)

    # resolve the snaps for the remodel if offline has been requested
    # (currently offline was used for testing in certain scenarios during
    # test development) - for normal testing offline should not be needed
    offline = False
    if len(sys.argv) > 2 and sys.argv[2] == "offline":
        offline = True

    if offline:
        resolve_snaps(uc_ver)

        # instantiate the offline remodel
        print("initiating offline device remodel")
        subprocess.run(
            [
                "sudo",
                "snap",
                "remodel",
                "--offline",
                "--snap",
                f"core{uc_ver}.snap",
                "--assertion",
                f"core{uc_ver}.assert",
                "--snap",
                "gadget.snap",
                "--assertion",
                "gadget.assert",
                "--snap",
                "kernel.snap",
                "--assertion",
                "kernel.assert",
                model_path,
            ]
        )
    else:
        # instantiate the remodel
        print("initiating device remodel")
        subprocess.run(["sudo", "snap", "remodel", model_path])


if __name__ == "__main__":
    exit(main())
