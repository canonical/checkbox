#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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

from gettext import bindtextdomain
from gettext import dgettext

from plainbox.impl.providers.special import get_exporters_def
from plainbox.provider_manager import DevelopCommand
from plainbox.provider_manager import InstallCommand
from plainbox.provider_manager import N_
from plainbox.provider_manager import manage_py_extension
from plainbox.provider_manager import setup

# NOTE: this is not a good example of manage.py as it is internally bound to
# plainbox. Don't just copy paste this as good design, it's *not*.
# Use `plainbox startprovider` if you want to get a provider template to edit.
exporters_def = get_exporters_def()


def _(msgid):
    """
    manage.py specific gettext that uses the manifest provider domain
    """
    return dgettext(exporters_def.gettext_domain, msgid)


# This is exporters_def.description,
# we need it here to extract is as a part of this provider
N_("Exporters Provider")


@manage_py_extension
class DevelopCommandExt(DevelopCommand):
    __doc__ = DevelopCommand.__doc__

    name = 'develop'

    def invoked(self, ns):
        print(_("The Exporters provider is special"))
        print(_("You don't need to develop it explicitly"))


@manage_py_extension
class InstallCommandExt(InstallCommand):
    __doc__ = InstallCommand.__doc__

    name = 'install'

    def invoked(self, ns):
        print(_("The Exporters provider is special"))
        print(_("You don't need to install it explicitly"))


if __name__ == "__main__":
    if exporters_def.effective_locale_dir:
        bindtextdomain(
            exporters_def.gettext_domain, exporters_def.effective_locale_dir)
    setup(
        name=exporters_def.name,
        version=exporters_def.version,
        description=exporters_def.description,
        gettext_domain=exporters_def.gettext_domain
    )
