#!/usr/bin/env python3
# This file is part of textland.
#
# Copyright 2014 Canonical Ltd.
# Written by:
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
from textland import DrawingContext
from textland import BRIGHT_GREEN
from textland import EVENT_KEYBOARD
from textland import EVENT_RESIZE
from textland import Event
from textland import IApplication
from textland import RED
from textland import REVERSE
from textland import Size
from textland import TextImage
from textland import UNDERLINE
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

    def repaint(self, event: Event):
        # Draw something on the image
        ctx = DrawingContext(self.image)
        title = "TextLand Cell Character Attribute and Colors Demo Application"
        ctx.move_to((self.image.size.width - len(title)) // 2, 0)
        ctx.print(title)
        ctx.print('=' * len(title))
        ctx.move_to(0, 3)
        ctx.attributes.fg = BRIGHT_GREEN
        ctx.attributes.bg = RED
        ctx.print("Type 'q' to quit")
        ctx.attributes.reset()
        ctx.move_to(10, 6)
        ctx.attributes.style = REVERSE
        ctx.print("REVERSE")
        ctx.move_to(10, 7)
        ctx.attributes.style = UNDERLINE
        ctx.print("UNDERLINE")
        ctx.move_to(10, 8)
        ctx.attributes.style = UNDERLINE | REVERSE
        ctx.print("BOTH")


def main():
    display = get_display()
    display.run(DemoApp())


if __name__ == "__main__":
    main()
