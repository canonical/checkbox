# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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
#
"""
checkbox_support.dbus
=============

Utility modules for working with various things accessible over dbus
"""

import logging

from dbus import SystemBus
from dbus.mainloop.glib import DBusGMainLoop
from dbus import (Array, Boolean, Byte, Dictionary, Double, Int16, Int32,
                  Int64, ObjectPath, String, Struct, UInt16, UInt32, UInt64)
from gi.repository import GObject


def connect_to_system_bus():
    """
    Connect to the system bus properly.

    Returns a tuple (system_bus, loop) where loop is a GObject.MainLoop
    instance. The loop is there so that you can listen to signals.
    """
    # We'll need an event loop to observe signals. We will need the instance
    # later below so let's keep it. Note that we're not passing it directly
    # below as DBus needs specific API. The DBusGMainLoop class that we
    # instantiate and pass is going to work with this instance transparently.
    #
    # NOTE: DBus tutorial suggests that we should create the loop _before_
    # connecting to the bus.
    logging.debug("Setting up glib-based event loop")
    loop = GObject.MainLoop()
    # Let's get the system bus object. We need that to access UDisks2 object
    logging.debug("Connecting to DBus system bus")
    system_bus = SystemBus(mainloop=DBusGMainLoop())
    return system_bus, loop


def drop_dbus_type(value):
    """
    Convert types from the DBus bindings to their python counterparts.

    This function is mostly lossless, except for arrays of bytes (DBus
    signature "y") that are transparently converted to strings, assuming
    an UTF-8 encoded string.

    The point of this function is to simplify printing of nested DBus data that
    gets displayed in a rather illegible way.
    """
    if isinstance(value, Array) and value.signature == "y":
        # Some other things are reported as array of bytes that are just
        # strings but due to Unix heritage the encoding is not known.
        # In practice it is better to treat them as UTF-8 strings
        return bytes(value).decode("UTF-8", "replace").strip("\0")
    elif isinstance(value, (Struct, Array)):
        return [drop_dbus_type(item) for item in value]
    elif isinstance(value, (Dictionary)):
        return {drop_dbus_type(dict_key): drop_dbus_type(dict_value)
                for dict_key, dict_value in value.items()}
    elif isinstance(value, (String, ObjectPath)):
        return str(value)
    elif isinstance(value, (Byte, UInt16, UInt32, UInt64,
                            Int16, Int32, Int64)):
        return int(value)
    elif isinstance(value, Boolean):
        return bool(value)
    elif isinstance(value, Double):
        return float(value)
    else:
        return value
