#!/usr/bin/env python3

import argparse
import re
import subprocess
import sys

print("Beginning Platform Metapackage Test", file=sys.stderr)


def _run(*cmd):
    """Run a command and return its stdout as a string (stderr suppressed)."""
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ).stdout


def _dpkg_query_status(package):
    """Return the dpkg Status string for *package* (empty string on error)."""
    return subprocess.run(
        ["dpkg-query", "-W", "-f=${Status}\n", package],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout


def _apt_cache_modaliases(package):
    """Return the Modaliases line from apt-cache show output, or ''."""
    output = _run("apt-cache", "show", package)
    for line in output.splitlines():
        if line.startswith("Modaliases"):
            return line
    return ""


def _is_installed(package):
    return "install ok installed" in _dpkg_query_status(package)


# ---------------------------------------------------------------------------
# DMI / OS helpers
# ---------------------------------------------------------------------------


def _read_dmi(field):
    with open(f"/sys/devices/virtual/dmi/id/{field}") as f:
        return f.read().strip()


def _ubuntu_codename():
    return subprocess.run(
        ["lsb_release", "-cs"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ).stdout.strip()


def _ubuntu_drivers_list():
    """Return the list of OEM meta packages from ubuntu-drivers."""
    output = _run("ubuntu-drivers", "list")
    return [
        pkg
        for pkg in output.splitlines()
        if pkg.startswith("oem") and pkg.endswith("meta")
    ]


# ---------------------------------------------------------------------------
# OEM meta check
# ---------------------------------------------------------------------------

_OEM_CONFIGS = {
    "somerville": {
        "dmi_field": "product_sku",
        "biosid_fn": lambda raw: raw,
        "pattern_fn": lambda biosid: rf"sv00001028sd0000{re.escape(biosid)}",
        "factory_prefix": "oem-somerville",
    },
    "stella": {
        "dmi_field": "board_name",
        "biosid_fn": lambda raw: raw,
        "pattern_fn": lambda biosid: rf"sv0000103csd0000{re.escape(biosid)}",
        "factory_prefix": "oem-stella",
    },
    "sutton": {
        "dmi_field": "bios_version",
        "biosid_fn": lambda raw: raw[:3],
        "pattern_fn": lambda biosid: rf"bvr{re.escape(biosid)}",
        "factory_prefix": "oem-sutton",
    },
}


def check_oem_meta(oem):
    cfg = _OEM_CONFIGS[oem]
    raw = _read_dmi(cfg["dmi_field"])
    biosid = cfg["biosid_fn"](raw)
    codename = _ubuntu_codename()

    if codename in ("jammy", "noble"):
        for meta in _ubuntu_drivers_list():
            modaliases = _apt_cache_modaliases(meta)
            if not re.search(
                cfg["pattern_fn"](biosid), modaliases, re.IGNORECASE
            ):
                continue
            if not _is_installed(meta):
                continue
            factory = meta.replace(
                cfg["factory_prefix"], cfg["factory_prefix"] + "-factory", 1
            )
            if not _is_installed(factory):
                print(
                    f"Factory meta package '{factory}' is not installed!!!",
                    file=sys.stderr,
                )
                continue
            print(
                f"Found the platform meta package '{meta}' containing "
                f"BIOS ID '{biosid}' and the platform factory meta "
                f"package '{factory}'"
            )
            sys.exit(0)
        print(f"BIOS ID: {biosid}", file=sys.stderr)
        print("Meta package not installed", file=sys.stderr)
        sys.exit(1)

    print(f"{codename} is not supported yet.", file=sys.stderr)
    print(f"{sys.argv[0]} failed!", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        description="Platform metapackage sanity test",
        add_help=True,
    )
    parser.add_argument(
        "--oem-codename",
        choices=_OEM_CONFIGS.keys(),
        required=True,
        metavar="CODENAME",
        help="OEM codename: %(choices)s",
    )
    args = parser.parse_args()

    check_oem_meta(args.oem_codename)


if __name__ == "__main__":
    main()
