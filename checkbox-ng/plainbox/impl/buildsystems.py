# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
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
:mod:`plainbox.impl.buildsystems` -- build system interfaces
============================================================
"""

import glob
import shlex
import os

from plainbox.abc import IBuildSystem
from plainbox.impl.secure.plugins import PkgResourcesPlugInCollection


# python3.2 doesn't have shlex.quote
# so let's use the bundled copy here
if not hasattr(shlex, 'quote'):
    from ._shlex import quote
    shlex.quote = quote


class MakefileBuildSystem(IBuildSystem):
    """
    A build system for projects using classic makefiles
    """

    def probe(self, src_dir: str) -> int:
        # If a configure script exists (autotools?) then let's not pretend we
        # do the whole thing and bail out. It's better to let test authors to
        # customize everything.
        if os.path.isfile(os.path.join(src_dir, "configure")):
            return 0
        if os.path.isfile(os.path.join(src_dir, "Makefile")):
            return 90
        return 0

    def get_build_command(self, src_dir: str, build_dir: str) -> str:
        return "VPATH={} make -f {}".format(
            shlex.quote(os.path.relpath(src_dir, build_dir)),
            shlex.quote(os.path.relpath(
                os.path.join(src_dir, 'Makefile'), build_dir)))


class AutotoolsBuildSystem(IBuildSystem):
    """
    A build system for projects using autotools
    """

    def probe(self, src_dir: str) -> int:
        if os.path.isfile(os.path.join(src_dir, "configure")):
            return 90
        return 0

    def get_build_command(self, src_dir: str, build_dir: str) -> str:
        return "{}/configure && make".format(
            shlex.quote(os.path.relpath(src_dir, build_dir)))


class GoBuildSystem(IBuildSystem):
    """
    A build system for projects written in go
    """

    def probe(self, src_dir: str) -> int:
        if glob.glob("{}/*.go".format(src_dir)) != []:
            return 50
        return 0

    def get_build_command(self, src_dir: str, build_dir: str) -> str:
        return "go build {}/*.go".format(os.path.relpath(src_dir, build_dir))


# Collection of all buildsystems
all_buildsystems = PkgResourcesPlugInCollection('plainbox.buildsystem')
