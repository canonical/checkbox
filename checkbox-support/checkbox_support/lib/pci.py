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
#

# See http://pciids.sourceforge.net/pci.ids.bz2
class Pci:

    BASE_CLASS_STORAGE              = 1
    CLASS_STORAGE_SCSI              = 0
    CLASS_STORAGE_IDE               = 1
    CLASS_STORAGE_FLOPPY            = 2
    CLASS_STORAGE_IPI               = 3
    CLASS_STORAGE_RAID              = 4
    CLASS_STORAGE_OTHER             = 80

    BASE_CLASS_NETWORK              = 2
    CLASS_NETWORK_ETHERNET          = 0
    CLASS_NETWORK_TOKEN_RING        = 1
    CLASS_NETWORK_FDDI              = 2
    CLASS_NETWORK_ATM               = 3
    CLASS_NETWORK_OTHER             = 80
    CLASS_NETWORK_WIRELESS          = 128

    BASE_CLASS_DISPLAY              = 3
    CLASS_DISPLAY_VGA               = 0
    CLASS_DISPLAY_XGA               = 1
    CLASS_DISPLAY_3D                = 2
    CLASS_DISPLAY_OTHER             = 80

    BASE_CLASS_MULTIMEDIA           = 4
    CLASS_MULTIMEDIA_VIDEO          = 0
    CLASS_MULTIMEDIA_AUDIO          = 1
    CLASS_MULTIMEDIA_PHONE          = 2
    CLASS_MULTIMEDIA_AUDIO_DEVICE   = 3
    CLASS_MULTIMEDIA_OTHER          = 80

    BASE_CLASS_BRIDGE               = 6
    CLASS_BRIDGE_HOST               = 0
    CLASS_BRIDGE_ISA                = 1
    CLASS_BRIDGE_EISA               = 2
    CLASS_BRIDGE_MC                 = 3
    CLASS_BRIDGE_PCI                = 4
    CLASS_BRIDGE_PCMCIA             = 5
    CLASS_BRIDGE_NUBUS              = 6
    CLASS_BRIDGE_CARDBUS            = 7
    CLASS_BRIDGE_RACEWAY            = 8
    CLASS_BRIDGE_OTHER              = 80

    BASE_CLASS_COMMUNICATION        = 7
    CLASS_COMMUNICATION_SERIAL      = 0
    CLASS_COMMUNICATION_PARALLEL    = 1
    CLASS_COMMUNICATION_MULTISERIAL = 2
    CLASS_COMMUNICATION_MODEM       = 3
    CLASS_COMMUNICATION_OTHER       = 80

    BASE_CLASS_INPUT                = 9
    CLASS_INPUT_KEYBOARD            = 0
    CLASS_INPUT_PEN                 = 1
    CLASS_INPUT_MOUSE               = 2
    CLASS_INPUT_SCANNER             = 3
    CLASS_INPUT_GAMEPORT            = 4
    CLASS_INPUT_OTHER               = 80

    BASE_CLASS_SERIAL               = 12
    CLASS_SERIAL_FIREWIRE           = 0
    CLASS_SERIAL_ACCESS             = 1

    BASE_CLASS_WIRELESS             = 13
    CLASS_WIRELESS_BLUETOOTH        = 17

    CLASS_SERIAL_SSA                = 2
    CLASS_SERIAL_USB                = 3
    CLASS_SERIAL_FIBER              = 4
    CLASS_SERIAL_SMBUS              = 5
