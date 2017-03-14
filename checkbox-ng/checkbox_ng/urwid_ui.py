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

from gettext import gettext as _
import urwid


def TestPlanBrowser(title, test_plan_list, selection=None):
    palette = [
        ('body', 'light gray', 'black', 'standout'),
        ('header', 'black', 'light gray', 'bold'),
        ('buttnf', 'black', 'light gray'),
        ('buttn', 'light gray', 'black', 'bold'),
        ('foot', 'light gray', 'black'),
        ('start', 'dark green,bold', 'black'),
        ]
    footer_text = [('Press '), ('start', '<Enter>'), (' to continue')]
    radio_button_group = []
    blank = urwid.Divider()
    listbox_content = [
        blank,
        urwid.Padding(urwid.Pile(
            [urwid.AttrWrap(urwid.RadioButton(
                radio_button_group,
                txt, state=False), 'buttn', 'buttnf')
                for txt in test_plan_list]),
            left=4, right=3, min_width=13),
        blank,
        ]
    if selection:
        radio_button_group[selection].set_state(True)
    header = urwid.AttrWrap(urwid.Padding(urwid.Text(title), left=1), 'header')
    footer = urwid.AttrWrap(
        urwid.Padding(urwid.Text(footer_text), left=1), 'foot')
    listbox = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
    frame = urwid.Frame(urwid.AttrWrap(urwid.LineBox(listbox), 'body'),
                        header=header, footer=footer)
    del frame._command_map["enter"]

    def unhandled(key):
        if key == "enter":
            raise urwid.ExitMainLoop()

    urwid.MainLoop(frame, palette, unhandled_input=unhandled).run()
    try:
        return next(
            radio_button_group.index(i) for i in radio_button_group if i.state)
    except StopIteration:
        return None

