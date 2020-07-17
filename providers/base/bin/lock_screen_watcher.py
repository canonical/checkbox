#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2018 Canonical Ltd.
# Written by: Sylvain Pineau <sylvain.pineau@canonical.com>
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

import dbus
import gi
from dbus.mainloop.glib import DBusGMainLoop
gi.require_version('GLib', '2.0')
from gi.repository import GObject  # noqa: E402
from gi.repository import GLib     # noqa: E402


def filter_cb(bus, message):
    if message.get_member() == "EventEmitted":
        args = message.get_args_list()
        if args[0] == "desktop-lock":
            print("Lock Screen detected")
            mainloop.quit()
    elif message.get_member() == "ActiveChanged":
        args = message.get_args_list()
        if args[0] == True:  # noqa: E712
            print("Lock Screen detected")
            mainloop.quit()


def on_timeout_expired():
    print("You have failed to perform the required manipulation in time")
    raise SystemExit(1)


DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
bus.add_match_string("type='signal',interface='com.ubuntu.Upstart0_6'")
bus.add_match_string("type='signal',interface='org.gnome.ScreenSaver'")
bus.add_message_filter(filter_cb)
mainloop = GLib.MainLoop()
GObject.timeout_add_seconds(30, on_timeout_expired)
mainloop.run()
