#!/usr/bin/env python3
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

"""
Host OpenGL helper for Checkbox.

Subcommands:
  resource          Emit a resource record if a GPU is available via host
                    OpenGL drivers (used by depends:
                    graphics/gl_classic_gpu_avail).
  validate-install  Emit a resource record if the host EGL library is
                    installed (used by depends: graphics/gl_classic_gl_avail).
  run-test ARGS...  Run the opengl-cts glcts binary with host EGL/Mesa,
                    forwarding all remaining arguments to the test.
"""

import logging
import os
import subprocess
import sys

from checkbox_support.helpers.host_utils import get_arch_triple


class OpenGLError(Exception):
    pass


# PCI vendor IDs found in /sys/class/drm/<card>/device/vendor
_DRM_KNOWN_VENDORS = {"0x8086", "0x1002", "0x10de"}


def _has_drm_gpu():
    """Return True if a known physical GPU is present in DRM sysfs."""
    try:
        entries = sorted(os.listdir("/sys/class/drm"))
    except OSError as exc:
        raise OpenGLError(
            "Could not read /sys/class/drm: {}".format(exc)
        ) from exc
    for entry in entries:
        if not entry.startswith("card") or not entry[4:].isdigit():
            continue
        vendor_path = "/sys/class/drm/{}/device/vendor".format(entry)
        try:
            with open(vendor_path) as f:
                vid = f.read().strip().lower()
            if vid in _DRM_KNOWN_VENDORS:
                return True
        except OSError as exc:
            logging.warning("Could not read %s: %s", vendor_path, exc)
    return False


def cmd_resource():
    if not _has_drm_gpu():
        raise OpenGLError(
            "No known GPU found in DRM sysfs (/sys/class/drm)"
        )
    logging.info("Found an OpenGL-capable GPU in DRM sysfs")


def cmd_validate_install():
    arch_triple = get_arch_triple()
    host_egl = "/usr/lib/{}/libEGL.so.1".format(arch_triple)
    if not os.path.isfile(host_egl):
        raise OpenGLError(
            "Host EGL library not found at {}. "
            "Install libegl-mesa0 or equivalent"
            " before running host OpenGL tests".format(host_egl)
        )
    logging.info("Host EGL library found at %s", host_egl)


def cmd_run_test(test_args):
    snap = "/snap/opengl-cts/current"
    result = subprocess.run(
        ["{}/test".format(snap), "--no-confinement"] + test_args,
        env=dict(os.environ, SNAP=snap),
    )
    return result.returncode


def main():
    logging.basicConfig(
        format="%(levelname)s: %(message)s", level=logging.INFO
    )
    if len(sys.argv) < 2:
        logging.error(
            "Usage: gl_host.py {resource,validate-install,run-test} [args...]"
        )
        return 1
    command = sys.argv[1]
    try:
        if command == "resource":
            cmd_resource()
        elif command == "validate-install":
            cmd_validate_install()
        elif command == "run-test":
            return cmd_run_test(sys.argv[2:])
        else:
            logging.error("Unknown command: %s", command)
            return 1
    except (RuntimeError, OpenGLError) as exc:
        logging.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
