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
import argparse

from textland import DrawingContext
from textland import EVENT_KEYBOARD
from textland import EVENT_RESIZE
from textland import Event
from textland import IApplication
from textland import KeyboardData
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
        # Draw something on the image
        ctx = DrawingContext(self.image)
        ctx.fill('.')
        title = "TextLand Demo Application"
        ctx.move_to((self.image.size.width - len(title)) // 2, 0)
        ctx.print(title)
        ctx.print('=' * len(title))
        ctx.move_to(0, 3)
        ctx.print("Type 'q' to quit")
        ctx.move_to(10, 10)
        ctx.print("Event: {}".format(event))


def main():
    parser = argparse.ArgumentParser()
    parser.set_defaults(display=None)
    parser.add_argument(
        '--curses',
        help="Use curses for display",
        action="store_const",
        const="curses",
        dest="display")
    parser.add_argument(
        '--print',
        help="Use simple line printer for display",
        action="store_const",
        const="print",
        dest="display")
    parser.add_argument(
        "--test",
        help="Use test display (just for testing)",
        action="store_const",
        const="test",
        dest="display")
    ns = parser.parse_args()
    display = get_display(ns.display)
    if ns.display == 'test':
        display.inject_event(Event(EVENT_KEYBOARD, KeyboardData('x')))
        display.inject_event(Event(EVENT_KEYBOARD, KeyboardData('y')))
        display.inject_event(Event(EVENT_KEYBOARD, KeyboardData('q')))
    display.run(DemoApp())
    if ns.display == 'test':
        for frame, image in enumerate(display.screen_log, 1):
            print("Frame {}:".format(frame))
            image.print_frame()


if __name__ == "__main__":
    main()
