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
:mod:`plainbox.impl.commands.inv_device` -- device sub-command (invocation)
===========================================================================

This module contains the implementation parts of the 'plainbox device' command.
"""
from plainbox.i18n import gettext as _
from plainbox.impl.device import LocalDevice


class DeviceInvocation:
    """
    Invocation of the 'plainbox device' command.

    :ivar ns:
        The argparse namespace obtained from :class:`DeviceCommand`
    """

    def __init__(self, ns):
        self.ns = ns

    def run(self):
        device_list = LocalDevice.discover()
        for device in device_list:
            print(device.cookie)
            break
        else:
            print(_("No supported devices detected?"))
