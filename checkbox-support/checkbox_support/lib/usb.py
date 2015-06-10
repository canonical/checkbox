#
# This file is part of Checkbox.
#
# Copyright 2008 Canonical Ltd.
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


# See http://www.linux-usb.org/usb.ids
class Usb(object):

    BASE_CLASS_INTERFACE = 0

    BASE_CLASS_AUDIO = 1
    CLASS_AUDIO_CONTROL_DEVICE = 1
    CLASS_AUDIO_STREAMING = 2
    CLASS_AUDIO_MIDI_STREAMING = 3

    BASE_CLASS_COMMUNICATIONS = 2
    CLASS_COMMUNICATIONS_DIRECT_LINE = 1
    CLASS_COMMUNICATIONS_ABSTRACT = 2
    CLASS_COMMUNICATIONS_TELEPHONE = 3

    BASE_CLASS_PRINTER = 7
    CLASS_PRINTER_OTHER = 1

    BASE_CLASS_STORAGE = 8
    CLASS_STORAGE_RBC = 1
    CLASS_STORAGE_SFF = 2
    CLASS_STORAGE_QIC = 3
    CLASS_STORAGE_FLOPPY = 4
    CLASS_STORAGE_SFF = 5
    CLASS_STORAGE_SCSI = 6

    BASE_CLASS_HUB = 9
    CLASS_HUB_UNUSED = 0

    BASE_CLASS_VIDEO = 14
    CLASS_VIDEO_UNDEFINED = 0
    CLASS_VIDEO_CONTROL = 1
    CLASS_VIDEO_STREAMING = 2
    CLASS_VIDEO_INTERFACE_COLLECTION = 3

    BASE_CLASS_WIRELESS = 224
    CLASS_WIRELESS_RADIO_FREQUENCY = 1
    CLASS_WIRELESS_USB_ADAPTER = 2

    PROTOCOL_BLUETOOTH = 1
