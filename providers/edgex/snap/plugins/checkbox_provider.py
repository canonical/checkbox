# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2016-2019 Canonical Ltd
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

import os

from snapcraft.internal import mangling
from snapcraft.plugins import plainbox_provider


class CheckboxProvider(plainbox_provider.PlainboxProviderPlugin):

    def __init__(self, name, options, project):
        super().__init__(name, options, project)
        self.build_snaps.append("checkbox-provider-tools")
        if project.info.base in (None, "core16"):
            self.build_snaps.append("checkbox16")
        if project.info.base == "core18":
            self.build_snaps.append("checkbox18")

    def build(self):
        env = os.environ.copy()
        # Ensure the first provider does not attempt to validate against
        # providers installed on the build host by initialising PROVIDERPATH
        # to empty
        env["PROVIDERPATH"] = ""
        provider_stage_dir = os.path.join(self.project.stage_dir, "providers")
        if os.path.exists(provider_stage_dir):
            provider_dirs = [
                os.path.join(provider_stage_dir, provider)
                for provider in os.listdir(provider_stage_dir)
            ]
            env["PROVIDERPATH"] = ":".join(provider_dirs)
        for snap_name in self.build_snaps:
            build_snap_provider_dir = os.path.join(
                "/snap", snap_name, "current", "providers")
            if os.path.exists(build_snap_provider_dir):
                provider_dirs = [
                    os.path.join(build_snap_provider_dir, provider)
                    for provider in os.listdir(build_snap_provider_dir)
                    if 'edgex' not in provider
                ]
                env["PROVIDERPATH"] = ":".join(provider_dirs)
        cmd = "checkbox-provider-tools"
        self.run([cmd, "validate"], env=env)
        self.run([cmd, "build"])
        self.run(
            [
                cmd,
                "install",
                "--layout=relocatable",
                "--prefix=/providers/{}".format(self.name),
                "--root={}".format(self.installdir),
            ]
        )
        mangling.rewrite_python_shebangs(self.installdir)
