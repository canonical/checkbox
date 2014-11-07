# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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
:mod:`checkbox_ng.dbus_ex` -- DBus Extensions
=============================================
"""

__all__ = [
    'service',
    'exceptions',
    'Signature',
    'Struct',
    'types',
    'INTROSPECTABLE_IFACE',
    'PEER_IFACE',
    'PROPERTIES_IFACE',
    'OBJECT_MANAGER_IFACE',
]

import re
import os

if os.getenv("MOCK_DBUS") == "yes":
    import sys
    from plainbox.vendor import mock
    for name in (
        '_dbus_bindings',
        'dbus',
        'dbus._compat',
        'dbus.exceptions',
        'dbus.lowlevel',
        'dbus.mainloop',
        'dbus.mainloop.glib',
        'dbus.service',
        'gi',
        'gi.repository',
    ):
        sys.modules[name] = mock.MagicMock(name=name)
    sys.modules['dbus'].service.Object = object
    sys.modules['dbus'].service.Interface = object
    sys.modules['dbus'].service.InterfaceType = type


from dbus import INTROSPECTABLE_IFACE
from dbus import PEER_IFACE
from dbus import PROPERTIES_IFACE
from dbus import Signature
from dbus import Struct
from dbus import exceptions
from dbus import types

OBJECT_MANAGER_IFACE = "org.freedesktop.DBus.ObjectManager"

from checkbox_ng.dbus_ex import service


def mangle_object_path(path):
    """
    "Mangles" the provided candidate dbus object path to ensure it complies
    with the dbus specification. Returns the mangled path.
    """
    # TODO: It just enforces the valid characters rule, not the rest of the
    # DBus path construction rules
    return re.sub(r"[^a-zA-Z0-9_/]", "_", path)
