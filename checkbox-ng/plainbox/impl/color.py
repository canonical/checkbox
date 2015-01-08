# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
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
:mod:`plainbox.impl.color` -- ANSI color codes
==============================================
"""
import sys


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


# XXX: Temporary hack that disables colors on win32 until
# all of the codebase has been ported over to use colorama
if sys.platform == 'win32':
    try:
        import colorama
    except ImportError:
        ansi_on = ansi_off
    else:
        colorama.init()


def get_color_for_tty(stream=None):
    """
    Get ``ansi_on`` if stdout is a tty, ``ansi_off`` otherwise.

    :param stream:
        Alternate stream to use (sys.stdout by default)
    :returns:
        ``ansi_on`` or ``ansi_off``, depending on if the stream being a tty or
        not.
    """
    if stream is None:
        stream = sys.stdout
    return ansi_on if stream.isatty() else ansi_off


class Colorizer:
    """
    Colorizing helper for various kinds of content we need to handle
    """

    # NOTE: Ideally result and all would be handled by multi-dispatch __call__

    def __init__(self, color=None):
        if color is True:
            self.c = ansi_on
        elif color is False:
            self.c = ansi_off
        elif color is None:
            self.c = get_color_for_tty()
        else:
            self.c = color

    @property
    def is_enabled(self):
        """
        if true, this colorizer is actually using colors

        This property is useful to let applications customize their
        behavior if they know color support is desired and enabled.
        """
        return self.c is ansi_on

    def result(self, result):
        return self.custom(
            result.tr_outcome(), result.outcome_color_ansi())

    def header(self, text, color_name='WHITE', bright=True, fill='='):
        return self("[ {} ]".format(text).center(80, fill), color_name, bright)

    def f(self, color_name):
        return getattr(self.c.f, color_name.upper())

    def b(self, color_name):
        return getattr(self.c.b, color_name.upper())

    def s(self, style_name):
        return getattr(self.c.s, style_name.upper())

    def __call__(self, text, color_name="WHITE", bright=True):
        return ''.join([
            self.f(color_name),
            self.c.s.BRIGHT if bright else '', str(text),
            self.c.s.RESET_ALL])

    def custom(self, text, ansi_code):
        """
        Render a piece of text with custom ANSI styling sequence

        :param text:
            The text to stylize
        :param ansi_code:
            A string containing ANSI escape sequence to use.
        :returns:
            A combination of ``ansi_code``, ``text`` and a fixed
            reset sequence that resets text styles.

        .. note::
            When the colorizer is not really doing anything (see
            :meth:`is_enabled`) then custom text is not used at all.  This is
            done to ensure that any custom styling is not permantently enabled
            if colors are to be disabled.
        """
        return ''.join([
            ansi_code if self.is_enabled else "",
            text,
            self.c.s.RESET_ALL])

    def BLACK(self, text, bright=True):
        return self(text, "BLACK", bright)

    def RED(self, text, bright=True):
        return self(text, "RED", bright)

    def GREEN(self, text, bright=True):
        return self(text, "GREEN", bright)

    def YELLOW(self, text, bright=True):
        return self(text, "YELLOW", bright)

    def BLUE(self, text, bright=True):
        return self(text, "BLUE", bright)

    def MAGENTA(self, text, bright=True):
        return self(text, "MAGENTA", bright)

    def CYAN(self, text, bright=True):
        return self(text, "CYAN", bright)

    def WHITE(self, text, bright=True):
        return self(text, "WHITE", bright)
