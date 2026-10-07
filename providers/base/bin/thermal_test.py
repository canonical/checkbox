#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Checkbox Contributors
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

"""Intel thermal management certification checks.

This module gathers the thermal-related checks that validate the Intel
thermal stack (thermald, RAPL, P-State, powerclamp, thermal zones and
platform thermal policy).  Each check is exposed as an ``argparse``
sub-command so it can be invoked individually from a Checkbox job.
"""

import argparse
import glob
import os
import subprocess
import sys

KERNEL_POWERCAP = (
    "https://www.kernel.org/doc/html/latest/power/powercap/powercap.html"
)
THERMAL_DAEMON_README = (
    "https://github.com/intel/thermal_daemon/blob/master/README.txt"
)

# Thermal zone types that identify an Intel CPU thermal zone created by the
# int340x thermal driver from BIOS defined devices.
CPU_THERMAL_ZONE_TYPES = ("B0D4", "B0DB", "TCPU")

# Equivalent thermal zone types exposing the CPU package temperature sensor.
# thermald accepts any of these interchangeably.
PKG_TEMP_ZONE_TYPES = ("x86_pkg_temp", "pkg-temp-0", "soc_dts0")

# Journal messages emitted when the running thermald cannot manage the
# platform because the CPU is absent from its built-in id_table. The adaptive
# engine (Ubuntu default) logs "... or platform" and exits; the default engine
# logs "... use thermal-conf.xml file ...". Benign degraded-but-working cases
# ("using thermal-conf.xml only", "using Linux PowerCap sysfs") are excluded.
UNSUPPORTED_CPU_PATTERN = (
    r"Unsupported cpu model( or platform|, use thermal-conf\.xml file)"
)

# Thermal zone types that legitimately have no trip points and should be
# skipped when validating trip points.
TRIP_POINT_SKIP_PREFIXES = (
    "iwlwifi",
    "INT3400 Thermal",
    "x86_pkg_temp",
    "TCPU_PCI",
)


def _read(path):
    """Return the stripped content of ``path`` or None if unreadable."""
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _glob_read(pattern):
    """Yield (path, content) for every readable file matching ``pattern``."""
    for path in sorted(glob.glob(pattern)):
        content = _read(path)
        if content is not None:
            yield path, content


def check_rapl(args):
    """Check that the Intel RAPL power capping driver is present."""
    if os.path.isdir("/sys/class/powercap/intel-rapl"):
        print("Intel RAPL power capping driver is present")
        return
    print("Is CONFIG_INTEL_RAPL configured?")
    print("List node under /sys/class/powercap:")
    for entry in sorted(glob.glob("/sys/class/powercap/*")):
        print("  {}".format(entry))
    print("The info of powercap driver: {}".format(KERNEL_POWERCAP))
    print("The info of Intel thermal_daemon: {}".format(THERMAL_DAEMON_README))
    raise SystemExit("Intel RAPL power capping driver is not installed")


def check_rapl_mmio(args):
    """Check that the Intel RAPL-mmio power capping driver is present."""
    if os.path.isdir("/sys/class/powercap/intel-rapl-mmio"):
        print("Intel RAPL-mmio power capping driver is present")
        return
    print(
        "Lack of MMIO interface for power capping. "
        "It depends on proc_thermal, please check if processor thermal "
        "device exists and proc_thermal driver has probed properly."
    )
    print("The info of powercap driver: {}".format(KERNEL_POWERCAP))
    print("The info of Intel thermal_daemon: {}".format(THERMAL_DAEMON_README))
    raise SystemExit("Intel RAPL-mmio power capping driver is not installed")


def check_pstate(args):
    """Check that the Intel P-State driver is present."""
    if os.path.isdir("/sys/devices/system/cpu/intel_pstate"):
        print("Intel P-State driver is present")
        return
    print("Is CONFIG_X86_INTEL_PSTATE configured?")
    print("List node under /sys/devices/system/cpu:")
    for entry in sorted(glob.glob("/sys/devices/system/cpu/*")):
        print("  {}".format(entry))
    print("The intel_pstate driver is required by thermald.")
    print("The info of Intel thermal_daemon: {}".format(THERMAL_DAEMON_README))
    print(
        "The info of Intel pstate driver: https://www.kernel.org/doc/html/"
        "latest/admin-guide/pm/intel_pstate.html"
    )
    raise SystemExit("Intel P-State driver is not installed")


def check_powerclamp(args):
    """Check whether the Intel powerclamp cooling device is registered.

    thermald treats intel_powerclamp as optional: it null-checks the cooling
    device and falls back to RAPL when it is absent (do_default_binding() in
    src/thd_cpu_default_binding.cpp). This check is therefore advisory -- it
    reports the state but does not fail when powerclamp is missing.
    """
    for _, content in _glob_read("/sys/class/thermal/cooling_device*/type"):
        if "intel_powerclamp" in content:
            print("Intel powerclamp cooling device is registered")
            return
    print(
        "Intel powerclamp cooling device is not registered (advisory). "
        "thermald treats it as optional and falls back to RAPL. Is "
        "CONFIG_INTEL_POWERCLAMP configured? Registered cooling devices:"
    )
    for path, content in _glob_read("/sys/class/thermal/cooling_device*/type"):
        print("  {}: {}".format(path, content))
    print(
        "The info of Intel powerclamp driver: https://www.kernel.org/doc/"
        "Documentation/thermal/intel_powerclamp.txt"
    )


def check_cpu_thermal(args):
    """Check that an Intel CPU thermal zone is registered.

    thermald checks whether /sys/class/thermal/thermal_zone* contains a zone
    of type B0D4, B0DB or TCPU (BIOS defined devices enumerated by the
    int340x thermal driver).  When those devices are absent thermald falls
    back to the coretemp hwmon device to create a CPU thermal zone.
    """
    for _, content in _glob_read("/sys/class/thermal/thermal_zone*/type"):
        if any(t in content for t in CPU_THERMAL_ZONE_TYPES):
            print("Intel CPU thermal zone is registered ({})".format(content))
            return
    for _, content in _glob_read("/sys/class/hwmon/hwmon*/name"):
        if "coretemp" in content:
            print("CPU thermal zone available via coretemp hwmon")
            return
    print("No valid sysfs node to create cpu thermal zone")
    print("Nodes in thermal class:")
    for path, content in _glob_read("/sys/class/thermal/thermal_zone*/type"):
        print("  {}: {}".format(path, content))
    print("Nodes in hwmon class:")
    for path, content in _glob_read("/sys/class/hwmon/hwmon*/name"):
        print("  {}: {}".format(path, content))
    raise SystemExit("Intel CPU thermal zone is not registered")


def check_x86_pkg_temp(args):
    """Check that a CPU package temperature thermal zone is present.

    thermald looks for the package temperature sensor under several
    equivalent zone names (x86_pkg_temp, pkg-temp-0, soc_dts0); any of them
    provides the same CPU package temperature reading (see DEVELOPER.md and
    src/thd_engine_default.cpp), so all are accepted here.
    """
    for _, content in _glob_read("/sys/class/thermal/thermal_zone*/type"):
        if any(name in content for name in PKG_TEMP_ZONE_TYPES):
            print(
                "Package temperature thermal zone is present ({})".format(
                    content
                )
            )
            return
    print("The system has no package temperature thermal zone.")
    print("Accepted zone types: {}".format(", ".join(PKG_TEMP_ZONE_TYPES)))
    print(
        "The info of Intel x86_pkg_temp thermal zone: https://www.kernel.org/"
        "doc/html/latest/driver-api/thermal/x86_pkg_temperature_thermal.html"
    )
    raise SystemExit("Package temperature thermal zone is not present")


def _zone_has_valid_trip_point(zone):
    """Return True if ``zone`` has at least one positive trip point."""
    for _, content in _glob_read(os.path.join(zone, "trip_point_*_temp")):
        try:
            if int(content) > 0:
                return True
        except ValueError:
            continue
    return False


def check_trip_points(args):
    """Check that every relevant thermal zone has a valid trip point."""
    failed = False
    for zone in sorted(glob.glob("/sys/class/thermal/thermal_zone*")):
        tp_type = _read(os.path.join(zone, "type")) or ""
        if any(tp_type.startswith(p) for p in TRIP_POINT_SKIP_PREFIXES):
            continue
        if not _zone_has_valid_trip_point(zone):
            print("{} contains no valid trip point".format(tp_type))
            for path, content in _glob_read(
                os.path.join(zone, "trip_point_*_temp")
            ):
                print("  {}: {}".format(path, content))
            print("Please consult ODM to see if it is expected.")
            failed = True
    if failed:
        print(
            "For more detail, please refer to https://www.kernel.org/doc/"
            "html/latest/driver-api/thermal/sysfs-api.html"
        )
        raise SystemExit("One or more thermal zones lack a valid trip point")
    print("All relevant thermal zones contain a valid trip point")


def check_proc_thermal(args):
    """Check that the processor thermal PCI driver has probed."""
    driver = "/sys{}/driver".format(args.path)
    if os.path.exists(driver):
        print("Processor thermal driver is loaded ({})".format(driver))
        return
    print(
        "There is no processor thermal driver probed. "
        "Dynamic Tuning Technology (DTT) - this PCI device (Bus 0 Device 4) "
        "contains the configuration registers for the DPPM device. "
        "More detail is in Intel Document ID:640686, Processor EDS."
    )
    raise SystemExit("Processor thermal driver is not loaded")


def _thinkpad_lapmode():
    """Return True for Lenovo machines with in-firmware thermal management."""
    return os.path.exists("/sys/devices/platform/thinkpad_acpi/dytc_lapmode")


def check_thermald(args):
    """Check that the thermald service is active."""
    if _thinkpad_lapmode():
        print("Some Lenovo machines have in-firmware thermal management")
        return
    result = subprocess.run(["systemctl", "is-active", "--quiet", "thermald"])
    if result.returncode == 0:
        print("thermald is active")
        return
    print("FAIL: thermald is not active")
    print("===")
    print("# journalctl -b -u thermald")
    subprocess.run(["journalctl", "-b", "-u", "thermald", "--no-pager"])
    print("===")
    print("Debugging Tips:")
    print(
        "Please check the upstream code (https://github.com/intel/"
        "thermal_daemon/blob/master/src/thd_engine.cpp) for the target id "
        "in id_table[]."
    )
    print(
        "If the ID is not there, open an upstream bug like "
        "https://github.com/intel/thermal_daemon/issues/275"
    )
    print(
        "If the CPU is not supported by thermald, add model information from "
        "lscpu to the test job blacklist."
    )
    raise SystemExit("thermald is not active")


def check_cpu_support(args):
    """Check the running thermald recognises this CPU and platform.

    thermald matches the CPU against its built-in id_table (intel_id_table[]
    in src/thd_platform_intel.cpp). When the CPU is not listed, the daemon
    cannot manage the platform: the adaptive engine logs "Unsupported cpu
    model or platform" and exits, and the default engine logs "Unsupported
    cpu model, use thermal-conf.xml file ..." and fails to initialise.

    This journal-based check reflects the behaviour of the actually installed
    daemon, so it stays accurate even when Ubuntu backports CPU enablement
    into an older thermald version via the SRU process -- unlike comparing the
    reported version against upstream.
    """
    result = subprocess.run(
        [
            "journalctl",
            "-b",
            "0",
            "-u",
            "thermald",
            "-g",
            UNSUPPORTED_CPU_PATTERN,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        universal_newlines=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        print("The running thermald recognises this CPU and platform")
        return
    print("The running thermald does not support this CPU/platform:")
    print(result.stdout.strip())
    print("")
    print(
        "The installed thermald has no matching entry in its id_table, so "
        "it cannot provide thermal management for this platform. Check the "
        "upstream id_table (https://github.com/intel/thermal_daemon/blob/ "
        "master/src/thd_platform_intel.cpp) for the CPU family:model, and "
        "request an SRU backport of the CPU enablement into the Ubuntu "
        "thermald package if it is supported upstream but missing here."
    )
    raise SystemExit("thermald does not support this CPU/platform")


def check_thermal_policy(args):
    """Check that a thermal policy is applied for a platform device."""
    uuid_path = "/sys{}/uuids/current_uuid".format(args.path)
    if not os.path.exists(uuid_path):
        print("No current_uuid node at {}, nothing to check".format(uuid_path))
        return
    policy = _read(uuid_path)
    if policy != "INVALID":
        print("Thermal policy is set: {}".format(policy))
        return
    print("Check {} got INVALID.".format(uuid_path))
    print(
        "INVALID means the thermal policy is not set. "
        "The possible causes: "
        "a. thermald can't support the adaptive table in BIOS "
        "b. BIOS didn't configure any adaptive table "
        "c. The BIOS only supports the default passive table "
        "d. The platform doesn't require the OS to do thermal management "
        "Please consult the ODM/OEM to confirm the expected policy. See: "
        "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/ "
        "tree/drivers/thermal/intel/int340x_thermal/int3400_thermal.c"
    )
    raise SystemExit("Thermal policy is not set (INVALID)")


def check_unknown_cond(args):
    """Check thermald journal for out-of-bound GDDV condition values."""
    # Older thermald releases emit the misspelled "UKNKNOWN"; current
    # releases emit "UNKNOWN". Match both so the check stays valid.
    pattern = r"Unsupported condition [0-9]+ \(UK?NKNOWN\)"
    result = subprocess.run(
        ["journalctl", "-b", "0", "-u", "thermald", "-g", pattern],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        print("No out-of-bound condition values found in thermald journal")
        return
    print("This error occurs because OOB values appear when parsing the GDDV")
    print("")
    print(
        "Thermald constructs conditions by parsing the GDDV blob from "
        "/sys/devices/platform/INT*/data_vault and checks if the parsed "
        "values make sense. If the type of adaptive_condition appears to be "
        "an out-of-bound value, the following error shows up in journal:"
    )
    print("")
    print("\tUnsupported condition %d (UKNKNOWN)")
    print("")
    print("This test job catches those erroneously parsed enum values.")
    print("")
    print(
        "See the following part of thermald source code for detail: "
        "  1. cthd_gddv::verify_condition in src/thd_engine_adaptive.cpp "
        "  2. enum adaptive_condition and struct condition in src/thd_gddv.h"
    )
    raise SystemExit("Out-of-bound condition values found in thermald journal")


# Runtime directory used by thermald for its sentinel/state files. Modern
# systems symlink /var/run to /run; check both to be safe.
THERMALD_RUN_DIRS = ("/run/thermald", "/var/run/thermald")


def check_adaptive_fallback(args):
    """Check that thermald did not silently fall back from adaptive mode.

    When adaptive mode installs a table that produces zero active thermal
    zones, thermald creates an ``ignore_adaptive`` sentinel file in its
    runtime directory, exits with failure and is restarted by systemd into
    the non-adaptive default engine.  The presence of that sentinel means the
    DPTF/GDDV adaptive tables failed to produce usable zones, so the platform
    is running with degraded thermal management.
    """
    found = [
        os.path.join(d, "ignore_adaptive")
        for d in THERMALD_RUN_DIRS
        if os.path.exists(os.path.join(d, "ignore_adaptive"))
    ]
    if not found:
        print("thermald is running with adaptive mode enabled")
        return
    print("Found thermald ignore_adaptive sentinel: {}".format(found[0]))
    print(
        "thermald installed an adaptive table that produced zero active "
        "zones and fell back to the non-adaptive default engine. "
        "The possible causes are the same as an INVALID thermal policy: "
        "the BIOS adaptive/DPTF table is missing or cannot be supported. "
        "Please consult the ODM/OEM to confirm the expected DPTF tables. "
        "See https://github.com/intel/thermal_daemon/blob/master/DEVELOPER.md"
    )
    raise SystemExit("thermald fell back from adaptive mode")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    subparsers.add_parser(
        "rapl", help="Check Intel RAPL power capping driver"
    ).set_defaults(func=check_rapl)
    subparsers.add_parser(
        "rapl-mmio", help="Check Intel RAPL-mmio power capping driver"
    ).set_defaults(func=check_rapl_mmio)
    subparsers.add_parser(
        "pstate", help="Check Intel P-State driver"
    ).set_defaults(func=check_pstate)
    subparsers.add_parser(
        "powerclamp", help="Check Intel powerclamp cooling device"
    ).set_defaults(func=check_powerclamp)
    subparsers.add_parser(
        "cpu-thermal", help="Check Intel CPU thermal zone"
    ).set_defaults(func=check_cpu_thermal)
    subparsers.add_parser(
        "x86-pkg-temp", help="Check x86_pkg_temp thermal zone"
    ).set_defaults(func=check_x86_pkg_temp)
    subparsers.add_parser(
        "trip-points", help="Check thermal zone trip points"
    ).set_defaults(func=check_trip_points)
    subparsers.add_parser(
        "thermald", help="Check thermald service is active"
    ).set_defaults(func=check_thermald)
    subparsers.add_parser(
        "cpu-support",
        help="Check running thermald supports this CPU/platform",
    ).set_defaults(func=check_cpu_support)
    subparsers.add_parser(
        "unknown-cond", help="Check thermald GDDV parse errors"
    ).set_defaults(func=check_unknown_cond)
    subparsers.add_parser(
        "adaptive-fallback",
        help="Check thermald did not fall back from adaptive mode",
    ).set_defaults(func=check_adaptive_fallback)

    proc = subparsers.add_parser(
        "proc-thermal", help="Check processor thermal PCI driver"
    )
    proc.add_argument("path", help="sysfs device path (without /sys prefix)")
    proc.set_defaults(func=check_proc_thermal)

    policy = subparsers.add_parser(
        "thermal-policy", help="Check platform thermal policy is set"
    )
    policy.add_argument("path", help="sysfs device path (without /sys prefix)")
    policy.set_defaults(func=check_thermal_policy)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
