# This file is part of textland.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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

from .bits import Offset, Rect
from .image import TextImage, TextAttributes


class DrawingContext:
    """
    Context for simple text drawing
    """

    def __init__(self, image: TextImage):
        self.image = image
        self.offset = Offset(0, 0)
        self.clip = Rect(0, 0, image.size.width, image.size.height)
        self.attributes = TextAttributes()

    def fill(self, c: str) -> None:
        packed_attr = self.attributes.packed
        for x in range(self.clip.x1, self.clip.x2):
            for y in range(self.clip.y1, self.clip.y2):
                self.image.put(x, y, c, packed_attr)

    def clip_to(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self.clip = Rect(x1, y1, x2, y2)

    def clip_by(self, dx1: int, dy1: int, dx2: int, dy2: int) -> None:
        x1 = self.clip.x1 + dx1
        y1 = self.clip.y1 + dy1
        x2 = self.clip.x2 + dx2
        y2 = self.clip.y2 + dy2
        self.clip = Rect(x1, y1, x2, y2)

    def move_to(self, x: int, y: int) -> None:
        """
        Move paint offset to the specified spot
        """
        self.offset = Offset(x, y)

    def move_by(self, dx: int, dy: int) -> None:
        """
        Move paint offset by the specified delta
        """
        self.offset = Offset(self.offset.x + dx, self.offset.y + dy)

    def print(self, text: str) -> None:
        """
        Print the specified text

        Multi-line strings are supported. The offset and clipping area
        is respected. Painting beyond the clipping area is ignored

        The offset is automatically adjusted to point
        to the end of the string.
        """
        pa = self.attributes.packed
        for line in text.splitlines():
            self._put_line(line, pa)
            self.move_by(0, 1)

    def border(self, lm=0, rm=0, tm=0, bm=0) -> None:
        """
        Draw a border around the edges of the current cli. Each parameter
        specifies the margin to use for a specific side of the border.
        """
        pa = self.attributes.packed
        self._put_x_y_c_pa(self.clip.x1 + lm, self.clip.y1 + tm, '┌', pa)
        self._put_x_y_c_pa(self.clip.x1 + lm, self.clip.y2 - 1 - bm, '└', pa)
        self._put_x_y_c_pa(self.clip.x2 - rm - 1, self.clip.y1 + tm, '┐', pa)
        self._put_x_y_c_pa(
            self.clip.x2 - rm - 1, self.clip.y2 - 1 - bm, '┘', pa)
        for x in range(self.clip.x1 + 1 + lm, self.clip.x2 - 1 - rm):
            self._put_x_y_c_pa(x, self.clip.y1 + tm, '─', pa)
            self._put_x_y_c_pa(x, self.clip.y2 - 1 - bm, '─', pa)
        for y in range(self.clip.y1 + 1 + tm, self.clip.y2 - 1 - bm):
            self._put_x_y_c_pa(self.clip.x1 + lm, y, '│', pa)
            self._put_x_y_c_pa(self.clip.x2 - rm - 1, y, '│', pa)

    def _put_line(self, text: str, pa: int) -> None:
        """
        Print one line, respecting clipping and offset
        """
        if "\n" in text:
            raise ValueError("should be without any newlines")
        for dx, c in enumerate(text):
            self._put_dx_dy_c_pa(dx, 0, c, pa)

    def _put_dx_dy_c_pa(self, dx: int, dy: int, c: str, pa: int) -> None:
        x = self.offset.x + dx
        y = self.offset.y + dy
        self._put_x_y_c_pa(x, y, c, pa)

    def _put_x_y_c_pa(self, x: int, y: int, c: str, pa: int) -> None:
        if (self.clip.x1 <= x < self.clip.x2
                and self.clip.y1 <= y < self.clip.y2):
            self.image.put(x, y, c, pa)
