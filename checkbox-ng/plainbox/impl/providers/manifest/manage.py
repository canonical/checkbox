#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
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

"""Management script for the manifest provider."""

from gettext import bindtextdomain
from gettext import dgettext

from guacamole.ingredients.ansi import ANSIFormatter

from plainbox.impl.providers.special import get_manifest_def
from plainbox.provider_manager import DevelopCommand
from plainbox.provider_manager import InstallCommand
from plainbox.provider_manager import ManageCommand
from plainbox.provider_manager import N_
from plainbox.provider_manager import manage_py_extension
from plainbox.provider_manager import setup

# NOTE: this is not a good example of manage.py as it is internally bound to
# plainbox. Don't just copy paste this as good design, it's *not*.
# Use `plainbox startprovider` if you want to get a provider template to edit.
manifest_def = get_manifest_def()


def _(msgid):
    """manage.py specific gettext that uses the manifest provider domain."""
    return dgettext(manifest_def.gettext_domain, msgid)


# This is manifest_def.description,
# we need it here to extract is as a part of this provider
N_("Hardware Manifest Provider")


@manage_py_extension
class DevelopCommandExt(DevelopCommand):

    __doc__ = DevelopCommand.__doc__

    name = 'develop'

    def invoked(self, ns):
        print(_("The Manifest provider is special"))
        print(_("You don't need to develop it explicitly"))


@manage_py_extension
class InstallCommandExt(InstallCommand):

    __doc__ = InstallCommand.__doc__

    name = 'install'

    def invoked(self, ns):
        print(_("The Manifest provider is special"))
        print(_("You don't need to install it explicitly"))


@manage_py_extension
class L10NCommand(ManageCommand):

    """display localized data specific to this provider."""

    name = 'l10n'

    def register_parser(self, subparsers):
        self.add_subcommand(subparsers)

    def invoked(self, ns):
        provider = self.get_provider()
        ansi = ANSIFormatter()
        ansi.aprint(_(
            "Legend: {native}N: native{reset},"
            " {raw}R: raw{reset},"
            " {localized}L: localized{reset}"
        ).format(
            native=ansi("", fg='bright_green', reset=False),
            raw=ansi("", fg='bright_blue', reset=False),
            localized=ansi("", fg='bright_yellow', reset=False),
            reset=ansi("", reset=True)),
        bold=1)
        for unit in provider.unit_list:
            need_unit_header = True
            for field in unit.Meta.fields.get_all_symbols():
                field = str(field)
                if not unit.is_translatable_field(field):
                    continue
                if need_unit_header:
                    ansi.aprint("In unit: {!r}".format(unit))
                    need_unit_header = False
                ansi.aprint("Internationalized field: {!a}".format(field))
                ansi.aprint('N: {!a}'.format(
                    unit.get_record_value(field)), fg='bright_green')
                ansi.aprint('R: {!a}'.format(
                    unit.get_raw_record_value(field)), fg='bright_blue')
                ansi.aprint('L: {!a}'.format(
                    unit.get_translated_record_value(field)),
                    fg='bright_yellow')


if __name__ == "__main__":
    if manifest_def.effective_locale_dir:
        bindtextdomain(
            manifest_def.gettext_domain, manifest_def.effective_locale_dir)
    setup(
        name=manifest_def.name,
        version=manifest_def.version,
        description=manifest_def.description,
        gettext_domain=manifest_def.gettext_domain
    )
