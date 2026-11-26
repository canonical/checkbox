# Copyright 2019-2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Jonathan Cave <jonathan.cave@canonical.com>

import os
import re
import subprocess as sp
import yaml

from checkbox_ng.support.parsers.kernel_cmdline import parse_kernel_cmdline
from checkbox_ng.support.release_info import (
    get_release_file_content,
    get_release_info,
)
from checkbox_ng.support.snap_utils.asserts import decode
from checkbox_ng.support.snap_utils.asserts import model_to_resource
from checkbox_ng.support.snap_utils.snapd import Snapd
from plainbox.impl.snap import in_classic_snap  # noqa: F401
from plainbox.impl.snap import in_strict_snap


def on_ubuntucore():
    """
    Return True if the host OS is Ubuntu Core.

    The host os-release is used (via hostfs when running in a strict snap)
    because the snap's own /etc/os-release comes from its base snap, which
    always reports Ubuntu Core.
    """
    return any(
        line.partition("=")[0] == "ID"
        and line.partition("=")[2].strip('"') == "ubuntu-core"
        for line in get_release_file_content().splitlines()
    )


def get_series():
    """Return the host OS version (e.g. "24.04" or "24" on Ubuntu Core)."""
    return get_release_info().get("release")


def get_kernel_snap():
    model = next(decode(Snapd().get_assertions("model")), None)
    if model:
        # convert to resource to handle presence of track info
        resource = model_to_resource(model)
        return resource.get("kernel")
    return None


def get_gadget_snap():
    model = next(decode(Snapd().get_assertions("model")), None)
    if model:
        # convert to resource to handle presence of track info
        resource = model_to_resource(model)
        return resource.get("gadget")
    return None


def get_bootloader():
    bootloader = None
    gadget_yaml = f"/snap/{get_gadget_snap()}/current/meta/gadget.yaml"
    with open(gadget_yaml) as f:
        data = yaml.load(f)
        for k in data["volumes"].keys():
            bootloader = data["volumes"][k]["bootloader"]
    return bootloader


def get_lk_bootimg_path():
    with open("/proc/cmdline") as f:
        cmdline = f.readline()
    result = parse_kernel_cmdline(cmdline)
    try:
        snap_kernel = result.params["snap_kernel"]
        # get the bootimg matrix using `lk-boot-env -r`
        snap_boot_selection = sp.run(
            ["lk-boot-env", "-r", "/dev/disk/by-partlabel/snapbootsel"],
            check=True,
            stdout=sp.PIPE,
        ).stdout.decode()
        match = re.search(
            rf"bootimg_matrix\s+\[(.*?)\]\[{snap_kernel}\]",
            snap_boot_selection,
            re.M,
        )
        if match:
            path = os.path.join("/dev/disk/by-partlabel", match.group(1))
    except (KeyError, AttributeError, FileNotFoundError):
        path = "unknown"
    return path


def add_hostfs_prefix(path):
    if in_strict_snap():
        if os.path.isabs(path):
            path = path.split(os.path.sep, 1)[1]
        return os.path.join(os.path.sep, "var", "lib", "snapd", "hostfs", path)
    return path
