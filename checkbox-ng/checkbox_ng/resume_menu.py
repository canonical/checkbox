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

from collections import namedtuple

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
    """
    A ListBox that is not selectable. It is used to display information
    about the currently focused session.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._selectable = False


class ReactiveListBox(urwid.ListBox):
    """
    A ListBox that calls a callback when the focus changes.
    """

    def __init__(self, *args, callback=None, **kwargs):
        self._callback = callback
        super().__init__(*args, **kwargs)

    def keypress(self, size, key):
        res = super().keypress(size, key)
        if key in ("down", "up"):
            self._callback()
        return res


ResumeOutcome = namedtuple(
    "ResumeOutcome", ["session_id", "action", "comments"]
)


class ResumeMenu:
    """
    A menu that allows the operator to choose a session to resume and
    what to do with the last job in the session.

    This menu can be in 3 states:
    - session selection
    - action selection
    - comment entry
    The state is determined by the values of the following attributes:
    - chosen_session
    - chosen_action

    The execution of the menu is done by calling the run() method. It will
    return a ResumeOutcome object with the chosen session, action and comment.
    """

    _SESSION_MENU_STATIC_ELEMENTS = [
        urwid.Text("Incomplete sessions:"),
        urwid.Divider(),
    ]
    _ACTION_MENU_STATIC_ELEMENTS = [
        urwid.Text("What to do with the last job?"),
        urwid.Divider(),
    ]

    @property
    def chosen_session(self):
        return self._chosen_session

    @chosen_session.setter
    def chosen_session(self, value):
        """
        This setter is needed, so the comment is reset when the session is
        changed.
        """
        if value == self._chosen_session:
            return
        self._chosen_session = value
        self._comment = ""
        self._comment_edit_box.edit_text = ""

    def __init__(self, entries):
        """
        Create a new ResumeMenu.

        :param entries: a list of tuples (session_id, session_info)
        """
        self._entries = entries
        self._chosen_session = None
        self._chosen_action = None
        self._comment = ""
        self._infobox = PassiveListBox([])
        nice_box = urwid.AttrWrap(
            urwid.Padding(
                urwid.LineBox(self._infobox),
                align="center",
                width=("relative", 100),
            ),
            "body",
        )

        menu_frame = self._create_menu_frame()

        self._body = urwid.Frame(
            urwid.Columns(
                [
                    ("weight", 5, menu_frame),
                    ("weight", 5, nice_box),
                ],
            ),
            footer=self._create_footer(),
        )
        self._create_action_view()
        self._create_comment_view()
        self._update_infobox()

    @staticmethod
    def _create_footer():
        """Create a footer for the menu."""
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
        """Create an urwid frame for the menu."""
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
            width=("relative", 100),
            height=("relative", 100),
        )
        return urwid.Frame(urwid.AttrWrap(olay, "body"))

    def _create_action_view(self):
        """Create a view for the action selection menu."""
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
        """Create a view for the comment entry."""
        self._comment_edit_box = urwid.Edit("Enter comment:\n")
        box = urwid.LineBox(
            urwid.Filler(
                self._comment_edit_box,
            )
        )
        self._comment_view = urwid.AttrMap(
            urwid.Overlay(
                box,
                self._action_view,
                "center",
                ("relative", 45),
                "middle",
                ("relative", 30),
                left=10,
            ),
            "body",
        )

    def run(self) -> ResumeOutcome:
        """
        Run the menu and return the chosen session and action.
        """
        self.loop = urwid.MainLoop(
            self._body,
            palette,
            unhandled_input=self._unhandled_input,
            handle_mouse=False,
        )
        self.loop.run()
        return ResumeOutcome(
            self._chosen_session, self._chosen_action, self._comment
        )

    def _handle_input_on_session_menu(self, key):
        if key == "enter":
            self.chosen_session = self._entries[self.focused_index][0]
            # now let's show action menu, operator will chose what to do with
            # the session
            self.loop.widget = self._action_view

        elif key == "esc":
            self.chosen_session = None

            raise urwid.ExitMainLoop()
        elif key in ["d", "D"]:
            # user chose to delete the session
            self.chosen_session = self._entries[self.focused_index][0]
            self._chosen_action = "delete"
            raise urwid.ExitMainLoop()

    def _handle_input_on_action_menu(self, key):
        """Handle input on the action menu."""
        if key == "esc":
            # user cancelled the action, go back to the session selection
            self.chosen_session = None
            self.loop.widget = self._body

        elif key == "enter":
            # user chose an action, let's record it and exit
            # if the action is "comment" we need to show the comment box

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
        """Handle input on the comment box."""
        if key == "esc":
            self._comment_edit_box.edit_text = self._comment
            self._chosen_action = None
            self.loop.widget = self._action_view
        if key == "enter":
            self._comment = self._comment_edit_box.edit_text
            self._chosen_action = None
            self.loop.widget = self._action_view

    def _unhandled_input(self, key):
        """
        Handle all input in the urwid loop for the resume screen.
        This propagates the input to the correct handler depending on
        the current state of the menu.
        """
        if self.chosen_session:
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
        """
        Return the index of the currently focused session.
        """
        # there are some static elements in the session menu, like the title
        # and the divider, so when we get the focus position from the listbox
        # we get the index of the focused session item, but that index is
        # relative to the listbox, not the list of sessions, so
        # we need to substract the number of static elements, for instance,
        # if there's 5 static elements, the first session item will have an
        # index of 5 (6th element)

        # on startup the focus index is 0 so when we substract the number of
        # static elements we get -2, which is not what we want, so we need to
        # make sure it's not negative (the first one is selected) hence the
        # max(0, ...)

        return max(
            0,
            self._menu_body.focus_position
            - len(self._SESSION_MENU_STATIC_ELEMENTS),
        )

    def _update_infobox(self):
        """
        Update the infobox to show information about the currently focused
        session.
        """

        labels = self._entries[self.focused_index][1].splitlines()
        text_widgets = [urwid.Text(label) for label in labels]
        self._infobox.body = urwid.SimpleListWalker(
            [
                urwid.Text("Session information: "),
                urwid.Divider(),
            ]
            + text_widgets
        )
