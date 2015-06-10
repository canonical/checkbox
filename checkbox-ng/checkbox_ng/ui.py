# This file is part of Checkbox.
#
# Copyright 2013-2015 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
:mod:`checkbox_ng.ui` -- user interface elements
================================================
"""

from gettext import gettext as _
from logging import getLogger
import textwrap

from plainbox.vendor.textland import DrawingContext
from plainbox.vendor.textland import EVENT_KEYBOARD
from plainbox.vendor.textland import EVENT_RESIZE
from plainbox.vendor.textland import Event
from plainbox.vendor.textland import IApplication
from plainbox.vendor.textland import Size
from plainbox.vendor.textland import TextImage
from plainbox.vendor.textland import NORMAL, REVERSE


logger = getLogger("checkbox.ng.ui")


class ShowWelcome(IApplication):
    """
    Display a welcome message
    """
    def __init__(self, text):
        self.image = TextImage(Size(0, 0))
        self.text = text

    def consume_event(self, event: Event):
        if event.kind == EVENT_RESIZE:
            self.image = TextImage(event.data)  # data is the new size
        elif event.kind == EVENT_KEYBOARD and event.data.key == "enter":
            raise StopIteration
        self.repaint(event)
        return self.image

    def repaint(self, event: Event):
        ctx = DrawingContext(self.image)
        i = 0
        ctx.border()
        for paragraph in self.text.splitlines():
            i += 1
            for line in textwrap.fill(
                    paragraph,
                    self.image.size.width - 8,
                    replace_whitespace=False).splitlines():
                ctx.move_to(4, i)
                ctx.print(line)
                i += 1
        ctx.move_to(4, i + 1)
        ctx.attributes.style = REVERSE
        ctx.print(_("< Continue >"))


class ShowMenu(IApplication):
    """
    Display the appropriate menu and return the selected options
    """
    def __init__(self, title, menu, selection=[0]):
        self.image = TextImage(Size(0, 0))
        self.title = title
        self.menu = menu
        self.option_count = len(menu)
        self.position = 0  # Zero-based index of the selected menu option
        if self.option_count:
            self.selection = selection
        else:
            self.selection = []

    def consume_event(self, event: Event):
        if event.kind == EVENT_RESIZE:
            self.image = TextImage(event.data)  # data is the new size
        elif event.kind == EVENT_KEYBOARD:
            if event.data.key == "down":
                if self.position < self.option_count:
                    self.position += 1
                else:
                    self.position = 0
            elif event.data.key == "up":
                if self.position > 0:
                    self.position -= 1
                else:
                    self.position = self.option_count
            elif (event.data.key == "enter" and
                  self.position == self.option_count):
                raise StopIteration(self.selection)
            elif event.data.key == "space":
                if self.position in self.selection:
                    self.selection.remove(self.position)
                elif self.position < self.option_count:
                    self.selection.append(self.position)
        self.repaint(event)
        return self.image

    def repaint(self, event: Event):
        ctx = DrawingContext(self.image)
        ctx.border(tm=1)
        ctx.attributes.style = REVERSE
        ctx.print(' ' * self.image.size.width)
        ctx.move_to(1, 0)
        ctx.print(self.title)

        # Display all the menu items
        for i in range(self.option_count):
            ctx.attributes.style = NORMAL
            if i == self.position:
                ctx.attributes.style = REVERSE
            # Display options from line 3, column 4
            ctx.move_to(4, 3 + i)
            ctx.print("[{}] - {}".format(
                'X' if i in self.selection else ' ',
                self.menu[i].replace('ihv-', '').capitalize()))

        # Display "OK" at bottom of menu
        ctx.attributes.style = NORMAL
        if self.position == self.option_count:
            ctx.attributes.style = REVERSE
        # Add an empty line before the last option
        ctx.move_to(4, 4 + self.option_count)
        ctx.print("< OK >")


class ScrollableTreeNode(IApplication):
    """
    Class used to interact with a SelectableJobTreeNode
    """
    def __init__(self, tree, title):
        self.image = TextImage(Size(0, 0))
        self.tree = tree
        self.title = title
        self.top = 0  # Top line number
        self.highlight = 0  # Highlighted line number

    def consume_event(self, event: Event):
        if event.kind == EVENT_RESIZE:
            self.image = TextImage(event.data)  # data is the new size
        elif event.kind == EVENT_KEYBOARD:
            self.image = TextImage(self.image.size)
            if event.data.key == "up":
                self._scroll("up")
            elif event.data.key == "down":
                self._scroll("down")
            elif event.data.key == "space":
                self._selectNode()
            elif event.data.key == "enter":
                self._toggleNode()
            elif event.data.key in 'sS':
                self.tree.set_descendants_state(True)
            elif event.data.key in 'dD':
                self.tree.set_descendants_state(False)
            elif event.data.key in 'tT':
                raise StopIteration
        self.repaint(event)
        return self.image

    def repaint(self, event: Event):
        ctx = DrawingContext(self.image)
        ctx.border(tm=1, bm=1)
        cols = self.image.size.width
        extra_cols = 0
        if cols > 80:
            extra_cols = cols - 80
        ctx.attributes.style = REVERSE
        ctx.print(' ' * cols)
        ctx.move_to(1, 0)
        bottom = self.top + self.image.size.height - 4
        ctx.print(self.title)
        ctx.move_to(1, self.image.size.height - 1)
        ctx.attributes.style = REVERSE
        ctx.print(_("Enter"))
        ctx.move_to(6, self.image.size.height - 1)
        ctx.attributes.style = NORMAL
        ctx.print(_(": Expand/Collapse"))
        ctx.move_to(27, self.image.size.height - 1)
        ctx.attributes.style = REVERSE
        # FIXME: i18n problem
        ctx.print("S")
        ctx.move_to(28, self.image.size.height - 1)
        ctx.attributes.style = NORMAL
        ctx.print("elect All")
        ctx.move_to(41, self.image.size.height - 1)
        ctx.attributes.style = REVERSE
        # FIXME: i18n problem
        ctx.print("D")
        ctx.move_to(42, self.image.size.height - 1)
        ctx.attributes.style = NORMAL
        ctx.print("eselect All")
        ctx.move_to(66 + extra_cols, self.image.size.height - 1)
        ctx.print(_("Start "))
        ctx.move_to(72 + extra_cols, self.image.size.height - 1)
        ctx.attributes.style = REVERSE
        # FIXME: i18n problem
        ctx.print("T")
        ctx.move_to(73 + extra_cols, self.image.size.height - 1)
        ctx.attributes.style = NORMAL
        ctx.print("esting")
        for i, line in enumerate(self.tree.render(cols - 3)[self.top:bottom]):
            ctx.move_to(2, i + 2)
            if i != self.highlight:
                ctx.attributes.style = NORMAL
            else:  # highlight the current line
                ctx.attributes.style = REVERSE
            ctx.print(line)

    def _selectNode(self):
        """
        Mark a node/job as selected for this test run.
        See :meth:`SelectableJobTreeNode.set_ancestors_state()` and
        :meth:`SelectableJobTreeNode.set_descendants_state()` for details
        about the automatic selection of parents and descendants.
        """
        node, category = self.tree.get_node_by_index(self.top + self.highlight)
        if category:  # then the selected node is a job not a category
            job = node
            category.job_selection[job] = not(category.job_selection[job])
            category.update_selected_state()
            category.set_ancestors_state(category.job_selection[job])
        else:
            node.selected = not(node.selected)
            node.set_descendants_state(node.selected)
            node.set_ancestors_state(node.selected)

    def _toggleNode(self):
        """
        Expand/collapse a node
        """
        node, is_job = self.tree.get_node_by_index(self.top + self.highlight)
        if node is not None and not is_job:
            node.expanded = not(node.expanded)

    def _scroll(self, direction):
        visible_length = len(self.tree.render())
        # Scroll the tree view
        if (direction == "up" and
                self.highlight == 0 and self.top != 0):
            self.top -= 1
            return
        elif (direction == "down" and
                (self.highlight + 1) == (self.image.size.height - 4) and
                (self.top + self.image.size.height - 4) != visible_length):
            self.top += 1
            return
        # Move the highlighted line
        if (direction == "up" and
                (self.top != 0 or self.highlight != 0)):
            self.highlight -= 1
        elif (direction == "down" and
                (self.top + self.highlight + 1) != visible_length and
                (self.highlight + 1) != (self.image.size.height - 4)):
            self.highlight += 1


class ShowRerun(ScrollableTreeNode):
    """ Display the re-run screen."""
    def __init__(self, tree, title):
        super().__init__(tree, title)

    def consume_event(self, event: Event):
        if event.kind == EVENT_RESIZE:
            self.image = TextImage(event.data)  # data is the new size
        elif event.kind == EVENT_KEYBOARD:
            self.image = TextImage(self.image.size)
            if event.data.key == "up":
                self._scroll("up")
            elif event.data.key == "down":
                self._scroll("down")
            elif event.data.key == "space":
                self._selectNode()
            elif event.data.key == "enter":
                self._toggleNode()
            elif event.data.key in 'sS':
                self.tree.set_descendants_state(True)
            elif event.data.key in 'dD':
                self.tree.set_descendants_state(False)
            elif event.data.key in 'fF':
                self.tree.set_descendants_state(False)
                raise StopIteration
            elif event.data.key in 'rR':
                raise StopIteration
        self.repaint(event)
        return self.image

    def repaint(self, event: Event):
        ctx = DrawingContext(self.image)
        ctx.border(tm=1, bm=1)
        cols = self.image.size.width
        extra_cols = 0
        if cols > 80:
            extra_cols = cols - 80
        ctx.attributes.style = REVERSE
        ctx.print(' ' * cols)
        ctx.move_to(1, 0)
        bottom = self.top + self.image.size.height - 4
        ctx.print(self.title)
        ctx.move_to(1, self.image.size.height - 1)
        ctx.attributes.style = REVERSE
        ctx.print(_("Enter"))
        ctx.move_to(6, self.image.size.height - 1)
        ctx.attributes.style = NORMAL
        ctx.print(_(": Expand/Collapse"))
        ctx.move_to(27, self.image.size.height - 1)
        ctx.attributes.style = REVERSE
        # FIXME: i18n problem
        ctx.print("S")
        ctx.move_to(28, self.image.size.height - 1)
        ctx.attributes.style = NORMAL
        ctx.print("elect All")
        ctx.move_to(41, self.image.size.height - 1)
        ctx.attributes.style = REVERSE
        # FIXME: i18n problem
        ctx.print("D")
        ctx.move_to(42, self.image.size.height - 1)
        ctx.attributes.style = NORMAL
        ctx.print("eselect All")
        ctx.move_to(63 + extra_cols, self.image.size.height - 1)
        ctx.attributes.style = REVERSE
        # FIXME: i18n problem
        ctx.print("F")
        ctx.move_to(64 + extra_cols, self.image.size.height - 1)
        ctx.attributes.style = NORMAL
        ctx.print(_("inish"))
        ctx.move_to(73 + extra_cols, self.image.size.height - 1)
        ctx.attributes.style = REVERSE
        # FIXME: i18n problem
        ctx.print("R")
        ctx.move_to(74 + extra_cols, self.image.size.height - 1)
        ctx.attributes.style = NORMAL
        ctx.print("e-run")
        for i, line in enumerate(self.tree.render(cols - 3)[self.top:bottom]):
            ctx.move_to(2, i + 2)
            if i != self.highlight:
                ctx.attributes.style = NORMAL
            else:  # highlight the current line
                ctx.attributes.style = REVERSE
            ctx.print(line)
