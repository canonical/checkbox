# This file is part of Checkbox.
#
# Copyright 2013-2026 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
#
# PEP440 version pattern:
# Copyright (c) Donald Stufft and individual contributors.
# All rights reserved.
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

import os
import sys
import logging

from pathlib import Path
from functools import lru_cache
from collections import defaultdict

logger = logging.getLogger("plainbox.secure.providers.custom_frontend")

if os.getenv("SNAP"):
    CUSTOM_FRONTEND_LOCATION = Path(os.getenv("SNAP")) / "custom_frontends"
else:
    CUSTOM_FRONTEND_LOCATION = None


def custom_frontend_roots() -> list:
    if not CUSTOM_FRONTEND_LOCATION:
        return []
    try:
        return list(filter(Path.is_dir, CUSTOM_FRONTEND_LOCATION.iterdir()))
    except FileNotFoundError:
        return []


def paths_to_custom_frontend_path(frontend_root, paths) -> list:
    frontend_paths = [frontend_root / path for path in paths]
    return [str(path) for path in frontend_paths if path.exists()]


def parse_extra_path_environment_file(custom_frontend_root) -> defaultdict:
    extra_path_environment = custom_frontend_root / "extra_path_environment"
    try:
        text = extra_path_environment.read_text()
    except FileNotFoundError:
        return defaultdict(list)
    lines = text.splitlines()
    lines = (l.strip() for l in lines)
    lines = filter(bool, lines)
    lines = [l for l in lines if not l.startswith("#")]
    to_r = defaultdict(list)
    for line in lines:
        try:
            key, value = line.split("+=", maxsplit=1)
            key = key.strip()
            value = value.strip()
            if value.startswith("/"):
                value = value[1:]
            to_r[key].append(str(custom_frontend_root / value))
        except ValueError:
            logger.error(
                "Ignoring malformed line in extra_path_environment {}".format(
                    line
                )
            )
    return to_r


@lru_cache(maxsize=1)
def extra_snap_environment() -> dict:
    """
    Additional environment variables from `$PROVIDER_ROOT/extra_path_environment`

    $PROVIDER_ROOT is either $SNAP if test comes from a runtime provider
    or custom_frontend_root
    """
    runtime_root = os.getenv("SNAP")
    if not runtime_root:
        return {}

    runtime_root = Path(runtime_root)
    # Always load the runtime ones as frontend assume that the dependencies
    # from the frontend are available
    to_r = parse_extra_path_environment_file(runtime_root)

    for custom_frontend_root in custom_frontend_roots():
        custom_frontend_envvars = parse_extra_path_environment_file(
            custom_frontend_root
        )

        # give priority to the custom_frontend additions
        for key, value in custom_frontend_envvars.items():
            to_r[key] = value + to_r[key]

    return dict(to_r)


@lru_cache(maxsize=1)
def extra_PYTHONPATH() -> list:
    """
    additional entry for PYTHONPATH, if needed.

    This entry is required for Checkbox scripts to import the correct
    Checkbox python libraries.
    """
    if not os.getenv("SNAP"):
        return []
    python_name = "python{}.{}".format(
        sys.version_info.major, sys.version_info.minor
    )
    paths = [
        # Don't put a / in front or you will point to the root one
        # as Path("/a/b") / "/a" == Path("/a")
        "lib/{}/site-packages".format(python_name),
        "lib/{}/dist-packages".format(python_name),
        "usr/lib/{}/site-packages".format(python_name),
        "usr/lib/{}/lib-dynload".format(python_name),
        "usr/lib/python3/dist-packages",
        "usr/local/lib/{}/dist-packages".format(python_name),
    ]
    return [
        path
        for custom_frontend_root in custom_frontend_roots()
        for path in paths_to_custom_frontend_path(custom_frontend_root, paths)
    ]


@lru_cache(maxsize=1)
def extra_PATH() -> list:
    """
    Additional PATH entries necessary to make tests in this provider work

    This includes all PATH entries that are necessary beside bin/ given
    that it is populated (merged with the others) in the nest
    """
    if not os.getenv("SNAP"):
        return []
    paths = [
        # Don't put a / in front or you will point to the root one
        # as Path("/a/b") / "/a" == Path("/a")
        "usr/local/bin",
        "usr/local/sbin",
        "usr/bin",
        "usr/sbin",
        "bin",
        "sbin",
    ]
    return [
        path
        for custom_frontend_root in custom_frontend_roots()
        for path in paths_to_custom_frontend_path(custom_frontend_root, paths)
    ]


@lru_cache(maxsize=1)
def extra_LD_LIBRARY_PATH():
    """
    Additional LD_LIBRARY_PATH necessary to run tests in this provider
    """
    if not os.getenv("SNAP"):
        return []
    paths = [
        # Don't put a / in front or you will point to the root one
        # as Path("/a/b") / "/a" == Path("/a")
        "usr/lib",
        "usr/lib64",
        "lib",
        "lib64",
    ]
    return [
        path
        for custom_frontend_root in custom_frontend_roots()
        for path in paths_to_custom_frontend_path(custom_frontend_root, paths)
    ]
