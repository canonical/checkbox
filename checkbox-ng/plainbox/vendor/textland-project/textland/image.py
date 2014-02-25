# This file is part of textland.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#
# Textland is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Textland is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Textland.  If not, see <http://www.gnu.org/licenses/>.

from array import array

from .bits import Cell, Size

# ANSI color index
(
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE,
    BRIGHT_BLACK, BRIGHT_RED, BRIGHT_GREEN, BRIGHT_YELLOW, BRIGHT_BLUE,
    BRIGHT_MAGENTA, BRIGHT_CYAN, BRIGHT_WHITE
) = range(16)

# Supported text styles.
NORMAL = 0  # Normal (default style)
REVERSE = 1 << 0  # Reverse background and foreground colors
UNDERLINE = 1 << 1  # Underline mode


class TextImage:
    """
    A rectangular, mutable text image.

    The image supports NORMAL, REVERSE and UNDERLINE as per-cell attributes,
    the 8 colors described in the ANSI standard and the BOLD video attribute
    to render the foreground colors as bright (aka light or intensified).
    """

    def __init__(self, size: Size):
        self.size = size
        self.width = self.size.width
        self.text_buffer = array('u')
        self.text_buffer.extend(' ' * size.width * size.height)
        self.attribute_buffer = array('H')  # Unsigned short
        self.attribute_buffer.extend([0] * size.width * size.height)

    def put(self, x: int, y: int, c: str, pa: int) -> None:
        """
        Put character *c* with attributes *pa* into cell at (*x*, *y*)

        :param x:
            X coordinate
        :param y:
            Y coordinate
        :param c:
            One character string
        :param pa:
            Packed attribute (up to uint16_t)
        """
        assert 0 <= x < self.size.width
        assert 0 <= y < self.size.height
        offset = x + y * self.width
        self.text_buffer[offset] = c
        self.attribute_buffer[offset] = pa

    def get(self, x: int, y: int) -> Cell:
        """
        Get a cell from (*x*, *y*)

        :param x:
            X coordinate
        :param y:
            Y coordinate
        :returns:
            Cell(c, pa)
        """
        offset = x + y * self.width
        return Cell(self.text_buffer[offset], self.attribute_buffer[offset])

    def print_frame(self) -> None:
        text_buffer = self.text_buffer
        width = self.size.width
        height = self.size.height
        print("/{}\\".format('=' * width))
        for y in range(height):
            line = text_buffer[y * width: (y + 1) * width].tounicode()
            print("|{}|".format(line))
        print("\\{}/".format('=' * width))


class TextAttributes:

    def __init__(self):
        self.fg = WHITE
        self.bg = BLACK
        self.style = NORMAL

    def reset(self):
        self.fg = WHITE
        self.bg = BLACK
        self.style = NORMAL

    @property
    def packed(self):
        return ((self.fg & 15) << 8) + ((self.bg & 15) << 4) + (self.style & 3)

    @staticmethod
    def unpack(pa: int) -> (int, int, int):
        """
        Unpack packed attributes into (fg, bg, style)
        """
        fg = (pa >> 8) & 15
        bg = (pa >> 4) & 15
        style = pa & 3
        return fg, bg, style
