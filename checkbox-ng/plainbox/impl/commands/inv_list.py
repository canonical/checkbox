# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
:mod:`plainbox.impl.commands.inv_list` -- list sub-command
==========================================================
"""
from plainbox.i18n import gettext as _
from plainbox.impl.highlevel import Explorer


class ListInvocation:

    def __init__(self, provider_loader, ns):
        self.explorer = Explorer(provider_loader())
        self.group = ns.group
        self.show_attrs = ns.attrs

    def run(self):
        obj = self.explorer.get_object_tree()
        self._show(obj)

    def _show(self, obj, indent=None):
        if indent is None:
            indent = ""
        # Apply optional filtering
        if self.group is None or obj.group == self.group:
            # Display the object name and group
            print("{}{} {!r}".format(indent, obj.group, obj.name))
            indent += "  "
            # It would be cool if this would draw an ASCI-art tree
            if self.show_attrs:
                for key, value in obj.attrs.items():
                    print("{}{}: {!r}".format(indent, key, value))
        if obj.children:
            if self.group is None:
                print("{}{}".format(indent, _("children")))
                indent += "  "
            for child in obj.children:
                self._show(child, indent)
