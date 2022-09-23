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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

"""
checkbox_support.heuristics.udev
================================

Heuristics for udev.

    Documentation: http://udisks.freedesktop.org/docs/latest/
    Source code: http://cgit.freedesktop.org/systemd/systemd/ (src/udev)
    Bug tracker: http://bugs.freedesktop.org/ (using systemd product)
"""


def is_virtual_device(device_file):
    """
    Given a device name like /dev/ramX, /dev/sdX or /dev/loopX determine if
    this is a virtual device. Virtual devices are typically uninteresting to
    users. The only exception may be nonempty loopback device.

    Possible prior art: gnome-disks, palimpset (precursor, suffering from this
    flaw and showing all the /dev/ram devices by default)
    """
    for part in device_file.split("/"):
        if part.startswith("ram") or part.startswith("loop"):
            return True
    return False
