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
checkbox_support.heuristics.udisks2
===================================

Heuristics for udisks2.

    Documentation: http://udisks.freedesktop.org/docs/latest/
    Source code: http://cgit.freedesktop.org/systemd/systemd/ (src/udev)
    Bug tracker: http://bugs.freedesktop.org/ (using systemd product)
"""

from checkbox_support.parsers.udevadm import CARD_READER_RE
from checkbox_support.parsers.udevadm import FLASH_RE
from checkbox_support.parsers.udevadm import GENERIC_RE


def is_memory_card(vendor, model, udisks2_media):
    """
    Check if the device seems to be a memory card

    The vendor and model arguments are _strings_, not integers.
    The udisks2_media argument is the value of org.freedesktop.UDisks2.Drive/


    This is rather fuzzy, sadly udev and udisks2 don't do a very good job and
    mostly don't specify the "media" property (it has a few useful values, such
    as flash_cf, flash_ms, flash_sm, flash_sd, flash_sdhc, flash_sdxc and
    flash_mmc but I have yet to see a device that reports such values)
    """
    # Treat any udisks2_media that contains 'flash' as a memory card
    if udisks2_media is not None and FLASH_RE.search(udisks2_media):
        return True
    # Treat any device that match model name to the following regular
    # expression as a memory card reader.
    if CARD_READER_RE.search(model):
        return True
    # Treat any device that contains the word 'Generic' in the vendor string as
    # a memory card reader.
    #
    # XXX: This seems odd but strangely enough seems to gets the job done. I
    # guess if I should start filing tons of bugs/patches on udev/udisks2 to
    # just have a few more rules and make this rule obsolete.
    if GENERIC_RE.search(vendor):
        return True
    return False
