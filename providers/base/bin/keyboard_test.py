#!/usr/bin/env python3

import os
import sys
from gettext import gettext as _
import gettext


def cli_prompt():
    import termios

    limit = 50
    separator = ord("\n")
    fileno = sys.stdin.fileno()
    saved_attributes = termios.tcgetattr(fileno)
    attributes = termios.tcgetattr(fileno)
    attributes[3] = attributes[3] & ~(termios.ICANON)
    attributes[6][termios.VMIN] = 1
    attributes[6][termios.VTIME] = 0
    termios.tcsetattr(fileno, termios.TCSANOW, attributes)

    sys.stdout.write(_("Enter text:\n"))

    input = ""
    try:
        while len(input) < limit:
            ch = str(sys.stdin.read(1))
            if ord(ch) == separator:
                break
            input += ch
    finally:
        termios.tcsetattr(fileno, termios.TCSANOW, saved_attributes)


def gtk_prompt():
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk

    # create a new window
    window = Gtk.Window()
    window.set_type_hint(Gdk.WindowType.TOPLEVEL)
    window.set_size_request(200, 100)
    window.set_resizable(False)
    window.set_title(_("Type Text"))
    window.connect("delete_event", lambda w, e: Gtk.main_quit())

    vbox = Gtk.VBox()
    vbox.set_homogeneous(False)
    vbox.set_spacing(0)
    window.add(vbox)
    vbox.show()

    entry = Gtk.Entry()
    entry.set_max_length(50)
    vbox.pack_start(entry, True, True, 0)
    entry.show()

    hbox = Gtk.HBox()
    hbox.set_homogeneous(False)
    hbox.set_spacing(0)
    vbox.add(hbox)
    hbox.show()

    button = Gtk.Button(stock=Gtk.STOCK_CLOSE)
    button.connect("clicked", lambda w: Gtk.main_quit())
    vbox.pack_start(button, False, False, 0)
    button.set_can_default(True)
    button.grab_default()
    button.show()
    window.show()

    Gtk.main()


def main(args):

    gettext.textdomain("checkbox")

    if "DISPLAY" in os.environ:
        gtk_prompt()
    else:
        cli_prompt()

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
