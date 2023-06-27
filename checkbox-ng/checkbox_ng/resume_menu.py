# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
This module contains Uriwd components used on Resume Session screen.
"""
import urwid

palette = [
    ("focus", "black", "light gray", "standout"),
    ("body", "light gray", "black", "standout"),
    ("head", "black", "light gray", "bold"),
    ("buttnf", "black", "light gray"),
    ("buttn", "light gray", "black", "bold"),
    ("foot", "light gray", "black"),
    ("start", "dark green,bold", "black"),
]


class PassiveListBox(urwid.ListBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._selectable = False


class ReactiveListBox(urwid.ListBox):
    def __init__(self, *args, callback=None, **kwargs):
        self._callback = callback
        super().__init__(*args, **kwargs)

    def keypress(self, size, key):
        res = super().keypress(size, key)
        if key in ("down", "up"):
            self._callback()
        return res


class ResumeMenu:
    _SESSION_MENU_STATIC_ELEMENTS = [
        urwid.Text("Incomplete sessions:"),
        urwid.Divider(),
    ]
    _ACTION_MENU_STATIC_ELEMENTS = [
        urwid.Text("What to do with the last job?"),
        urwid.Divider(),
    ]

    def __init__(self, entries):
        self._entries = entries
        self._chosen_session = None
        self._chosen_action = None
        self._comment = ""
        self._infobox = PassiveListBox([])
        nice_box = urwid.AttrWrap(
            urwid.Padding(
                urwid.LineBox(self._infobox),
                align="center",
                width=("relative", 90),
            ),
            "body",
        )

        menu_frame = self._create_menu_frame()

        self._body = urwid.Frame(
            urwid.Columns(
                [
                    ("weight", 6, menu_frame),
                    ("weight", 4, nice_box),
                ]
            ),
            footer=self._create_footer(),
        )
        self._create_action_view()
        self._create_comment_view()
        self._update_infobox()

    @staticmethod
    def _create_footer():
        footer_text = [
            ("Press "),
            ("start", "<Enter>"),
            (" to resume the session, "),
            ("start", "D"),
            (" to delete the session, or "),
            ("start", "<ESC>"),
            (" to go back"),
        ]
        return urwid.AttrWrap(
            urwid.Padding(urwid.Text(footer_text), left=1), "foot"
        )

    def _create_menu_frame(self):
        menu_entries = [urwid.Button(id) for id, _ in self._entries]

        self._menu_body = ReactiveListBox(
            urwid.SimpleFocusListWalker(
                self._SESSION_MENU_STATIC_ELEMENTS + menu_entries
            ),
            callback=self._update_infobox,
        )
        menu = urwid.LineBox(self._menu_body)
        olay = urwid.Overlay(
            menu,
            urwid.SolidFill(" "),
            align="center",
            valign="middle",
            width=("relative", 90),
            height=("relative", 100),
        )
        return urwid.Frame(urwid.AttrWrap(olay, "body"))

    def _create_action_view(self):
        self._action_buttons = [
            # label that goes on the button and the action string recorded
            ("Add comment", "comment"),
            ("Resume and skip the job", "skip"),
            ("Mark the job as passed and continue", "pass"),
            ("Mark the job as failed and continue", "fail"),
            ("Resume and run the job again.", "rerun"),
        ]
        action_listbox_content = self._ACTION_MENU_STATIC_ELEMENTS + [
            urwid.Button(btn[0]) for btn in self._action_buttons
        ]

        self._action_menu = urwid.LineBox(
            urwid.ListBox(urwid.SimpleFocusListWalker(action_listbox_content))
        )
        self._action_view = urwid.AttrWrap(
            urwid.Overlay(
                self._action_menu,
                self._body,
                "center",
                ("relative", 50),
                "middle",
                ("relative", 50),
                left=10,
            ),
            "body",
        )

    def _create_comment_view(self):
        self._comment_edit_box = urwid.Edit("Enter comment:\n")
        box = urwid.Filler(self._comment_edit_box)
        self._comment_view = urwid.AttrMap(
            urwid.Overlay(
                box,
                self._action_menu,
                "center",
                ("relative", 50),
                "middle",
                ("relative", 50),
                left=10,
            ),
            "body",
        )

    def run(self):
        self.loop = urwid.MainLoop(
            self._body,
            palette,
            unhandled_input=self._unhandled_input,
            handle_mouse=False,
        )
        self.loop.run()

        return (self._chosen_session, self._chosen_action, self._comment)

    def _handle_input_on_session_menu(self, key):
        if key == "enter":
            chosen_session = self._entries[self.focused_index][0]
            if chosen_session != self._chosen_session:
                # operator may have selected a session and then written a
                # comment but then went back to the previous menu, and
                # selected another session, so we need to disregard the
                # comment they entered
                self._comment = ""
                self._comment_edit_box.edit_text = ""
                self._chosen_session = chosen_session
            # now let's show action menu, operator will chose what to do with
            # the session
            self.loop.widget = self._action_view

        elif key == "esc":
            self._chosen_session = None

            raise urwid.ExitMainLoop()

    def _handle_input_on_action_menu(self, key):
        if key == "esc":
            # self.loop.widget = self._body
            self._chosen_session = None
            self.loop.widget = self._body

        elif key == "enter":
            action_index = self._action_menu.base_widget.focus_position - len(
                self._ACTION_MENU_STATIC_ELEMENTS
            )
            action = self._action_buttons[action_index][1]

            self._chosen_action = action
            if action == "comment":
                self.loop.widget = self._comment_view
            else:
                raise urwid.ExitMainLoop()

    def _handle_input_on_comment_box(self, key):
        if key == "esc":
            self._comment_edit_box.edit_text = self._comment
            self._chosen_action = None
            self.loop.widget = self._action_view
        if key == "enter":
            self._comment = self._comment_edit_box.edit_text
            self._chosen_action = None
            self.loop.widget = self._action_view

    def _unhandled_input(self, key):
        if self._chosen_session:
            # if the session is already chosen it means we're
            # on the action selection menu or entering a comment
            if self._chosen_action:
                self._handle_input_on_comment_box(key)
            else:
                self._handle_input_on_action_menu(key)
        else:
            # otherwise it means were' at the session selection menu
            self._handle_input_on_session_menu(key)

    @property
    def focused_index(self):
        # we need to substract the number of static elements, for instance,
        # if there's 5 static elements, the first session item will have an
        # index of 5 (6th element)
        return self._menu_body.focus_position - len(
            self._SESSION_MENU_STATIC_ELEMENTS
        )

    def _update_infobox(self):
        labels = self._entries[self.focused_index][1].split("\n")
        text_widgets = [urwid.Text(label) for label in labels]
        self._infobox.body = urwid.SimpleListWalker(
            [
                urwid.Text("Session information: "),
                urwid.Divider(),
            ]
            + text_widgets
        )
