# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2016-2021 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from textwrap import dedent
from typing import Any, Dict, List, Set

from snapcraft.plugins.v2 import PluginV2
from snapcraft.project import Project, get_snapcraft_yaml


class PluginImpl(PluginV2):
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {}

    def __init__(self, *, part_name: str, options) -> None:
        super().__init__(part_name=part_name, options=options)
        self.project = Project(snapcraft_yaml_file_path=get_snapcraft_yaml())

    def get_build_snaps(self) -> Set[str]:
        return set()

    def get_build_packages(self) -> Set[str]:
        return set()

    def get_build_environment(self) -> Dict[str, str]:
        if self.project._get_build_base() == "core22":
            site_pkg_path = "$SNAPCRAFT_STAGE/lib/python3.10/site-packages:$SNAPCRAFT_STAGE/usr/lib/python3/dist-packages"
        else:
            site_pkg_path = "$SNAPCRAFT_STAGE/lib/python3.8/site-packages"
        return {"PYTHONPATH": site_pkg_path}

    def get_build_commands(self) -> List[str]:
        build_commands = [
            'for path in $(find "$SNAPCRAFT_STAGE/providers/" -mindepth 1 -maxdepth 1 -type d); do export PROVIDERPATH=$path${PROVIDERPATH:+:$PROVIDERPATH}; done',
            'python3 manage.py validate',
            'python3 manage.py build',
            'python3 manage.py install '
            '--layout=relocatable '
            '--prefix=/providers/{} '
            '--root="${{SNAPCRAFT_PART_INSTALL}}"'.format(self.name)
        ]
        # See https://github.com/snapcore/snapcraft/blob/master/snapcraft/plugins/v2/python.py
        # Now fix shebangs.
        # TODO: replace with snapcraftctl once the two scripts are consolidated
        # and use mangling.rewrite_python_shebangs.
        build_commands.append(
            dedent(
                """\
            for e in $(find "${SNAPCRAFT_PART_INSTALL}" -type f -executable)
            do
                if head -1 "${e}" | grep -q "python" ; then
                    sed \\
                        -r '1 s|#\\!.*python3?$|#\\!/usr/bin/env python3|' \\
                        -i "${e}"
                fi
            done
        """
            )
        )
        return build_commands
