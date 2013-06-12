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
:mod:`plainbox.impl.color` -- ANSI color codes
==============================================
"""


class ansi_on:
    """
    ANSI control codes for various useful stuff.
    Reference source: wikipedia
    """

    class f:
        """
        Foreground color attributes
        """
        BLACK = 30
        RED = 31
        GREEN = 32
        YELLOW = 33
        BLUE = 34
        MAGENTA = 35
        CYAN = 36
        WHITE = 37
        # what was 38?
        RESET = 39

    class b:
        """
        Background color attributes
        """
        BLACK = 40
        RED = 41
        GREEN = 42
        YELLOW = 44
        BLUE = 44
        MAGENTA = 45
        CYAN = 46
        WHITE = 47
        # what was 48?
        RESET = 49

    class s:
        """
        Style attributes
        """
        BRIGHT = 1
        DIM = 2
        NORMAL = 22
        RESET_ALL = 0


class ansi_off:

    class f:
        pass

    class b:
        pass

    class s:
        pass


# Convert from numbers to full escape sequences
for obj_on, obj_off in zip(
        (ansi_on.f, ansi_on.b, ansi_on.s),
        (ansi_off.f, ansi_off.b, ansi_off.s)):
    for name in [name for name in dir(obj_on) if name.isupper()]:
        setattr(obj_on, name, "\033[%sm" % getattr(obj_on, name))
        setattr(obj_off, name, "")
