# This file is part of Checkbox.
#
# Copyright 2017 Canonical Ltd.
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
:mod:`checkbox_ng.urwid_ui` -- user interface URWID elements
============================================================
"""

import os
import time

from gettext import gettext as _
import urwid.raw_display
import urwid

from plainbox.abc import IJobResult


_widget_cache = {}
test_info_list = ()
show_job_ids = False


class ASCIIScreen(urwid.raw_display.Screen):
    def draw_screen(self, size, r):
        _trans_table = "?" * 32 + "".join([chr(x) for x in range(32, 256)])
        line = []
        for row in r.content():
            for a, cs, run in row:
                line.append(run.decode().translate(_trans_table))
            line.append("\n")
        print("".join(line))

    def get_cols_rows(self):
        return 80, 24


if os.getenv("DISABLE_URWID_ESCAPE_CODES"):
    Screen = ASCIIScreen
else:
    Screen = urwid.raw_display.Screen


class FlagUnitWidget(urwid.TreeWidget):
    # apply an attribute to the expand/unexpand icons
    unexpanded_icon = urwid.AttrMap(
        urwid.TreeWidget.unexpanded_icon, 'dirmark')
    expanded_icon = urwid.AttrMap(
        urwid.TreeWidget.expanded_icon, 'dirmark')
    selected = urwid.Text(u'[X]')
    unselected = urwid.Text(u'[ ]')

    def __init__(self, node):
        self.flagged = True
        super().__init__(node)
        # insert an extra AttrWrap for our own use
        self._w = urwid.AttrWrap(self._w, None)
        self.update_w()

    def selectable(self):
        return True

    def get_indent_cols(self):
        depth = self.get_node().get_depth()
        if depth > 1:
            return self.indent_cols * (self.get_node().get_depth() - 1)
        else:
            return 1

    def get_indented_widget(self):
        indent_cols = self.get_indent_cols()
        widget = self.get_inner_widget()
        if self.is_leaf:
            widget = urwid.Columns(
                [(3, [self.selected, self.unselected][self.flagged]),
                 urwid.Padding(widget,
                               width=('relative', 100),
                               left=indent_cols)],
                dividechars=1)
        else:
            widget = urwid.Columns(
                [(3, [self.selected, self.unselected][self.flagged]),
                 (indent_cols-1, urwid.Text(' ')),
                 (1, [self.unexpanded_icon,
                      self.expanded_icon][self.expanded]),
                 urwid.Padding(widget, width=('relative', 100))],
                dividechars=1)
        return widget

    def update_expanded_icon(self):
        """Update display widget text for parent widgets"""
        # icon is second element in columns indented widget
        self._w.base_widget.widget_list[2] = [
            self.unexpanded_icon, self.expanded_icon][self.expanded]

    def keypress(self, size, key):
        key = super().keypress(size, key)
        if key:
            key = self.unhandled_keys(size, key)
        return key

    def mouse_event(self, size, event, button, col, row, focus):
        if event != 'mouse press' or button != 1:
            return False
        expand_col = 4
        if self.get_node().get_depth() > 1:
            expand_col = self.get_indent_cols() + 4
        if not self.is_leaf and row == 0 and col == expand_col:
            self.expanded = not self.expanded
            self.update_expanded_icon()
            return True
        if row == 0 and col < 3:
            self.unhandled_keys(size, " ")
            return True
        return False

    def unhandled_keys(self, size, key):
        global show_job_ids, _widget_cache
        if key == " ":
            self.flagged = not self.flagged
            self.set_descendants_state(self.flagged)
            self.set_ancestors_state(self.flagged)
            self.update_w()
        elif not self.is_leaf and key == "enter":
            self.expanded = not self.expanded
            self.update_expanded_icon()
        elif key in ('i', 'I'):
            show_job_ids = not show_job_ids
            for w in _widget_cache.values():
                w._w.base_widget.widget_list[-1] = urwid.Padding(
                    w.load_inner_widget(),
                    width=('relative', 100),
                    left=w.get_indent_cols())
        elif key in ('s', 'S'):
            root_node_widget = self.get_node().get_root().get_widget()
            root_node_widget.flagged = True
            root_node_widget.update_w()
            root_node_widget.set_descendants_state(True)
        elif key in ('d', 'D'):
            root_node_widget = self.get_node().get_root().get_widget()
            root_node_widget.flagged = False
            root_node_widget.update_w()
            root_node_widget.set_descendants_state(False)
        else:
            return key

    def set_ancestors_state(self, new_state):
        """Set the selection state of all ancestors consistently."""
        parent = self.get_node().get_parent()
        # If child is set, then all ancestors must be set
        if self.flagged:
            while parent:
                parent_w = parent.get_widget()
                parent_w.flagged = new_state
                parent_w.update_w()
                parent = parent.get_parent()
        # If child is not set, then all ancestors mustn't be set
        # unless another child of the ancestor is set
        else:
            while parent:
                if any((parent.get_child_node(key).get_widget().flagged
                        for key in parent.get_child_keys())):
                    break
                parent_w = parent.get_widget()
                parent_w.flagged = new_state
                parent_w.update_w()
                parent = parent.get_parent()

    def set_descendants_state(self, new_state):
        """Set the selection state of all descendants recursively."""
        if self.is_leaf:
            return
        node = self.get_node()
        for key in node.get_child_keys():
            child_w = node.get_child_node(key).get_widget()
            child_w.flagged = new_state
            try:
                child_w.update_w()
            except AttributeError:
                break
            child_w.set_descendants_state(new_state)

    def update_w(self):
        """Update the attributes of self.widget based on self.flagged."""
        self._w.attr = 'body'
        self._w.focus_attr = 'focus'
        self._w.base_widget.widget_list[0] = [
            self.unselected, self.selected][self.flagged]


class JobTreeWidget(FlagUnitWidget):
    """Widget for individual files."""

    def __init__(self, node):
        super().__init__(node)
        add_widget(node.get_key(), self)

    def get_display_text(self):
        global show_job_ids
        if show_job_ids:
            return self.get_node().get_value()[0]
        else:
            return self.get_node().get_value()[1]


class CategoryWidget(FlagUnitWidget):
    """Widget for a category."""

    def __init__(self, node):
        super().__init__(node)
        self.expanded = False
        if node.get_depth() == 0:
            self.expanded = True
        self.update_expanded_icon()

    def get_display_text(self):
        node = self.get_node()
        if node.get_depth() == 0:
            return _("Categories")
        else:
            cat_names = dict()
            for test in test_info_list:
                cat_names[test["category_id"]] = test["category_name"]
            return cat_names[node.get_key()]


class JobNode(urwid.TreeNode):
    """Metadata storage for individual jobs"""

    def load_widget(self):
        return JobTreeWidget(self)


class CategoryNode(urwid.ParentNode):
    """Metadata storage for categories"""

    def load_widget(self):
        return CategoryWidget(self)

    def load_child_keys(self):
        if self.get_depth() == 0:
            cat_names = dict()
            for test in test_info_list:
                cat_names[test["category_id"]] = test["category_name"]
            return sorted(cat_names.keys(), key=lambda x: cat_names[x])
        else:
            return sorted([
                job['id'] for job in test_info_list
                if job['category_id'] == self.get_key()])

    def load_child_node(self, key):
        """Return either a CategoryNode or JobNode"""
        if self.get_depth() == 0:
            return CategoryNode(self.get_value(), parent=self,
                                key=key, depth=self.get_depth() + 1)
        else:
            value = next(
                (job['partial_id'], job['name']) for job in test_info_list
                if job["id"] == key)
            return JobNode(
                value, parent=self, key=key, depth=self.get_depth() + 1)


class CategoryWalker(urwid.TreeWalker):
    """ListWalker-compatible class for displaying CategoryWidgets."""

    def __init__(self, root_node):
        self.root_node = root_node
        self.focus = root_node.get_widget().next_inorder().get_node()

    def get_prev(self, start_from):
        widget = start_from.get_widget()
        target = widget.prev_inorder()
        if target is None or target is self.root_node.get_widget():
            return None, None
        else:
            return target, target.get_node()


class CategoryListBox(urwid.TreeListBox):
    """A ListBox with special handling for navigation and
    collapsing of CategoryWidgets"""

    def move_focus_to_parent(self, size):
        """Move focus to parent of widget in focus."""
        widget, pos = self.body.get_focus()
        parentpos = pos.get_parent()
        if parentpos is None or parentpos is pos.get_root():
            return
        middle, top, bottom = self.calculate_visible(size)
        row_offset, focus_widget, focus_pos, focus_rows, cursor = middle
        trim_top, fill_above = top
        for widget, pos, rows in fill_above:
            row_offset -= rows
            if pos == parentpos:
                self.change_focus(size, pos, row_offset)
                return
        self.change_focus(size, pos.get_parent())

    def focus_home(self, size):
        """Move focus to first category."""
        widget, pos = self.body.get_focus()
        rootnode = pos.get_root()
        self.change_focus(
            size, rootnode.get_widget().next_inorder().get_node())


class CategoryBrowser:
    palette = [
        ('body', 'light gray', 'black'),
        ('focus', 'black', 'light gray', 'standout'),
        ('head', 'black', 'light gray', 'standout'),
        ('foot', 'light gray', 'black'),
        ('title', 'white', 'black', 'bold'),
        ('dirmark', 'light gray', 'black', 'bold'),
        ('start', 'dark green,bold', 'black'),
        ('rerun', 'yellow,bold', 'black'),
    ]

    footer_text = [('Press ('), ('start', 'T'), (') to start Testing')]

    help_text = urwid.ListBox(urwid.SimpleListWalker([
        urwid.Text(('focus', " Keyboard Controls and Shortcuts "), 'center'),
        urwid.Divider(),
        urwid.Text("Expand/Collapse          Enter/+/-"),
        urwid.Text("Select/Deselect all      s/d"),
        urwid.Text("Select/Deselect          Space"),
        urwid.Text("Navigation               Up/Down"),
        urwid.Text("                         Home/End"),
        urwid.Text("                         PageUp/PageDown"),
        urwid.Text("Back to parent category  Left"),
        urwid.Text("Toggle job id/summary    i"),
        urwid.Text('Show job details         m'),
        urwid.Text("Exit (abandon session)   Ctrl+C")]))

    def __init__(self, title, tests):
        global test_info_list
        test_info_list = tests
        self.header = urwid.Padding(urwid.Text(title), left=1)
        root_node = CategoryNode(tests)
        root_node.get_widget().set_descendants_state(True)
        self.listbox = CategoryListBox(CategoryWalker(root_node))
        self.listbox.offset_rows = 1
        self.footer = urwid.Columns(
            [urwid.Padding(urwid.Text(self.footer_text), left=1),
             urwid.Text('(H) Help ', 'right')])
        self.view = urwid.Frame(
            urwid.AttrWrap(urwid.LineBox(self.listbox), 'body'),
            header=urwid.AttrWrap(self.header, 'head'),
            footer=urwid.AttrWrap(self.footer, 'foot'))
        help_w = urwid.AttrWrap(urwid.LineBox(self.help_text), 'body')
        self.help_view = urwid.Overlay(
            help_w, self.view,
            'center', ('relative', 80), 'middle', ('relative', 80))

    def run(self):
        """Run the urwid MainLoop."""
        self.loop = urwid.MainLoop(
            self.view, self.palette, unhandled_input=self.unhandled_input,
            handle_mouse=False, screen=Screen())
        self.loop.run()
        selection = []
        global test_info_list, _widget_cache
        for w in _widget_cache.values():
            if w.flagged:
                selection.append(w.get_node().get_key())
        _widget_cache = {}
        test_info_list = ()
        return frozenset(selection)

    def unhandled_input(self, key):
        if self.loop.widget == self.view:
            if key in ('t', 'T'):
                raise urwid.ExitMainLoop()
            elif key in ('h', 'H', '?', 'f1'):
                self.loop.widget = self.help_view
                return True
            elif key in ('m', 'M'):
                if self.listbox.focus is not None:
                    node = self.listbox.focus.get_node()
                    if isinstance(node, JobNode):
                        self.loop.widget = self._job_detail_view(node)
                        return True
        else:
            if key in ('h', 'H', '?', 'f1', 'esc', 'm', 'M'):
                self.loop.widget = self.view

    def _job_detail_view(self, node):
        job = None
        for test_info in test_info_list:
            if test_info["id"] == node.get_key():
                job = test_info
                break
        contents = [urwid.Text(('focus', ' Job Details '), 'center'),
                    urwid.Divider()]

        def add_section(title, body):
            contents.extend([urwid.Text(title), urwid.Text(body),
                             urwid.Divider()])
        add_section(_('Job Identifier:'), job["id"])
        add_section(_('Summary:'), job["name"])
        add_section(_('User input:'), job["automated"])
        add_section(_('Estimated duration:'), job["duration"])
        add_section(_('Description:'), job["description"])
        detail_text = urwid.ListBox(urwid.SimpleListWalker(contents))
        detail_w = urwid.AttrWrap(urwid.LineBox(detail_text), 'body')
        job_detail_view = urwid.Overlay(
            detail_w, self.view,
            'center', ('relative', 80), 'middle', ('relative', 80))
        return job_detail_view


class RerunWidget(CategoryWidget):
    """Widget for a rerun category."""
    section_names = {
        IJobResult.OUTCOME_FAIL: _("Failed Jobs"),
        IJobResult.OUTCOME_SKIP: _("Skipped Jobs"),
        IJobResult.OUTCOME_CRASH: _("Crashed Jobs"),
        IJobResult.OUTCOME_NOT_SUPPORTED: _("Jobs with failed dependencies"),
    }

    def __init__(self, node):
        super().__init__(node)
        self.expanded = True
        if node.get_depth() == 0:
            self.expanded = True
        self.update_expanded_icon()

    def get_display_text(self):
        node = self.get_node()
        if node.get_depth() == 0:
            return _("Categories")
        elif node.get_depth() == 1:
            return self.section_names[node.get_value()]
        else:
            return node.get_value()


class RerunNode(CategoryNode):
    """Metadata storage for rerun categories"""

    def load_widget(self):
        return RerunWidget(self)

    def load_child_keys(self):
        if self.get_depth() == 0:
            return sorted(set([job['outcome'] for job in test_info_list]))
        if self.get_depth() == 1:
            return sorted(set([job['category_name'] for job in test_info_list
                               if job['outcome'] == self.get_value()]))
        else:
            return sorted([
                job['id'] for job in test_info_list
                if job['category_name'] == self.get_key() and
                job['outcome'] == self.get_parent().get_key()])

    def load_child_node(self, key):
        """Return either a CategoryNode or JobNode"""
        if self.get_depth() == 0:
            return RerunNode(key, parent=self, key=key, depth=1)
        if self.get_depth() == 1:
            return RerunNode(key, parent=self, key=key, depth=2)
        else:
            value = next(
                (job['partial_id'], job['name']) for job in test_info_list
                if job["id"] == key)
            return JobNode(
                value, parent=self, key=key, depth=self.get_depth() + 1)


class ReRunBrowser(CategoryBrowser):
    footer_text = [('Press ('), ('rerun', 'R'), (') to Rerun selection, ('),
                   ('start', 'F'), (') to Finish')]

    def __init__(self, title, tests, rerun_candidates):
        global test_info_list
        test_info_list = tests
        self.header = urwid.Padding(urwid.Text(title), left=1)
        self.root_node = RerunNode(tests)
        root_node_widget = self.root_node.get_widget()
        root_node_widget.flagged = False
        root_node_widget.update_w()
        root_node_widget.set_descendants_state(False)
        self.listbox = CategoryListBox(CategoryWalker(self.root_node))
        self.listbox.offset_rows = 1
        self.footer = urwid.Columns(
            [urwid.Padding(urwid.Text(self.footer_text), left=1),
             urwid.Text('(H) Help ', 'right')])
        self.view = urwid.Frame(
            urwid.AttrWrap(urwid.LineBox(self.listbox), 'body'),
            header=urwid.AttrWrap(self.header, 'head'),
            footer=urwid.AttrWrap(self.footer, 'foot'))
        help_w = urwid.AttrWrap(urwid.LineBox(self.help_text), 'body')
        self.help_view = urwid.Overlay(
            help_w, self.view,
            'center', ('relative', 80), 'middle', ('relative', 80))

    def unhandled_input(self, key):
        if self.loop.widget == self.view:
            if key in ('r', 'R'):
                raise urwid.ExitMainLoop()
            elif key in ('f', 'F'):
                root_node_widget = self.root_node.get_widget()
                root_node_widget.flagged = False
                root_node_widget.update_w()
                root_node_widget.set_descendants_state(False)
                raise urwid.ExitMainLoop()
            elif key in ('h', 'H', '?', 'f1'):
                self.loop.widget = self.help_view
                return True
            elif key in ('m', 'M'):
                if self.listbox.focus is not None:
                    node = self.listbox.focus.get_node()
                    if isinstance(node, JobNode):
                        self.loop.widget = self._job_detail_view(node)
                        return True
        else:
            if key in ('h', 'H', '?', 'f1', 'esc', 'm', 'M'):
                self.loop.widget = self.view


class TestPlanButton(urwid.RadioButton):

    def __init__(self, tp_info, group):
        self._tp_info = tp_info
        self.is_name = True
        super(TestPlanButton, self).__init__(
            group, self._tp_info.get('name'), state=False)

    def label_toggle(self):
        if self.is_name:
            self.set_label(self._tp_info.get('id'))
            self.is_name = False
        else:
            self.set_label(self._tp_info.get('name'))
            self.is_name = True

    @property
    def tp_id(self):
        return self._tp_info.get('id')

    @property
    def name(self):
        return self._tp_info.get('name')


class TestPlanBrowser():

    palette = [
        ('focus', 'black', 'light gray', 'standout'),
        ('body', 'light gray', 'black', 'standout'),
        ('head', 'black', 'light gray', 'bold'),
        ('buttnf', 'black', 'light gray'),
        ('buttn', 'light gray', 'black', 'bold'),
        ('foot', 'light gray', 'black'),
        ('start', 'dark green,bold', 'black'),
    ]

    footer_text = [('Press '), ('start', '<Enter>'), (' to continue')]

    help_text = urwid.ListBox(urwid.SimpleListWalker([
        urwid.Text(('focus', " Keyboard Controls and Shortcuts "), 'center'),
        urwid.Divider(),
        urwid.Text("Select/Deselect                 Space"),
        urwid.Text("Navigation                      Up/Down"),
        urwid.Text("                                Home/End"),
        urwid.Text("                                PageUp/PageDown"),
        urwid.Text("Toggle test plan id/summary     i"),
        urwid.Text("Filter test plan list           f,s,/"),
        urwid.Text("Exit (abandon session)          Ctrl+C")]))

    def __init__(self, title, test_plan_list, selection=None):
        self.master_list = sorted(
            test_plan_list, key=lambda tp_info: tp_info.get('name'))
        # Header
        self.header = urwid.Padding(urwid.Text(title), left=1)
        # Body
        self.radio_button_group = []
        self.button_pile = None
        self._preselected_tp = selection
        self._update_button_pile(self.master_list)
        listbox_content = [
            urwid.Divider(),
            urwid.Padding(self.button_pile, left=4, right=3, min_width=13),
            urwid.Divider(),
        ]
        self.listbox = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
        # Footer
        self.default_footer = urwid.AttrWrap(urwid.Columns(
            [urwid.Padding(urwid.Text(self.footer_text), left=1),
             urwid.Text('(H) Help ', 'right')]), 'foot')
        self.filter_footer = urwid.AttrWrap(
            urwid.Edit("filter: "), 'foot')
        self.filtering = False
        # Main frame
        self.frame = urwid.Frame(
            urwid.AttrWrap(urwid.LineBox(self.listbox), 'body'),
            header=urwid.AttrWrap(self.header, 'head'),
            footer=self.default_footer)
        if self.frame._command_map["enter"]:
            del self.frame._command_map["enter"]
        # Pop up
        help_w = urwid.AttrWrap(urwid.LineBox(self.help_text), 'body')
        self.help_view = urwid.Overlay(
            help_w, self.frame,
            'center', ('relative', 80), 'middle', ('relative', 80))

    def _update_button_pile(self, tplist):
        if tplist:
            contents = [
                urwid.AttrWrap(TestPlanButton(tp, self.radio_button_group),
                               'buttn', 'buttnf')
                for tp in tplist]
            if self.button_pile is None:
                self.button_pile = urwid.Pile(contents)
            else:
                self.button_pile.widget_list[:] = contents
            if self._preselected_tp:
                for index, tp in enumerate(tplist):
                    if tp['id'] == self._preselected_tp:
                        self.radio_button_group[index].set_state(True)
                        break

    def unhandled_input(self, key):
        if self.loop.widget == self.frame:
            if self.filtering:
                if key == 'enter':
                    filter_str = self.filter_footer.get_edit_text()
                    self.radio_button_group = []
                    if filter_str == '':
                        self._update_button_pile(self.master_list)
                    else:
                        self._update_button_pile(
                            [x for x in self.master_list
                             if filter_str in x.get('name')])
                if key in ('esc', 'enter'):
                    self.frame.contents['footer'] = (self.default_footer, None)
                    self.frame.set_focus('body')
                    self.filtering = False
            else:
                if key == 'enter':
                    raise urwid.ExitMainLoop()
                elif key in ('i', 'I'):
                    for b in self.radio_button_group:
                        b.label_toggle()
                elif key in ('h', 'H', '?', 'f1'):
                    self.loop.widget = self.help_view
                    return True
                elif key in ('/', 's', 'S', 'f', 'F'):
                    self.frame.contents['footer'] = (self.filter_footer, None)
                    self.frame.set_focus('footer')
                    self.filtering = True
        else:
            if key in ('h', 'H', '?', 'f1', 'esc'):
                self.loop.widget = self.frame

    def run(self):
        self.loop = urwid.MainLoop(
            self.frame, self.palette, unhandled_input=self.unhandled_input,
            handle_mouse=False, screen=Screen())
        self.loop.run()
        try:
            return next(i.tp_id for i in self.radio_button_group if i.state)
        except StopIteration:
            return None


def interrupt_dialog(host):
    palette = [
        ('body', 'light gray', 'black', 'standout'),
        ('header', 'black', 'light gray', 'bold'),
        ('buttnf', 'black', 'light gray'),
        ('buttn', 'light gray', 'black', 'bold'),
        ('foot', 'light gray', 'black'),
        ('start', 'dark green,bold', 'black'),
    ]
    choices = [
        _("Cancel the interruption and resume the session (ESC)"),
        _("Kill test in progress and move on to next"),
        _("Disconnect the master (Same as CTRL+C)"),
        _("Stop the checkbox slave @{}".format(host)),
        _("Abandon the session on the slave @{}".format(host)),
    ]
    footer_text = [
        ('Press '), ('start', '<Enter>'), (' or '),
        ('start', '<ESC>'), (' to continue')]
    radio_button_group = []
    blank = urwid.Divider()
    listbox_content = [
        blank,
        urwid.Padding(urwid.Text(
            _('What do you want to interrupt?')), left=20),
        blank,
        urwid.Padding(urwid.Pile(
            [urwid.AttrWrap(urwid.RadioButton(
                radio_button_group,
                txt, state=False), 'buttn', 'buttnf')
                for txt in choices]),
            left=15, right=15, min_width=15),
        blank,
    ]
    radio_button_group[0].set_state(True)  # select cancel by default
    title = _("Interruption!")
    header = urwid.AttrWrap(urwid.Padding(urwid.Text(title), left=1), 'header')
    footer = urwid.AttrWrap(
        urwid.Padding(urwid.Text(footer_text), left=1), 'foot')
    listbox = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
    frame = urwid.Frame(urwid.AttrWrap(urwid.LineBox(listbox), 'body'),
                        header=header, footer=footer)
    if frame._command_map["enter"]:
        del frame._command_map["enter"]

    def unhandled(key):
        if key == "enter":
            raise urwid.ExitMainLoop()
        if key == "esc":
            radio_button_group[0].set_state(True)
            raise urwid.ExitMainLoop()

    urwid.MainLoop(frame, palette, unhandled_input=unhandled,
                   handle_mouse=False, screen=Screen()).run()
    try:
        index = next(
            radio_button_group.index(i) for i in radio_button_group if i.state)
        return ['cancel', 'kill-command', 'kill-controller',
                'kill-service', 'abandon'][index]
    except StopIteration:
        return None


class CountdownWidget(urwid.BigText):

    def __init__(self, duration):
        self._started = time.time()
        self._duration = duration
        self.set_text('{0:.1f}'.format(duration))
        self.font = urwid.HalfBlock6x5Font()
        super().__init__(self.get_text()[0], self.font)

    def update(self):
        remaining = self._duration + self._started - time.time()
        if remaining <= 0:
            remaining = 0
        text = '{0:.1f}'.format(remaining)
        self.set_text(text)
        print('\33]2;Auto resume remote session in %s\007' % text, end='')
        if remaining:
            return True
        else:
            raise urwid.ExitMainLoop


class ManifestNaturalEdit(urwid.IntEdit):

    def keypress(self, size, key):
        (maxcol,) = size
        return urwid.Edit.keypress(self, (maxcol,), key)

    def value(self):
        if self.edit_text:
            return int(self.edit_text)


class ManifestQuestion(urwid.WidgetWrap):

    def __init__(self, question):
        self.id = question['id']
        self._value = question['value']
        self._value_type = question['value_type']
        if self._value_type == 'bool':
            self.options = []
            yes = urwid.RadioButton(
                self.options, "Yes", state=False,
                on_state_change=self._set_bool_value)
            no = urwid.RadioButton(
                self.options, "No", state=False,
                on_state_change=self._set_bool_value)
            if question['value'] is not None:
                if question['value'] is True:
                    yes.set_state(True)
                else:
                    no.set_state(True)
            self.display_widget = urwid.Columns([
                urwid.Padding(urwid.Text(question['name']), left=2),
                urwid.GridFlow([yes, no], 7, 3, 1, align='left')
            ], dividechars=5)
            urwid.WidgetWrap.__init__(self, self.display_widget)
        elif self._value_type == 'natural':
            self._edit_widget = ManifestNaturalEdit(u"", self._value)
            self.display_widget = urwid.Columns([
                urwid.Padding(urwid.Text(question['name']), left=2),
                (8, urwid.Padding(urwid.Text("["), left=7)),
                self._edit_widget,
                (1, urwid.Text("]"))
            ])
            urwid.WidgetWrap.__init__(self, self.display_widget)

    def _set_bool_value(self, w, new_state, user_data=None):
        if w.label == 'Yes' and new_state:
            self._value = new_state
        elif w.label == 'No' and new_state:
            self._value = False

    @property
    def value(self):
        if self._value_type == 'bool':
            return self._value
        elif self._value_type == 'natural':
            return self._edit_widget.value()


class ManifestBrowser:
    palette = [
        ('body', 'light gray', 'black'),
        ('buttnf', 'black', 'light gray'),
        ('buttn', 'light gray', 'black', 'bold'),
        ('head', 'black', 'light gray', 'standout'),
        ('foot', 'light gray', 'black'),
        ('title', 'white', 'black', 'bold'),
        ('start', 'dark green,bold', 'black'),
        ('bold', 'bold', 'black'),
    ]

    footer_text = [('Press ('), ('start', 'T'), (') to start Testing')]
    footer_shortcuts = [('Shortcuts: '), ('bold', 'y'), ('/'), ('bold', 'n ')]

    def __init__(self, title, manifest):
        self.manifest = manifest
        self._manifest_out = {}
        self._widget_cache = []
        # Header
        self.header = urwid.Padding(urwid.Text(title), left=1)
        # Body
        content = []
        for prompt, questions in sorted(self.manifest.items()):
            content.append(urwid.Text(prompt))
            for q in sorted(questions, key=lambda i: i['name']):
                question_widget = ManifestQuestion(q)
                content.append(urwid.AttrWrap(question_widget,
                               'buttn', 'buttnf'))
                self._widget_cache.append(question_widget)
        self._pile = urwid.Pile(content)
        listbox_content = [
            urwid.Padding(self._pile, left=1, right=1, min_width=13),
        ]
        self.listbox = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
        # Footer
        self.default_footer = urwid.AttrWrap(urwid.Columns(
            [urwid.Padding(urwid.Text(self.footer_text), left=1),
             urwid.Text(self.footer_shortcuts, 'right')]), 'foot')
        # Main frame
        self.frame = urwid.Frame(
            urwid.AttrWrap(urwid.LineBox(self.listbox), 'body'),
            header=urwid.AttrWrap(self.header, 'head'),
            footer=self.default_footer)

    def run(self):
        """Run the urwid MainLoop."""
        self.loop = urwid.MainLoop(
            self.frame, self.palette, unhandled_input=self.unhandled_input,
            handle_mouse=False, screen=Screen())
        self.loop.run()
        for w in self._widget_cache:
            self._manifest_out.update({w.id: w.value})
        return self._manifest_out

    def unhandled_input(self, key):
        if key in ('t', 'T'):
            for w in self._widget_cache:
                if w.value is None:
                    break
            else:
                raise urwid.ExitMainLoop()
        if self._pile.focus._value_type == 'bool':
            if key in ('y', 'Y'):
                self.loop.process_input(["left", " ", "down"])
            elif key in ('n', 'N'):
                self.loop.process_input(["right", " ", "down"])
        elif self._pile.focus._value_type == 'natural':
            if key == 'enter':
                self.loop.process_input(["down"])


def resume_dialog(duration):
    palette = [
        ('body', 'light gray', 'black', 'standout'),
        ('header', 'black', 'light gray', 'bold'),
        ('buttnf', 'black', 'light gray'),
        ('buttn', 'light gray', 'black', 'bold'),
        ('foot', 'light gray', 'black'),
        ('start', 'dark green,bold', 'black'),
    ]
    footer_text = [
        ('Press '), ('<CTRL + C>'),
        (" to open the cancellation menu")]
    timer = CountdownWidget(duration)
    timer_pad = urwid.Padding(timer, align='center', width='clip')
    timer_fill = urwid.Filler(timer_pad)
    title = _("Checkbox slave is about to resume the session!")
    header = urwid.AttrWrap(urwid.Padding(urwid.Text(title), left=1), 'header')
    footer = urwid.AttrWrap(
        urwid.Padding(urwid.Text(footer_text), left=1), 'foot')
    frame = urwid.Frame(urwid.AttrWrap(urwid.LineBox(timer_fill), 'body'),
                        header=header, footer=footer)

    def update_timer(loop, timer):
        if timer.update():
            loop.set_alarm_in(0.1, update_timer, timer)

    loop = urwid.MainLoop(
        frame, palette, handle_mouse=False, screen=Screen())
    update_timer(loop, timer)
    loop.run()


def add_widget(id, widget):
    """Add the widget for a given id."""
    _widget_cache[id] = widget
