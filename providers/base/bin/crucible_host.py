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

"""
Host crucible helper for Checkbox.

Subcommands:
  resource          Check whether a GPU is available via host Vulkan drivers
                    (used by depends: graphics/crucible_classic_gpu_avail).
  validate-install  Check whether the host Vulkan ICD loader is installed
                    (used by depends: graphics/crucible_classic_vk_avail).
  run-test ARGS...  Run a crucible test using host Vulkan libraries,
                    forwarding all remaining arguments to crucible run.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import sysconfig


def get_arch_triple():
    """Return the Debian multiarch triple for the current architecture."""
    triple = sysconfig.get_config_var("MULTIARCH")
    if triple is None:
        raise RuntimeError("could not determine multiarch triple")
    return triple


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
    "0x8086": ("intel",),        # Intel
    "0x1002": ("radeon", "amd"), # AMD / Radeon
    "0x10de": ("nvidia",),       # NVIDIA
}


def prime_selected_vendor():
    """Return the GPU vendor chosen by prime-select, or None.

    Returns one of the keys in _PRIME_VENDOR_ICD_PREFIXES, or None if
    prime-select is not installed, returns an unrecognised value (e.g.
    'on-demand'), or fails for any reason.
    """
    try:
        output = subprocess.check_output(
            ["/usr/bin/prime-select", "query"],
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
        ).strip().lower()
        return output if output in _PRIME_VENDOR_ICD_PREFIXES else None
    except (FileNotFoundError, OSError, subprocess.CalledProcessError):
        return None


def find_plz_run():
    """Return the path to plz-run from PATH."""
    return shutil.which("plz-run")


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
                "-u", "root",
                "-g", "root",
                "-E", "LD_LIBRARY_PATH={}".format(ld_library_path),
                "--", "/usr/bin/vulkaninfo", "--summary",
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
        if "0x8086" in stripped:
            return ("intel",)
        if "0x1002" in stripped:
            return ("radeon", "amd")
        if "0x10de" in stripped:
            return ("nvidia",)
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
    output = _run_vulkaninfo(plz_run, arch_triple) if plz_run is not None else None
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


def cmd_resource():
    arch_triple = get_arch_triple()

    plz_run = find_plz_run()
    if plz_run is None:
        logging.error("plz-run not found in PATH")
        return 1

    if check_host_gpu(plz_run, arch_triple):
        logging.info("Found a Vulkan-capable GPU using host drivers")
        return 0

    logging.error("No GPU device found in vulkaninfo output using host drivers")
    return 1


def cmd_validate_install():
    arch_triple = get_arch_triple()
    host_vk = "/usr/lib/{}/libvulkan.so.1".format(arch_triple)
    if os.path.isfile(host_vk):
        logging.info("Host Vulkan ICD loader found at %s", host_vk)
        return 0
    logging.error("Host Vulkan ICD loader not found at %s", host_vk)
    logging.error(
        "Install libvulkan1 or equivalent before running host crucible tests"
    )
    return 1


def cmd_run_test(test_args):
    snap = "/snap/crucible/current"
    # NODEVICE_SELECT disables VK_LAYER_MESA_device_select, which is an
    # implicit host layer that fails to load under the snap's core24 glibc
    # (requires GLIBC_ABI_GNU2_TLS, which core24 does not provide).
    env = dict(os.environ, SNAP=snap, NODEVICE_SELECT="1")
    if not env.get("VK_ICD_FILENAMES"):
        icd_filenames = find_host_icd_filenames(_active_vendor_prefixes())
        if icd_filenames:
            env["VK_ICD_FILENAMES"] = icd_filenames
    result = subprocess.run(
        ["{}/test".format(snap), "--no-confinement", "--no-fork"] + test_args,
        env=env,
    )
    return result.returncode


def main():
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
    if len(sys.argv) < 2:
        logging.error(
            "Usage: crucible_host.py"
            " {resource,validate-install,run-test} [args...]"
        )
        return 1
    command = sys.argv[1]
    try:
        if command == "resource":
            return cmd_resource()
        elif command == "validate-install":
            return cmd_validate_install()
        elif command == "run-test":
            return cmd_run_test(sys.argv[2:])
        else:
            logging.error("Unknown command: %s", command)
            return 1
    except RuntimeError as exc:
        logging.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
