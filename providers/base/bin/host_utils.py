#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Shane McKee <shane.mckee@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""Shared utilities for host Vulkan test helpers."""

import json
import os
import shutil
import subprocess
import sysconfig


def get_arch_triple():
    """Return the Debian multiarch triple for the current architecture."""
    triple = sysconfig.get_config_var("MULTIARCH")
    if triple is None:
        raise RuntimeError("could not determine multiarch triple")
    return triple


def find_plz_run():
    """Return the path to plz-run from PATH."""
    return shutil.which("plz-run")


_VIRTUAL_ICD_LIBS = {"libvulkan_gfxstream.so", "libvulkan_virtio.so"}

# Maps prime-select vendor name to ICD filename prefixes.
# Used to filter the ICD list to the PRIME-selected GPU on multi-GPU systems.
_PRIME_VENDOR_ICD_PREFIXES = {
    "intel": ("intel",),
    "nvidia": ("nvidia",),
    "amd": ("radeon", "amd"),
}

# Maps PCI vendor ID from /sys/class/drm to ICD filename prefixes.
_DRM_VENDOR_ICD_PREFIXES = {
    "0x8086": ("intel",),
    "0x1002": ("radeon", "amd"),
    "0x10de": ("nvidia",),
}


def prime_selected_vendor():
    """Return the GPU vendor chosen by prime-select, or None.

    Returns one of the keys in _PRIME_VENDOR_ICD_PREFIXES, or None if
    prime-select is not installed, returns an unrecognised value (e.g.
    'on-demand'), or fails for any reason.
    """
    try:
        output = (
            subprocess.check_output(
                ["/usr/bin/prime-select", "query"],
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
            )
            .strip()
            .lower()
        )
        return output if output in _PRIME_VENDOR_ICD_PREFIXES else None
    except (FileNotFoundError, OSError, subprocess.CalledProcessError):
        return None


def _run_vulkaninfo(plz_run, arch_triple):
    """Run vulkaninfo --summary via plz-run with host libraries.

    vulkaninfo is executed inside a new mount/user namespace (via plz-run)
    so that it uses the host ICD stack instead of snap-bundled libraries.
    Returns the output string, or None if vulkaninfo fails.
    """
    ld_library_path = "/usr/lib/{arch}:/usr/lib".format(arch=arch_triple)
    try:
        return subprocess.check_output(
            [
                plz_run,
                "-u",
                "root",
                "-g",
                "root",
                "-E",
                "LD_LIBRARY_PATH={}".format(ld_library_path),
                "--",
                "/usr/bin/vulkaninfo",
                "--summary",
            ],
            universal_newlines=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError:
        return None


def _vendor_prefixes_from_vulkaninfo(output):
    """Return ICD filename prefixes for the first recognised GPU vendor in
    vulkaninfo --summary output, or None if no known vendor is found.

    Matches on the vendorID field which is unambiguous across driver versions
    and device names.  The field is right-padded with spaces for alignment,
    so each line is stripped before matching.
    """
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith("vendorID"):
            continue
        for vid, prefixes in _DRM_VENDOR_ICD_PREFIXES.items():
            if vid in stripped:
                return prefixes
    return None


def _active_vendor_prefixes():
    """Return ICD filename prefixes for the active GPU, or None.

    Detection order:
    1. prime-select — authoritative on PRIME multi-GPU systems.
    2. vulkaninfo via plz-run — available inside the Checkbox snap environment.
    3. DRM sysfs — works in any context without external tools.
    Returns None if no method identifies the vendor, which causes
    find_host_icd_filenames to fall back to all non-virtual ICDs.
    """
    vendor = prime_selected_vendor()
    if vendor is not None:
        return _PRIME_VENDOR_ICD_PREFIXES[vendor]
    try:
        arch_triple = get_arch_triple()
    except RuntimeError:
        return None
    plz_run = find_plz_run()
    output = (
        _run_vulkaninfo(plz_run, arch_triple) if plz_run is not None else None
    )
    if output is not None:
        prefixes = _vendor_prefixes_from_vulkaninfo(output)
        if prefixes is not None:
            return prefixes
    # Final fallback: read PCI vendor ID from DRM sysfs (no external tools
    # required — works even when plz-run is not in PATH).
    try:
        for entry in sorted(os.listdir("/sys/class/drm")):
            if not entry.startswith("card") or not entry[4:].isdigit():
                continue
            vendor_path = "/sys/class/drm/{}/device/vendor".format(entry)
            try:
                with open(vendor_path) as f:
                    vid = f.read().strip().lower()
                prefixes = _DRM_VENDOR_ICD_PREFIXES.get(vid)
                if prefixes is not None:
                    return prefixes
                break
            except OSError:
                continue
    except OSError:
        pass
    return None


def find_host_icd_filenames(vendor_prefixes=None):
    """Return a colon-separated list of Vulkan ICD files for the active GPU.

    Virtual ICDs (gfxstream, virtio) are always excluded — they hang on bare
    metal waiting for a virtual device that does not exist.

    When vendor_prefixes is provided, only ICDs whose filenames begin with
    one of the given prefixes are included.  Pass None to include all
    non-virtual ICDs (the Vulkan loader then selects the default device).
    """
    icd_dir = "/usr/share/vulkan/icd.d"
    result = []
    try:
        for name in sorted(os.listdir(icd_dir)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(icd_dir, name)
            try:
                with open(path) as f:
                    data = json.load(f)
                lib = os.path.basename(
                    data.get("ICD", {}).get("library_path", "")
                )
                if lib in _VIRTUAL_ICD_LIBS:
                    continue
                if vendor_prefixes and not any(
                    name.startswith(p) for p in vendor_prefixes
                ):
                    continue
                result.append(path)
            except (OSError, ValueError):
                result.append(path)
    except OSError:
        pass
    return ":".join(result)


def check_host_gpu(plz_run, arch_triple):
    """Return True if a physical GPU is available via host Vulkan drivers."""
    output = _run_vulkaninfo(plz_run, arch_triple)
    if output is None:
        return False
    return any(
        t in output
        for t in (
            "PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU",
            "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU",
            "PHYSICAL_DEVICE_TYPE_VIRTUAL_GPU",
        )
    )
