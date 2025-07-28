#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Philip Meulengracht <philip.meulengracht@canonical.com>

import argparse
import os
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
    raise SystemExit(f"platform not supported for remodeling test: {plt}")


# Currently images used in certifications are sourced from cdimage,
# those images builds using the models supplied in canonical/models.
# Make sure we use the same models that come from the same authority,
# otherwise remodeling will fail.
def download_model(uc_ver):
    base_uri = "https://raw.githubusercontent.com/canonical/models/"
    branch = "refs/heads/master/"
    model = f"ubuntu-core-{uc_ver}-{get_platform()}-dangerous.model"
    print(f"downloading model for remodeling: {base_uri + branch + model}")
    path, _ = urlretrieve(base_uri + branch + model)
    return path


# downloads a snap to the tmp folder
def download_snap(name, out, channel):
    dir = os.getcwd()
    os.chdir("/tmp")
    subprocess.run(
        [
            "snap",
            "download",
            name,
            f"--channel=latest/{channel}",
            f"--basename={out}",
        ]
    )
    os.chdir(dir)


def download_snaps(uc_ver):
    # use stable for remodel, we are not testing the snaps we are
    # remodeling to, but rather the process works.
    channel = "stable"
    download_snap(f"core{uc_ver}", "base", channel)
    if "pi" in get_platform():
        download_snap("pi", "gadget", f"--channel={uc_ver}/{channel}")
        download_snap("pi-kernel", "kernel", f"--channel={uc_ver}/{channel}")
    else:
        download_snap("pc", "gadget", f"--channel={uc_ver}/{channel}")
        download_snap("pc-kernel", "kernel", f"--channel={uc_ver}/{channel}")


def main():
    """Run remodel of an Ubuntu Core host."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "target",
        help="which verison of ubuntu-core that should be remodeled to",
        choices=["22", "24"],
    )

    # resolve the snaps for the remodel if offline has been requested
    # (currently offline was used for testing in certain scenarios during
    # test development) - for normal testing offline should not be needed
    parser.add_argument(
        "--offline",
        help="whether the remodel should be offline",
        action="store_true",
    )
    args = parser.parse_args()

    # resolve the model for the current platform
    model_path = download_model(args.target)

    if args.offline:
        download_snaps(args.target)

        # instantiate the offline remodel
        print("initiating offline device remodel")
        subprocess.run(
            [
                "sudo",
                "snap",
                "remodel",
                "--offline",
                "--snap",
                "/tmp/base.snap",
                "--assertion",
                "/tmp/base.assert",
                "--snap",
                "/tmp/gadget.snap",
                "--assertion",
                "/tmp/gadget.assert",
                "--snap",
                "/tmp/kernel.snap",
                "--assertion",
                "/tmp/kernel.assert",
                model_path,
            ]
        )
    else:
        # instantiate the remodel
        print("initiating device remodel")
        subprocess.run(["sudo", "snap", "remodel", model_path])


if __name__ == "__main__":
    exit(main())
