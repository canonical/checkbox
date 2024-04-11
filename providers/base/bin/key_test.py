#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
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


import gi
import os
import sys

import fcntl
import gettext
import struct
import termios

from gettext import gettext as _

from gi.repository import GLib
from optparse import OptionParser


EXIT_WITH_FAILURE = 1
EXIT_WITH_SUCCESS = 0
EXIT_TIMEOUT = 30

# Keyboard options from /usr/include/linux/kd.h
K_RAW = 0x00
K_XLATE = 0x01
K_MEDIUMRAW = 0x02
K_UNICODE = 0x03
K_OFF = 0x04
KDGKBMODE = 0x4B44
KDSKBMODE = 0x4B45


def ioctl_p_int(fd, request, value=0):
    s = struct.pack("i", value)
    s2 = fcntl.ioctl(fd, request, s)
    (ret,) = struct.unpack("i", s2)  # This always returns a tuple.
    return ret


class Key:

    def __init__(self, codes, name=None):
        self.codes = codes
        self.name = name
        self.tested = False
        self.required = True

    @property
    def status(self):
        if not self.required:
            return _("Not required")
        if not self.tested:
            return _("Untested")
        return _("Tested")


class Reporter(object):

    exit_code = EXIT_WITH_FAILURE

    def __init__(self, main_loop, keys, scancodes=False):
        self.main_loop = main_loop
        self.keys = keys
        self.scancodes = scancodes

        self.fileno = os.open("/dev/console", os.O_RDONLY)
        GLib.io_add_watch(self.fileno, GLib.IO_IN, self.on_key)

        # Set terminal attributes
        self.saved_attributes = termios.tcgetattr(self.fileno)
        attributes = termios.tcgetattr(self.fileno)
        attributes[3] &= ~(termios.ICANON | termios.ECHO)
        attributes[6][termios.VMIN] = 1
        attributes[6][termios.VTIME] = 0
        termios.tcsetattr(self.fileno, termios.TCSANOW, attributes)

        # Set keyboard mode
        self.saved_mode = ioctl_p_int(self.fileno, KDGKBMODE)
        mode = K_RAW if scancodes else K_MEDIUMRAW
        fcntl.ioctl(self.fileno, KDSKBMODE, mode)

    def _parse_codes(self, raw_bytes):
        """Parse the given string of bytes to scancodes or keycodes."""
        if self.scancodes:
            return self._parse_scancodes(raw_bytes)
        else:
            return self._parse_keycodes(raw_bytes)

    def _parse_scancodes(self, raw_bytes):
        """Parse the bytes in raw_bytes into a scancode."""
        index = 0
        length = len(raw_bytes)
        while index < length:
            if index + 1 < length and raw_bytes[index] == 0xE0:
                code = (raw_bytes[index] << 8) | raw_bytes[index + 1]
                index += 2
            else:
                code = raw_bytes[0]
                index += 1

            yield code

    def _parse_keycodes(self, raw_bytes):
        """Parse the bytes in raw_bytes into a keycode."""
        index = 0
        length = len(raw_bytes)
        while index < length:
            if (
                index + 2 < length
                and (raw_bytes[index] & 0x7F) == 0
                and (raw_bytes[index + 1] & 0x80) != 0
                and (raw_bytes[index + 2] & 0x80) != 0
            ):
                code = ((raw_bytes[index + 1] & 0x7F) << 7) | (
                    raw_bytes[2] & 0x7F
                )
                index += 3
            else:
                code = raw_bytes[0] & 0x7F
                index += 1

            yield code

    @property
    def required_keys_tested(self):
        """Returns True if all keys marked as required have been tested"""
        return all([key.tested for key in self.keys if key.required])

    def show_text(self, string):
        pass

    def quit(self, exit_code=EXIT_WITH_FAILURE):
        self.exit_code = exit_code

        termios.tcsetattr(self.fileno, termios.TCSANOW, self.saved_attributes)
        fcntl.ioctl(self.fileno, KDSKBMODE, self.saved_mode)

        # FIXME: Having a reference to the mainloop is suboptimal.
        self.main_loop.quit()

    def found_key(self, key):
        key.tested = True

    def toggle_key(self, key):
        key.required = not key.required
        key.tested = False

    def on_key(self, source, cb_condition):
        raw_bytes = os.read(source, 18)
        for code in self._parse_codes(raw_bytes):
            if code == 1:
                # Check for ESC key pressed
                self.show_text(_("Test cancelled"))
                self.quit()
            elif 1 < code < 10 and isinstance(self, CLIReporter):
                # Check for number to skip
                self.toggle_key(self.keys[code - 2])
            else:
                # Check for other key pressed
                for key in self.keys:
                    if code in key.codes:
                        self.found_key(key)
                        break

        return True


class CLIReporter(Reporter):

    def __init__(self, *args, **kwargs):
        super(CLIReporter, self).__init__(*args, **kwargs)

        self.show_text(_("Please press each key on your keyboard."))
        self.show_text(
            _("I will exit automatically once all keys " "have been pressed.")
        )
        self.show_text(
            _(
                "If your keyboard lacks one or more keys, "
                "press its number to skip testing that key."
            )
        )
        self.show_text(_("You can also close me by pressing ESC or Ctrl+C."))

        self.show_keys()

    def show_text(self, string):
        sys.stdout.write(string + "\n")
        sys.stdout.flush()

    def show_keys(self):
        self.show_text("---")
        for index, key in enumerate(self.keys):
            self.show_text(
                "%(number)d - %(key)s - %(status)s"
                % {"number": index + 1, "key": key.name, "status": key.status}
            )

    def found_key(self, key):
        super(CLIReporter, self).found_key(key)
        self.show_text(
            _("%(key_name)s key has been pressed" % {"key_name": key.name})
        )

        self.show_keys()
        if self.required_keys_tested:
            self.show_text(_("All required keys have been tested!"))
            self.quit(EXIT_WITH_SUCCESS)

    def toggle_key(self, key):
        super(CLIReporter, self).toggle_key(key)
        self.show_keys()


class GtkReporter(Reporter):

    def __init__(self, *args, **kwargs):
        super(GtkReporter, self).__init__(*args, **kwargs)

        gi.require_version("Gdk", "3.0")
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk, Gtk

        # Initialize GTK constants
        self.ICON_SIZE = Gtk.IconSize.BUTTON
        self.ICON_TESTED = Gtk.STOCK_YES
        self.ICON_UNTESTED = Gtk.STOCK_INDEX
        self.ICON_NOT_REQUIRED = Gtk.STOCK_REMOVE

        self.button_factory = Gtk.Button
        self.hbox_factory = Gtk.HBox
        self.image_factory = Gtk.Image
        self.label_factory = Gtk.Label
        self.vbox_factory = Gtk.VBox

        # Create GTK window.
        window = Gtk.Window()
        window.set_type_hint(Gdk.WindowType.TOPLEVEL)
        window.set_size_request(100, 100)
        window.set_resizable(False)
        window.set_title(_("Key test"))
        window.connect("delete_event", lambda w, e: self.quit())
        window.connect(
            "key-release-event",
            lambda w, k: k.keyval == Gdk.KEY_Escape and self.quit(),
        )
        window.show()

        # Add common widgets to the window.
        vbox = self._add_vbox(window)
        self.label = self._add_label(vbox)
        button_hbox = self._add_hbox(vbox)
        validation_hbox = self._add_hbox(vbox)
        skip_hbox = self._add_hbox(vbox)
        exit_button = self._add_button(vbox, _("_Exit"), True)
        exit_button.connect("clicked", lambda w: self.quit())

        # Add widgets for each key.
        self.icons = {}
        for key in self.keys:
            stock = getattr(Gtk, "STOCK_MEDIA_%s" % key.name.upper(), None)
            if stock:
                self._add_image(button_hbox, stock)
            else:
                self._add_label(button_hbox, key.name)
            self.icons[key] = self._add_image(validation_hbox, Gtk.STOCK_INDEX)
            button = self._add_button(skip_hbox, _("Skip"))
            button.connect("clicked", self.on_skip, key)

        self.show_text(_("Please press each key on your keyboard."))
        self.show_text(
            _(
                "If a key is not present in your keyboard, "
                "press the 'Skip' button below it to remove it "
                "from the test."
            )
        )

    def _add_button(self, context, label, use_underline=False):
        button = self.button_factory(label=label, use_underline=use_underline)
        context.add(button)
        button.show()
        return button

    def _add_hbox(self, context, spacing=4):
        hbox = self.hbox_factory()
        context.add(hbox)
        hbox.set_spacing(4)
        hbox.show()
        return hbox

    def _add_image(self, context, stock):
        image = self.image_factory(stock=stock, icon_size=self.ICON_SIZE)
        context.add(image)
        image.show()
        return image

    def _add_label(self, context, text=None):
        label = self.label_factory()
        context.add(label)
        label.set_size_request(0, 0)
        label.set_line_wrap(True)
        if text:
            label.set_text(text)
        label.show()
        return label

    def _add_vbox(self, context):
        vbox = self.vbox_factory()
        vbox.set_homogeneous(False)
        vbox.set_spacing(8)
        context.add(vbox)
        vbox.show()
        return vbox

    def show_text(self, string):
        self.label.set_text(self.label.get_text() + "\n" + string)

    def check_keys(self):
        if self.required_keys_tested:
            self.show_text(_("All required keys have been tested!"))
            self.quit(EXIT_WITH_SUCCESS)

    def found_key(self, key):
        super(GtkReporter, self).found_key(key)
        self.icons[key].set_from_icon_name(
            self.ICON_TESTED, size=self.ICON_SIZE
        )

        self.check_keys()

    def on_skip(self, sender, key):
        self.toggle_key(key)
        if key.required:
            stock_icon = self.ICON_UNTESTED
        else:
            stock_icon = self.ICON_NOT_REQUIRED
        self.icons[key].set_from_icon_name(stock_icon, self.ICON_SIZE)

        self.check_keys()


def main(args):
    gettext.textdomain("checkbox")

    usage = """\
Usage: %prog [OPTIONS] CODE...

Syntax for codes:

  57435               - Decimal code without name
  0160133:Super       - Octal code with name
  0xe05b,0xe0db:Super - Multiple hex codes with name

Hint to find codes:

  The showkey command can show keycodes and scancodes.
"""
    parser = OptionParser(usage=usage)
    parser.add_option(
        "-i",
        "--interface",
        default="auto",
        help="Interface to use: cli, gtk or auto",
    )
    parser.add_option(
        "-s",
        "--scancodes",
        default=False,
        action="store_true",
        help="Test for scancodes instead of keycodes.",
    )
    (options, args) = parser.parse_args(args)

    # Get reporter factory from options or environment.
    if options.interface == "auto":
        if "DISPLAY" in os.environ:
            reporter_factory = GtkReporter
        else:
            reporter_factory = CLIReporter
    elif options.interface == "cli":
        reporter_factory = CLIReporter
    elif options.interface == "gtk":
        reporter_factory = GtkReporter
    else:
        parser.error("Unsupported interface: %s" % options.interface)

    if not args:
        parser.error("Must specify codes to test.")

    # Get keys from command line arguments.
    keys = []
    for codes_name in args:
        if ":" in codes_name:
            codes, name = codes_name.split(":", 1)
        else:
            codes, name = codes_name, codes_name

        # Guess the proper base from the string.
        codes = [int(code, 0) for code in codes.split(",")]
        key = Key(codes, name)
        keys.append(key)

    main_loop = GLib.MainLoop()
    try:
        reporter = reporter_factory(main_loop, keys, options.scancodes)
    except OSError:
        parser.error("Failed to initialize interface: %s" % options.interface)

    try:
        main_loop.run()
    except KeyboardInterrupt:
        reporter.show_text(_("Test interrupted"))
        reporter.quit()

    return reporter.exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
