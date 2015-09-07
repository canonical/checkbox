# This file is part of Checkbox.
#
# Copyright 2012-2015 Canonical Ltd.
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

"""Guacamole ingredients specific to plainbox."""

import collections
import gettext
import sys
import textwrap
import traceback

from guacamole import Command
from guacamole.core import Ingredient
from guacamole.ingredients import ansi
from guacamole.ingredients import argparse
from guacamole.ingredients import cmdtree
from guacamole.recipes.cmd import CommandRecipe

from plainbox.impl.session.assistant import SessionAssistant

_ = gettext.gettext

box = collections.namedtuple("box", "top right bottom left")


class RenderingContext:

    """
    Context for stateful text display.

    The rendering context assists in displaying styled text by implementing a
    very simple box model and top-to-bottom paragraph flow.

    Particular attributes such as paragraph width, foreground and background
    color, text justification (alignment) and padding can be set and made to
    persist across calls.
    """

    def __init__(self, ansi):
        """
        Initialize the rendering context.

        :param ansi:
            The guacamole ANSIFormatter object. You want to extract it from
            ``ctx.ansi`` that is passed to the ``invoked()`` method of your
            ``gucamole.Command`` subclass.

        By default, text is entirely plain (without any style or color) and the
        terminal width is assumed to be exactly 80 columns. Padding around each
        paragraph is ``(0, 0, 0, 0)`` and each paragraph is left-aligned.
        """
        self.ansi = ansi
        self.reset()

    def reset(self):
        """Reset all rendering parameters to their default values."""
        self.width = 80
        self.bg = None
        self.fg = None
        self.bold = False
        self._padding = box(0, 0, 0, 0)
        self.align = 'left'

    @property
    def padding(self):
        """padding applied to each paragraph."""
        return self._padding

    @padding.setter
    def padding(self, value):
        """Set the padding to the desired values."""
        self._padding = box(*value)

    def para(self, text):
        """
        Display a paragraph.

        The paragraph is re-formatted to match the current rendering mode
        (width, and padding). Top and bottom padding is used to draw empty
        lines. Left and right padding is used to emulate empty columns around
        each content column.
        """
        content_width = self.width - (self.padding.left + self.padding.right)
        if isinstance(text, str):
            chunks = textwrap.wrap(text, content_width, break_long_words=True)
        elif isinstance(text, list):
            chunks = text
        else:
            raise TypeError('text must be either str or list of str')
        empty_line = ' ' * self.width
        pad_left = ' ' * self.padding.left
        pad_right = ' ' * self.padding.right
        for i in range(self.padding.top):
            print(self.ansi(empty_line, fg=self.fg, bg=self.bg))
        for chunk in chunks:
            for line in chunk.splitlines():
                if self.align == 'left':
                    line = line.ljust(content_width)
                elif self.align == 'right':
                    line = line.rjust(content_width)
                elif self.align == 'center':
                    line = line.center(content_width)
                print(self.ansi(
                    pad_left + line + pad_right,
                    fg=self.fg, bg=self.bg, bold=self.bold))
        for i in range(self.padding.bottom):
            print(self.ansi(empty_line, fg=self.fg, bg=self.bg))


class RenderingContextIngredient(Ingredient):

    """Ingredient that adds a RenderingContext to guacamole."""

    def late_init(self, context):
        """Add a RenderingContext as ``rc`` to the guacamole context."""
        context.rc = RenderingContext(context.ansi)


class SessionAssistantIngredient(Ingredient):

    """Ingredient that adds a SessionAssistant to guacamole."""

    def late_init(self, context):
        """Add a SessionAssistant as ``sa`` to the guacamole context."""
        context.sa = SessionAssistant(context.cmd_toplevel.get_app_id())


class CanonicalCrashIngredient(Ingredient):

    """Ingredient for handing crashes in a Canonical-theme way."""

    def dispatch_failed(self, context):
        """Print the unhanded exception and exit the application."""
        rc = context.rc
        rc.reset()
        rc.bg = 'red'
        rc.fg = 'bright_white'
        rc.bold = 1
        rc.align = 'center'
        rc.padding = (1, 1, 1, 1)
        rc.para(_("Application Malfunction Detected"))
        rc.align = 'left'
        rc.bold = 0
        rc.padding = (0, 0, 0, 0)
        exc_type, exc_value, tb = sys.exc_info()
        rc.para(traceback.format_exception(exc_type, exc_value, tb))
        rc.padding = (2, 2, 0, 2)
        rc.para(_(
            "Please report a bug including the information from the "
            "paragraph above. To report the bug visit {0}"
        ).format(context.cmd_toplevel.bug_report_url))
        rc.padding = (1, 2, 1, 2)
        rc.para(_("We are sorry for the inconvenience!"))
        raise SystemExit(1)


class CanonicalCommandRecipe(CommandRecipe):

    """A recipe for using Canonical-enhanced commands."""

    def get_ingredients(self):
        """Get a list of ingredients for guacamole."""
        return [
            cmdtree.CommandTreeBuilder(self.command),
            cmdtree.CommandTreeDispatcher(),
            argparse.ParserIngredient(),
            CanonicalCrashIngredient(),
            ansi.ANSIIngredient(),
            RenderingContextIngredient(),
            SessionAssistantIngredient(),
        ]


class CanonicalCommand(Command):

    """
    A command with Canonical-enhanced ingredients.

    This command has two additional items in the guacamole execution context,
    the :class:`RenderingContext` object ``rc`` and the
    :class:`SessionAssistant` object ``sa``.
    """

    bug_report_url = "https://bugs.launchpad.net/checkbox/+filebug"

    def main(self, argv=None, exit=True):
        """
        Shortcut for running a command.

        See :meth:`guacamole.recipes.Recipe.main()` for details.
        """
        return CanonicalCommandRecipe(self).main(argv, exit)
