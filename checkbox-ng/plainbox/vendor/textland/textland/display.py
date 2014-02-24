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

from abc import abstractmethod
from collections import deque
from copy import deepcopy
from os import getenv

from . import keys
from .abc import IApplication
from .abc import IDisplay
from .bits import Size
from .events import EVENT_KEYBOARD, EVENT_RESIZE
from .events import Event, KeyboardData
from .image import BLACK
from .image import REVERSE
from .image import TextAttributes
from .image import TextImage
from .image import UNDERLINE
from .image import WHITE


class AbstractDisplay(IDisplay):
    """
    Abstract display class.
    """

    def run(self, app: IApplication) -> None:
        """
        Run forever, feeding events to the controller
        the controller can raise StopIteration to "quit"
        """
        # Tell the app abount the initial size
        size = self.get_display_size()
        try:
            image = app.consume_event(Event(EVENT_RESIZE, size))
            self.display_image(image)
        except StopIteration:
            return
        # Then keep on running until the app raises StopIteration
        while True:
            try:
                # XXX: TestDisplay.wait_for_event() can raise StopIteration
                # but this is a hack that is not really applicable for curses
                event = self.wait_for_event()
                image = app.consume_event(event)
            except StopIteration as exc:
                if exc.args:
                    return exc.args[0]
                else:
                    break
            else:
                self.display_image(image)

    @abstractmethod
    def display_image(self, image: TextImage) -> None:
        """
        Display the contents of the image on the screen
        """

    @abstractmethod
    def get_display_size(self) -> Size:
        """
        Get the current size of the display
        """

    @abstractmethod
    def wait_for_event(self) -> Event:
        """
        Get the next event, waiting for it to occur
        """


class PrintDisplay(AbstractDisplay):
    """
    A display that uses regular print() and input()
    """

    def __init__(self, size=Size(80, 25)):
        self.screen = TextImage(size)

    def display_image(self, image: TextImage) -> None:
        text_buffer = image.text_buffer
        width = self.screen.size.width
        height = self.screen.size.height
        print("/{}\\".format('=' * width))
        for y in range(height):
            line = text_buffer[y * width: (y + 1) * width].tounicode()
            print("|{}|".format(line))
        print("\\{}/".format('=' * width))

    def get_display_size(self) -> Size:
        return self.screen.size

    _commands = {
        'up': Event(EVENT_KEYBOARD, KeyboardData(keys.KEY_UP)),
        'down': Event(EVENT_KEYBOARD, KeyboardData(keys.KEY_DOWN)),
        'left': Event(EVENT_KEYBOARD, KeyboardData(keys.KEY_LEFT)),
        'right': Event(EVENT_KEYBOARD, KeyboardData(keys.KEY_RIGHT)),
        '': Event(EVENT_KEYBOARD, KeyboardData(keys.KEY_ENTER)),
    }

    def wait_for_event(self) -> Event:
        while True:
            text = input("TextLand> ")
            try:
                return self._commands[text]
            except KeyError:
                if len(text) == 1:
                    return Event(EVENT_KEYBOARD, KeyboardData(text[0]))
                else:
                    print("Type command name or exactly one letter")


class CursesDisplay(AbstractDisplay):
    """
    A display using python curses module
    """

    def __init__(self):
        import curses
        self._curses = curses
        self._screen = None
        self._curses_attr = [0] * 0xffff

    def _pa_to_curses(self, pa: int) -> int:
        """
        Translate cell attributes into supported curses attributes

        Bright mode is well explained in the ncurses FAQ (see: The standard
        and VT100 documentation refer to "Bold".):
        http://invisible-island.net/ncurses/ncurses.faq.html#problems_coloring

        Check urwid documentation for general terminal supports:
        http://urwid.org/manual/displayattributes.html#foreground-and-background-settings

        As curses only supports A_BOLD, bright backgrounds are not supported.
        Only ANSI escape codes ANSI supports backgound intensity, see:
        http://en.wikipedia.org/wiki/ANSI_escape_code

        Urwid documentation explains why bright background are bad:
        "Terminal support for bright background colors is spotty, and they
        generally should be avoided. If you are in a high-color mode you
        might have better luck using the high-color versions", see:
        http://urwid.org/manual/displayattributes.html#bright-background-colors
        """
        fg, bg, style = TextAttributes.unpack(pa)
        curses_attr = 0
        if style == 0:
            curses_attr = self._curses.A_NORMAL
        if style & REVERSE:
            curses_attr |= self._curses.A_REVERSE
        if style & UNDERLINE:
            curses_attr |= self._curses.A_UNDERLINE
        if fg > 7:
            curses_attr |= self._curses.A_BOLD  # Bright foreground colors
            fg -= 8
        if bg > 7:
            bg -= 8  # Bright backgrounds are not supported
        curses_attr |= self._curses.color_pair(self._pair_index(fg, bg))
        return curses_attr

    def _pair_index(self, fg: int, bg: int) -> int:
        # XXX: Support the default colors (-1)
        #return (bg + 2) * 9 - fg - 2
        return bg * 8 + 7 - fg

    def run(self, app: IApplication) -> None:
        try:
            self._init_curses()
            return super().run(app)
        finally:
            self._fini_curses()

    def _init_curses(self):
        self._screen = self._curses.initscr()
        if self._curses.has_colors():
            try:
                self._curses.start_color()
                self._setup_color_pairs()
            except self._curses.error:
                pass
        self._curses.noecho()
        self._curses.cbreak()
        self._screen.keypad(1)

    def _setup_color_pairs(self):
        """
        Initialize all the color pairs based on the _pair_index() formula.
        To select the right color combination, we just need to use the right
        color pair number.
        """
        # XXX: hardcode 8, since curses.COLORS could be larger than the
        # portable set of 64 color pairs
        for fg in range(8):
            for bg in range(8):
                if fg == WHITE and bg == BLACK:
                    continue
                self._curses.init_pair(self._pair_index(fg, bg), fg, bg)
        self._curses_attr = [self._pa_to_curses(i) for i in range(0xffff)]

    def _fini_curses(self):
        if self._screen is not None:
            self._screen.keypad(0)
        self._curses.echo()
        self._curses.nocbreak()
        self._curses.endwin()

    def display_image(self, image: TextImage) -> None:
        width = image.size.width
        height = image.size.height
        for y in range(height - 1):
            for x in range(width):
                cell = image.get(x, y)
                self._screen.addstr(
                    y, x, cell.char, self._curses_attr[cell.attributes])
        y += 1
        for x in range(1, width):
            cell = image.get(x, y)
            self._screen.addstr(
                y, x - 1, cell.char, self._curses_attr[cell.attributes])
        cell = image.get(0, y)
        self._screen.insstr(
            y, 0, cell.char, self._curses_attr[cell.attributes])
        self._screen.refresh()

    def get_display_size(self) -> Size:
        y, x = self._screen.getmaxyx()
        return Size(x, y)

    def wait_for_event(self) -> Event:
        key_code = self._screen.getch()
        # XXX -1 is for OSX
        if key_code == self._curses.KEY_RESIZE or key_code == -1:
            return Event(EVENT_RESIZE, self.get_display_size())
        elif key_code == self._curses.KEY_UP:
            return Event(EVENT_KEYBOARD, KeyboardData(keys.KEY_UP))
        elif key_code == self._curses.KEY_DOWN:
            return Event(EVENT_KEYBOARD, KeyboardData(keys.KEY_DOWN))
        elif key_code == self._curses.KEY_LEFT:
            return Event(EVENT_KEYBOARD, KeyboardData(keys.KEY_LEFT))
        elif key_code == self._curses.KEY_RIGHT:
            return Event(EVENT_KEYBOARD, KeyboardData(keys.KEY_RIGHT))
        elif key_code == ord(' '):
            return Event(EVENT_KEYBOARD, KeyboardData(keys.KEY_SPACE))
        elif key_code == ord('\n'):
            return Event(EVENT_KEYBOARD, KeyboardData(keys.KEY_ENTER))
        else:
            return Event(EVENT_KEYBOARD, KeyboardData(chr(key_code)))


class TestDisplay(AbstractDisplay):
    """
    A display that records all images and replays pre-recorded events
    """

    def __init__(self, size=Size(80, 25)):
        self.screen_log = []
        self.size = size
        self.events = deque()

    def display_image(self, image: TextImage) -> None:
        self.screen_log.append(deepcopy(image))

    def get_display_size(self) -> Size:
        return self.size

    def wait_for_event(self) -> Event:
        try:
            return self.events.popleft()
        except IndexError:
            raise StopIteration

    def inject_event(self, event: Event) -> None:
        """
        Inject an event.

        Events are served in FIFO mode.
        """
        self.events.append(event)


def get_display(display=None) -> IDisplay:
    """
    Get a ITextDisplay according to TEXTLAND_DISPLAY environment variable
    """
    if display is None:
        display = getenv("TEXTLAND_DISPLAY", "curses")
    if display == "curses":
        try:
            return CursesDisplay()
        except ImportError:
            # Sized like that to fit 80x25 without any overflow
            return PrintDisplay(Size(77, 22))
    elif display == "print":
        return PrintDisplay()
    elif display == "test":
        return TestDisplay()
    else:
        raise ValueError("Unsupported TEXTLAND_DISPLAY type")
