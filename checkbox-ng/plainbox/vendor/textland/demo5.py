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

    def repaint(self, event: Event):
        ctx = DrawingContext(self.image)
        ctx.border()


def main():
    display = get_display()
    display.run(DemoApp())


if __name__ == "__main__":
    main()
