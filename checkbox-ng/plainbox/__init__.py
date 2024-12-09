# This file is part of Checkbox.
#
# Copyright 2012-2018 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
:mod:`plainbox` -- main package
===============================

Simple checkbox (2008 version) redesign, without the complex message passing

All abstract base classes are in :mod:`plainbox.abc`.
"""

# PEP440 compliant version declaration.
#
# This is used by @public decorator to enforce our public API guarantees.
try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    from importlib_metadata import version, PackageNotFoundError

try:
    __version__ = version("checkbox-ng")
except PackageNotFoundError:
    import logging

    logging.error("Failed to retrieve checkbox-ng version")
    __version__ = "unknown"


def get_version_string():
    import os

    version_string = ""
    if os.environ.get("SNAP_NAME"):
        version_string = "{} {} ({})".format(
            os.environ["SNAP_NAME"],
            os.environ.get("SNAP_VERSION", "unknown_version"),
            os.environ.get("SNAP_REVISION", "unknown_revision"),
        )
    else:
        version_string = "{} {}".format("Checkbox", __version__)
    return version_string


def get_origin():
    """
    Return a dictionary containing information such as the version and what
    packaging method is being used (Python virtual environment, Snap or
    Debian).
    """
    import os
    import subprocess

    if os.getenv("SNAP_NAME"):
        origin = {
            "name": "Checkbox",
            "version": __version__,
            "packaging": {
                "type": "snap",
                "name": os.getenv("SNAP_NAME"),
                "version": os.getenv("SNAP_VERSION"),
                "revision": os.getenv("SNAP_REVISION"),
            },
        }
    elif os.getenv("VIRTUAL_ENV"):
        origin = {
            "name": "Checkbox",
            "version": __version__,
            "packaging": {
                "type": "source",
                "version": __version__,
            },
        }
    else:
        dpkg_info = subprocess.check_output(
            ["dpkg", "-S", __path__[0]], universal_newlines=True
        )
        # 'python3-checkbox-ng: /usr/lib/python3/dist-packages/plainbox\n'
        package_name = dpkg_info.split(":")[0]
        origin = {
            "name": "Checkbox",
            "version": __version__,
            "packaging": {
                "type": "debian",
                "name": package_name,
                "version": __version__,
            },
        }
    return origin
