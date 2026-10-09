#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.

"""OpenGL eglinfo helper for CE OEM graphics jobs.

Subcommands:
  resource  Emit EGL platform records (gbm, wayland, x11, surfaceless) for
            Checkbox resource jobs. Reads the EGLINFO_IGNORED_PLATFORM
            environment variable (a comma-separated list of platform
            names, e.g. "x11,surfaceless") to mark platforms that should
            be skipped. Platform support is not auto-detected; every
            platform in PLATFORMS is emitted unless explicitly ignored. If
            eglinfo has no -p option, a single "all" record is emitted.
  test      Validate a single EGL platform using 'eglinfo -B -p <platform>'
            (plain 'eglinfo' for platform "all").

The eglinfo executable is taken from CUSTOM_EGLINFO_COMMAND_PATH (default:
'eglinfo'), e.g. the 'eglinfo' app of an OpenGL test snap.
"""

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys

# Platforms this suite cares about, in a stable, deterministic order.
# Android (and any other eglinfo-supported platform) is intentionally
# excluded from resource generation.
PLATFORMS = ("gbm", "wayland", "x11", "surfaceless")

# Comma-separated list of platform names (e.g. "x11,surfaceless") that
# should be marked ignored in the resource output.
EGLINFO_IGNORED_PLATFORM = "EGLINFO_IGNORED_PLATFORM"

# Software renderer keywords that indicate the GPU is not actually being
# used, e.g. Mesa's llvmpipe/softpipe or Gallium's swrast.
SOFTWARE_RENDERERS = ("llvmpipe", "softpipe", "swrast")

logger = logging.getLogger(__name__)


def parse_ignored_set() -> "set[str]":
    """Read ignored platform names from the EGLINFO_IGNORED_PLATFORM
    environment variable, a comma-separated list, e.g. "x11,surfaceless".
    """
    raw_value = os.environ.get(EGLINFO_IGNORED_PLATFORM, "")
    logger.debug(f"{EGLINFO_IGNORED_PLATFORM}={raw_value!r}")

    return {
        platform_name.strip().lower()
        for platform_name in raw_value.split(",")
        if platform_name.strip()
    }


def get_mesa_utils_version() -> str:
    """Return the installed mesa-utils deb version, or "unknown"."""
    try:
        output = subprocess.check_output(
            ["dpkg-query", "-W", "-f=${Version}", "mesa-utils"],
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return output.strip() or "unknown"


def is_snap_eglinfo(executable: str) -> bool:
    """Return whether the eglinfo executable comes from a snap."""
    path = os.path.realpath(shutil.which(executable) or executable)
    return path.startswith(("/snap/", "/var/lib/snapd/snap/"))


def log_eglinfo_origin() -> None:
    """Log where eglinfo comes from; for a host eglinfo also log the
    mesa-utils version. Used when platform selection is unavailable.
    """
    executable = get_eglinfo_executable()
    if is_snap_eglinfo(executable):
        logger.info(f"eglinfo source: snap ({executable})")
        return
    logger.info(f"eglinfo source: host ({executable})")
    logger.info(f"mesa-utils version: {get_mesa_utils_version()}")


def get_eglinfo_executable() -> str:
    return os.environ.get("CUSTOM_EGLINFO_COMMAND_PATH") or "eglinfo"


def eglinfo_supports_platform_option() -> bool:
    """Return whether 'eglinfo -h' advertises the -p option.

    Old eglinfo (mesa-utils 8.4.0) lacks it. If eglinfo cannot be probed,
    assume it is supported so the normal flow reports the real failure.
    """
    try:
        output = subprocess.run(
            [get_eglinfo_executable(), "-h"],
            env=eglinfo_environ(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            errors="replace",
        ).stdout
    except OSError:
        return True
    return re.search(r"-p\b", output) is not None


def cmd_resource() -> int:
    """Emit one resource record per platform in PLATFORMS, marking
    platforms listed in EGLINFO_IGNORED_PLATFORM with ignore: true.

    An eglinfo without the -p option (e.g. mesa-utils 8.4.0 on Ubuntu
    22.04) cannot select a platform, so a single "all" record is emitted
    instead.
    """
    if not eglinfo_supports_platform_option():
        print("platform_name: all")
        print("ignore: false")
        print("")
        return 0

    ignored_platforms = parse_ignored_set()

    for platform_name in PLATFORMS:
        is_ignored = platform_name in ignored_platforms
        print(f"platform_name: {platform_name}")
        print(f"ignore: {str(is_ignored).lower()}")
        print("")

    return 0


def eglinfo_environ() -> "dict[str, str]":
    """Return the environment to run eglinfo with.

    The LD_LIBRARY_PATH inherited from a Checkbox snap points at the
    Checkbox runtime, which ships its own libEGL/Mesa: a host eglinfo
    would load them and fall back to llvmpipe. Checkbox also refuses to
    override an existing LD_LIBRARY_PATH from the launcher, so it is
    replaced here by EGLINFO_LD_LIBRARY_PATH (or dropped when unset).
    """
    env = dict(os.environ)
    env.pop("LD_LIBRARY_PATH", None)
    ld_library_path = os.environ.get("EGLINFO_LD_LIBRARY_PATH")
    if ld_library_path:
        env["LD_LIBRARY_PATH"] = ld_library_path
    return env


def run_eglinfo(platform_name: str) -> str:
    """Run 'eglinfo -B -p <platform_name>' and return its combined output.

    For platform "all" plain 'eglinfo' is run, without -B/-p.

    Raises SystemExit if the command is missing, exits non-zero (e.g.
    'eglInitialize failed') or is killed by a signal; the output is logged.
    """
    executable = get_eglinfo_executable()
    command = [executable]
    if platform_name == "all":
        logger.warning("eglinfo has no -p option, running without it")
        log_eglinfo_origin()
    else:
        command += ["-B", "-p", platform_name]
    env = eglinfo_environ()
    logger.info(f"Running command: {command} ({shutil.which(executable)})")
    logger.info(f"LD_LIBRARY_PATH={env.get('LD_LIBRARY_PATH', '')}")
    try:
        return subprocess.check_output(
            command,
            env=env,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            errors="replace",
        )
    except FileNotFoundError as err:
        raise SystemExit(f"eglinfo command not found: {err}")
    except subprocess.CalledProcessError as err:
        logger.error(f"eglinfo output:\n{err.output}")
        raise SystemExit(
            f"FAIL: {command} exited with returncode {err.returncode}"
        )


def cmd_test(platform_name: str) -> int:
    """Validate a single EGL platform using 'eglinfo -B -p <platform_name>'.

    Fails when eglinfo exits non-zero, reports no renderer (e.g. the
    platform is unsupported and nothing is printed), or reports a software
    renderer (llvmpipe, softpipe, swrast).

    For platform "all" (eglinfo without -p, which prints no renderer line)
    the whole output is scanned instead: the missing renderer is not an
    error, but 'eglInitialize failed' and software renderer keywords are.
    """
    output = run_eglinfo(platform_name)
    logger.info(f"eglinfo output:\n{output.rstrip()}")

    if platform_name == "all":
        if "eglInitialize failed" in output:
            raise SystemExit("FAIL: eglInitialize failed")
        lines = [output]
    else:
        lines = [
            line.strip() for line in output.splitlines() if "renderer:" in line
        ]
        if not lines:
            raise SystemExit(
                f"FAIL: no renderer reported for platform '{platform_name}'"
            )

    found = [
        keyword
        for keyword in SOFTWARE_RENDERERS
        if any(keyword in line.lower() for line in lines)
    ]
    if found:
        raise SystemExit(
            f"FAIL: software renderer detected for platform "
            f"'{platform_name}': {', '.join(found)}"
        )

    logger.info(
        f"PASS: eglinfo validation passed for platform '{platform_name}'"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)

    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--debug",
        action="store_true",
        help="enable debug logging",
    )

    subparsers.add_parser("resource", parents=[common_parser])

    test_parser = subparsers.add_parser("test", parents=[common_parser])
    test_parser.add_argument(
        "-p",
        "--platform",
        required=True,
        help="EGL platform name, e.g. gbm, wayland, x11, surfaceless",
    )

    return parser


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="{levelname:<8} - {module:<10}: {funcName} "
        "{lineno:<4} - {message}",
        style="{",
    )

    args = build_parser().parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.action == "resource":
        return cmd_resource()
    return cmd_test(args.platform)


if __name__ == "__main__":
    sys.exit(main())
