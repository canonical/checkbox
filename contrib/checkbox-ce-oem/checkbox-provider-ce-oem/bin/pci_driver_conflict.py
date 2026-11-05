#!/usr/bin/env python3
"""
Find PCI devices that a second loaded kernel module also matches.

The kernel loads every module whose alias matches a device, and the first one
that probes gets it. A module that probes first and fails can leave side
effects (a Wi-Fi driver takes the phy0 number before its probe fails). For
each PCI device with a driver, report the other loaded modules that match the
device (modules.alias) and drive no PCI device: usually modules that the image
must block.
"""

import argparse
import fnmatch
import os
import sys
from pathlib import Path

# Drivers that share devices by design: each device goes to one of them and
# the others decline it at probe time (links: kernel v6.8 source).
# i915 and xe decline a device that needs force_probe, or that force_probe
# blocks:
# https://github.com/torvalds/linux/blob/v6.8/drivers/gpu/drm/i915/i915_pci.c#L1016-L1024
# https://github.com/torvalds/linux/blob/v6.8/drivers/gpu/drm/xe/xe_pci.c#L700-L716
# amdgpu declines SI and CIK chips when radeon is built (si_support=0 and
# cik_support=0 by default), and radeon declines them when its own
# si_support or cik_support is 0:
# https://github.com/torvalds/linux/blob/v6.8/drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c#L594-L601
# https://github.com/torvalds/linux/blob/v6.8/drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c#L2198-L2231
# https://github.com/torvalds/linux/blob/v6.8/drivers/gpu/drm/radeon/radeon_drv.c#L270-L293
DRIVER_FAMILIES = ({"i915", "xe"}, {"radeon", "amdgpu"})
# Modules that select one driver for a device at probe time; the drivers that
# use the same selector form a family. snd_intel_dspcfg selects the driver of
# the Intel audio DSP, and snd_hda_intel, SOF and AVS decline the device when
# they are not selected:
# https://github.com/torvalds/linux/blob/v6.8/sound/hda/intel-dsp-config.c#L607-L681
# https://github.com/torvalds/linux/blob/v6.8/sound/pci/hda/hda_intel.c#L2107-L2115
# https://github.com/torvalds/linux/blob/v6.8/sound/soc/sof/intel/hda.c#L1756-L1764
# https://github.com/torvalds/linux/blob/v6.8/sound/soc/intel/avs/core.c#L408-L410
DRIVER_SELECTORS = ("snd_intel_dspcfg",)


def normalize(module):
    return module.replace("-", "_")


def read_pci_aliases(modules_alias):
    """Return (pattern, module) for each "alias pci:..." line."""
    aliases = []
    for line in Path(modules_alias).read_text().splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[0] == "alias":
            if fields[1].startswith("pci:"):
                aliases.append((fields[1], normalize(fields[2])))
    return aliases


def read_loaded_modules(proc_modules):
    lines = Path(proc_modules).read_text().splitlines()
    return {normalize(line.split()[0]) for line in lines if line.strip()}


def drives_pci_device(sys_root, module):
    """Return True if a PCI driver of the module has a device bound."""
    drivers = Path(sys_root, "module", module, "drivers")
    if not drivers.is_dir():
        return False
    for link in drivers.glob("pci:*"):
        if any(":" in entry.name for entry in link.iterdir()):
            return True
    return False


def module_users(sys_root, module):
    """
    Return the modules that use the module, directly or through other
    modules (for example nvidia_drm -> nvidia_modeset -> nvidia).
    """
    users, todo = set(), [module]
    while todo:
        holders = Path(sys_root, "module", todo.pop(), "holders")
        for holder in holders.iterdir() if holders.is_dir() else []:
            if holder.name not in users:
                users.add(holder.name)
                todo.append(holder.name)
    return users


def find_conflicts(sys_root, aliases, loaded, ignore=()):
    """
    Return the number of PCI devices checked, and (device, ids, bound
    module, other module) for each conflict.
    """
    checked, conflicts = 0, []
    families = list(DRIVER_FAMILIES) + [
        module_users(sys_root, s) for s in DRIVER_SELECTORS
    ]
    pci = Path(sys_root, "bus", "pci", "devices")
    for device in sorted(pci.iterdir()) if pci.is_dir() else []:
        module_link = device / "driver" / "module"
        if not module_link.exists():
            # no driver, or a built-in driver: no module to compare
            continue
        checked += 1
        bound = normalize(os.path.basename(os.readlink(module_link)))
        modalias = (device / "modalias").read_text().strip()
        matches = {m for p, m in aliases if fnmatch.fnmatchcase(modalias, p)}
        ids = "{}:{}".format(
            (device / "vendor").read_text().strip()[2:],
            (device / "device").read_text().strip()[2:],
        )
        # a module that uses the bound module is part of its driver stack
        stack = {bound} | module_users(sys_root, bound)
        for family in families:
            if bound in family:
                stack |= family
        for other in sorted(matches - stack - set(ignore)):
            if other in loaded and not drives_pci_device(sys_root, other):
                conflicts.append((device.name, ids, bound, other))
    return checked, conflicts


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.strip().split("\n")[0]
    )
    parser.add_argument(
        "--ignore",
        default="",
        help="modules to skip, separated by spaces or commas",
    )
    parser.add_argument("--sys-root", default="/sys", help=argparse.SUPPRESS)
    parser.add_argument(
        "--modules-alias",
        default="/lib/modules/{}/modules.alias".format(os.uname().release),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--proc-modules", default="/proc/modules", help=argparse.SUPPRESS
    )
    args = parser.parse_args(argv)
    ignore = {normalize(m) for m in args.ignore.replace(",", " ").split()}

    checked, conflicts = find_conflicts(
        args.sys_root,
        read_pci_aliases(args.modules_alias),
        read_loaded_modules(args.proc_modules),
        ignore,
    )
    print("Checked {} PCI devices that have a driver module".format(checked))
    if ignore:
        print("Ignored modules: {}".format(" ".join(sorted(ignore))))
    for device, ids, bound, other in conflicts:
        print(
            "FAIL: {} [{}] is bound to module {}, but module {} also "
            "matches it, is loaded and drives no PCI device".format(
                device, ids, bound, other
            )
        )
    if conflicts:
        print(
            "Block a module that must not drive the device in the image "
            '(for example "blacklist <module>" in /etc/modprobe.d/), or '
            "add a correct one to PCI_DRIVER_CONFLICT_IGNORE."
        )
        return 1
    print("PASS: no second loaded module matches a bound PCI device")
    return 0


if __name__ == "__main__":
    sys.exit(main())
