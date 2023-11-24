# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
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
This module provides functions helping in determining how and where Checkbox
is being run.
"""

import os

from functools import lru_cache


@lru_cache(maxsize=1)
def on_core():
    """
    Return True if we are running on Ubuntu Core. False otherwise.

    If we get an exception while trying to read the file, we let it bubble up.
    """

    with open("/etc/os-release") as os_release_file:
        return any(
            line.startswith("NAME=Ubuntu Core") for line in os_release_file
        )


def application_name():
    """
    Return the name of the application.

    In case of snaps this means the full name of current snap. For example:
    checkbox-acme

    If the snap is just a generic checkbox snap, then the name will be just
    checkbox.

    If we're running from within a deb package, then the name will always be
    checkbox, as the project-specific providers don't change the name of the
    checkbox application.
    """

    return os.environ.get("SNAP_NAME", "checkbox")
