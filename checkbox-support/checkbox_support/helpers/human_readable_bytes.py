# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
checkbox_support.helpers.human_readable_bytes
=============================================

Utility class for representing ammount of bytes in human readable fashion
"""
import sys
from math import copysign, log, trunc


class HumanReadableBytes(int):
    """
    This class helps to build an int from human-readable form like 1kB or
    16 MiB. Suffixes may be one of both, SI or IEC.
    When printed, it also reduces itself to human-readable form.
    """
    def __new__(cls, x=0, *args):
        if isinstance(x, int) or x.isnumeric():
            return super().__new__(cls, x, *args)
        return super().__new__(cls, cls._parse_human_readable(x))

    def _parse_human_readable(s):
        """
        Create HumanReadableBytes number from string with a number and a suffix

        :param s:
            The text to parse. This syntax is NUMBER SCALE where NUMBER is any
            positive integer and SCALE is one of the prefixes defined here:
            http://en.wikipedia.org/wiki/Binary_prefix
        :returns:
            The numeric value of the text
        :raises ValueError:
            When suffix is not recognized or text could not have been parsed
        """
        suffixes = {}
        si_suffixes = '', 'k', 'm', 'g', 't', 'p', 'e', 'z', 'y'
        for power, suf in enumerate(si_suffixes):
            suffixes[suf] = 1000 ** power
            suffixes[suf+'b'] = 1000 ** power
        iec_suffixes = '', 'ki', 'mi', 'gi', 'ti', 'pi', 'ei', 'zi', 'yi'
        for power, suf in enumerate(iec_suffixes):
            suffixes[suf] = 1024 ** power
            suffixes[suf+'b'] = 1024 ** power
        num = ""
        while s and (s[0].isdigit() or s[0] == '-'):
            num += s[0]
            s = s[1:]
        s = s.strip()
        if s.lower() not in suffixes.keys():
            raise ValueError("Unrecognized unit suffis - %s" % s)
        return int(num) * suffixes[s.lower()]

    def __repr__(self):
        return "HumanReadableBytes({})".format(super().__repr__())

    def __str__(self):
        my_bytes = float(self)
        if self == 0:
            return "0B"
        suffixes = ["B", "KiB", "MiB", "GiB", "TiB",
                    "PiB", "EiB", "ZiB", "YiB"]
        sign = copysign(1, my_bytes)
        my_bytes = abs(my_bytes)
        # my_bytes' base-1024 logarithm.
        exponent = log(my_bytes, 1024)
        try:
            suffix = suffixes[int(exponent)]
        except IndexError:
            return "(Number too large)"
        scalar = my_bytes / (1024**int(exponent))
        if scalar - trunc(scalar) < sys.float_info.epsilon:
            return "{:.0f}{}".format(sign * scalar, suffix)
        else:
            return "{:.2f}{}".format(sign * scalar, suffix)
