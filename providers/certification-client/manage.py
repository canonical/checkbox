#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2012, 2013, 2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

import shutil
import os

from plainbox.provider_manager import InstallCommand
from plainbox.provider_manager import SourceDistributionCommand
from plainbox.provider_manager import _logger
from plainbox.provider_manager import manage_py_extension
from plainbox.provider_manager import setup, N_, _


@manage_py_extension
class SourceDistributionCommandExt(SourceDistributionCommand):
    # Overridden version of SourceDistributionCommand that handles launcher/
    __doc__ = SourceDistributionCommand.__doc__
    _INCLUDED_ITEMS = SourceDistributionCommand._INCLUDED_ITEMS + [
        'COPYING', 'launcher']


@manage_py_extension
class InstallCommandExt(InstallCommand):
    # Overridden version of InstallCommand that handles launcher/
    __doc__ = InstallCommand.__doc__
    name = 'install'

    def invoked(self, ns):
        super().invoked(ns)
        self._copy_launcher(ns)

    @property
    def launcher_dir(self):
        return os.path.join(self.definition.location, 'launcher')

    def _copy_launcher(self, ns):
        for name in os.listdir(self.launcher_dir):
            src_file = os.path.join(self.launcher_dir, name)
            if os.path.isfile(src_file) and name.endswith('.desktop'):
                self._copy_desktop_file(ns, src_file)
            elif os.path.isfile(src_file) and os.access(src_file, os.X_OK):
                self._copy_executable(ns, src_file)
            else:
                _logger.warning(_("unexpected file: %s"), os.path.relpath(
                    src_file, self.definition.location))

    def _copy_desktop_file(self, ns, src_file):
        destdir = ns.root + os.path.join(ns.prefix, 'share', 'applications')
        os.makedirs(destdir, exist_ok=True)
        shutil.copy(src_file, destdir)

    def _copy_executable(self, ns, src_file):
        destdir = ns.root + os.path.join(ns.prefix, 'bin')
        os.makedirs(destdir, exist_ok=True)
        shutil.copy(src_file, destdir)

    def _copy_all_executables(self, root, prefix, layout, provider):
        if provider.executable_list:
            super()._copy_all_executables(root, prefix, layout, provider)


setup(
    name='2013.com.canonical.certification:certification-client',
    version="1.0",
    description=N_("Client Certification provider"),
    gettext_domain="2013_com_canonical_certification_certification-client",
    deprecated=False,
    strict=False
)
