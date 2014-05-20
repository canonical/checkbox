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

from struct import calcsize


def get_bitmask(key):
    bitmask = []
    for value in reversed(key.split()):
        value = int(value, 16)
        bitmask.append(value)
    return bitmask


def get_bitcount(bitmask):
    bitcount = 0
    for value in bitmask:
        while value:
            bitcount += 1
            value &= (value - 1)
    return bitcount


def test_bit(bit, bitmask, bits=None):
    if bits is None:
        bits = calcsize("l") * 8
    offset = bit % bits
    long = int(bit / bits)
    if long >= len(bitmask):
        return 0
    return (bitmask[long] >> offset) & 1
