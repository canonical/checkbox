# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
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

"""
:mod:`plainbox.impl.service` -- DBus service for PlainBox
=========================================================
"""

import logging

import dbus
import dbus.service

logger = logging.getLogger("plainbox.service")

_BASE_IFACE = "com.canonical.certification."

SERVICE_IFACE = _BASE_IFACE + "PlainBox.Service"


class Service(dbus.service.Object):
    """
    PlainBox DBus Service
    """

    def __init__(self, provider_list, session_state_list, on_exit,
                 conn=None, object_path="/plainbox/service", bus_name=None):
        super(Service, self).__init__(conn, object_path, bus_name)
        self._provider_list = provider_list
        self._session_state_list = session_state_list
        self._on_exit = on_exit
        logger.debug("Created %r", self)

    @dbus.service.method(
        dbus_interface=SERVICE_IFACE, in_signature='', out_signature='')
    def Exit(self):
        """
        Shut down the service and terminate
        """
        # TODO: raise exception when job is in progress
        self._on_exit()
