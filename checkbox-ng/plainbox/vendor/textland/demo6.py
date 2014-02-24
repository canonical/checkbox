#!/usr/bin/env python3
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
from textland import DrawingContext
from textland import EVENT_KEYBOARD
from textland import EVENT_RESIZE
from textland import Event
from textland import IApplication
from textland import Size
from textland import TextImage
from textland import get_display


class DemoApp(IApplication):

    def __init__(self):
        self.image = TextImage(Size(0, 0))

    def consume_event(self, event: Event):
        if event.kind == EVENT_RESIZE:
            self.image = TextImage(event.data)  # data is the new size
        elif event.kind == EVENT_KEYBOARD and event.data.key == 'q':
            raise StopIteration
        self.repaint(event)
        return self.image

    def repaint(self, event: Event) -> None:
        ctx = DrawingContext(self.image)
        if self.image.size.width < 65 or self.image.size.height < 18:
            self._paint_resize_msg(ctx)
        else:
            self._paint_color_table(ctx)

    def _paint_color_table(self, ctx: DrawingContext) -> None:
        CELL_WIDTH = 4
        NUM_COLORS = 16
        for fg in range(NUM_COLORS):
            for bg in range(NUM_COLORS):
                ctx.attributes.reset()
                ctx.border(
                    0, self.image.size.width - (NUM_COLORS * CELL_WIDTH) - 1,
                    0, self.image.size.height - NUM_COLORS - 2)
                ctx.move_to(1 + fg * CELL_WIDTH, 1 + bg)
                ctx.attributes.fg = fg
                ctx.attributes.bg = bg
                ctx.print("{:X}+{:X}".format(fg, bg))

    def _paint_resize_msg(self, ctx: DrawingContext) -> None:
        text = "Please enlarge this window"
        ctx.move_to(
            (self.image.size.width - len(text)) // 2,
            self.image.size.height // 2)
        ctx.print(text)


def main():
    display = get_display()
    display.run(DemoApp())


if __name__ == "__main__":
    main()
