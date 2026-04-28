# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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

import os
import shutil
import subprocess
import sysconfig


class VulkanDetectionError(Exception):
    """Raised when a GPU/Vulkan detection step fails."""


def get_arch_triple():
    """Return the Debian multiarch triple for the current architecture."""
    triple = sysconfig.get_config_var("MULTIARCH")
    if triple is None:
        raise RuntimeError("could not determine multiarch triple")
    return triple


def find_plz_run():
    """Return the path to plz-run from PATH.

    Raises VulkanDetectionError if plz-run is not found.
    """
    path = shutil.which("plz-run")
    if path is None:
        raise VulkanDetectionError("plz-run not found in PATH")
    return path


_VIRTUAL_ICD_PREFIXES = {"gfxstream", "virtio"}

# Maps prime-select vendor name to ICD filename prefixes.
# Used to filter the ICD list to the PRIME-selected GPU on multi-GPU systems.
_PRIME_VENDOR_ICD_PREFIXES = {
    "intel": ("intel",),
    "nvidia": ("nvidia",),
    "amd": ("radeon", "amd"),
}

# Maps PCI vendor ID to ICD filename prefixes.
_PCI_VENDOR_ICD_PREFIXES = {
    "0x8086": ("intel",),
    "0x1002": ("radeon", "amd"),
    "0x10de": ("nvidia",),
}


def prime_selected_vendor():
    """Return the GPU vendor chosen by prime-select.

    Returns one of the keys in _PRIME_VENDOR_ICD_PREFIXES.
    Raises VulkanDetectionError if prime-select is not installed, fails,
    or returns an unrecognised value (e.g. 'on-demand').
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
    except (OSError, subprocess.CalledProcessError) as e:
        raise VulkanDetectionError("prime-select query failed") from e
    if output not in _PRIME_VENDOR_ICD_PREFIXES:
        raise VulkanDetectionError(
            "prime-select returned unrecognised value: {!r}".format(output)
        )
    return output


def _run_vulkaninfo(plz_run, arch_triple):
    """Run vulkaninfo --summary via plz-run with host libraries.

    vulkaninfo is executed inside a new mount/user namespace (via plz-run)
    so that it uses the host ICD stack instead of snap-bundled libraries.
    Raises VulkanDetectionError if vulkaninfo fails.
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
    except subprocess.CalledProcessError as e:
        raise VulkanDetectionError("vulkaninfo failed") from e


def _vendor_prefixes_from_vulkaninfo(output):
    """Return ICD filename prefixes for the first recognised GPU vendor in
    vulkaninfo --summary output.

    Matches on the vendorID field which is unambiguous across driver versions
    and device names.  The field is right-padded with spaces for alignment,
    so each line is stripped before matching.
    Raises VulkanDetectionError if no known vendor is found.
    """
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith("vendorID"):
            continue
        for vid, prefixes in _PCI_VENDOR_ICD_PREFIXES.items():
            if vid in stripped:
                return prefixes
    raise VulkanDetectionError("no known GPU vendor found in vulkaninfo output")


def active_vendor_prefixes():
    """Return ICD filename prefixes for the active GPU.

    Tries prime-select first (authoritative on PRIME multi-GPU systems),
    then falls back to vulkaninfo via plz-run.
    Raises VulkanDetectionError if no method identifies the vendor.
    """
    # prime-select is only present on NVIDIA hybrid systems; absence or
    # unrecognised output (e.g. on-demand) is normal — fall through to vulkaninfo.
    try:
        vendor = prime_selected_vendor()
        return _PRIME_VENDOR_ICD_PREFIXES[vendor]
    except VulkanDetectionError:
        pass

    plz_run = find_plz_run()
    arch_triple = get_arch_triple()
    output = _run_vulkaninfo(plz_run, arch_triple)
    return _vendor_prefixes_from_vulkaninfo(output)


def find_host_icd_filenames(vendor_prefixes=None):
    """Return a colon-separated list of Vulkan ICD files for the active GPU.

    Virtual ICDs (gfxstream, virtio) are always excluded — they hang on bare
    metal waiting for a virtual device that does not exist.

    When vendor_prefixes is provided, only ICDs whose filenames begin with
    one of the given prefixes are included.  Pass None to include all
    non-virtual ICDs (the Vulkan loader then selects the default device).
    """
    icd_dir = "/usr/share/vulkan/icd.d"
    try:
        entries = sorted(os.listdir(icd_dir))
    except OSError as e:
        raise VulkanDetectionError(
            "cannot read Vulkan ICD directory {}".format(icd_dir)
        ) from e
    result = []
    for name in entries:
        if not name.endswith(".json"):
            continue
        if any(name.startswith(p) for p in _VIRTUAL_ICD_PREFIXES):
            continue
        if vendor_prefixes and not any(
            name.startswith(p) for p in vendor_prefixes
        ):
            continue
        result.append(os.path.join(icd_dir, name))
    return ":".join(result)


def check_host_gpu(plz_run, arch_triple):
    """Return True if a physical GPU is available via host Vulkan drivers."""
    try:
        output = _run_vulkaninfo(plz_run, arch_triple)
    except VulkanDetectionError:
        return False
    return any(
        t in output
        for t in (
            "PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU",
            "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU",
            "PHYSICAL_DEVICE_TYPE_VIRTUAL_GPU",
        )
    )
