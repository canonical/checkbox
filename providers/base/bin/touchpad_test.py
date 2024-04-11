#!/usr/bin/env python3

import gi
import sys
import gettext
from time import sleep

from gettext import gettext as _

gi.require_version("Gdk", "3.0")
gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gio, Gtk, Gdk  # noqa: E402
from optparse import OptionParser  # noqa: E402


EXIT_WITH_FAILURE = 1
EXIT_WITH_SUCCESS = 0
EXIT_TIMEOUT = 30


class Direction(object):

    def __init__(self, name):
        self.name = name
        self.tested = False
        self.value = getattr(Gdk.ScrollDirection, name.upper())


class GtkScroller(object):

    exit_code = EXIT_WITH_FAILURE

    def __init__(self, directions, edge_scroll=False):
        self.directions = directions
        self.edge_scroll = edge_scroll
        self.touchpad_key = "org.gnome.settings-daemon.peripherals.touchpad"
        self.horiz_scroll_key = True
        source = Gio.SettingsSchemaSource.get_default()
        if not source.lookup(self.touchpad_key, True):
            self.touchpad_key = "org.gnome.desktop.peripherals.touchpad"
            self.horiz_scroll_key = False
        self.touchpad_settings = Gio.Settings.new(self.touchpad_key)

        # Initialize GTK constants
        self.ICON_SIZE = Gtk.IconSize.BUTTON
        self.ICON_TESTED = Gtk.STOCK_YES
        self.ICON_UNTESTED = Gtk.STOCK_DIALOG_QUESTION
        self.ICON_NOT_REQUIRED = Gtk.STOCK_REMOVE

        self.button_factory = Gtk.Button
        self.hbox_factory = Gtk.HBox
        self.image_factory = Gtk.Image
        self.label_factory = Gtk.Label
        self.vbox_factory = Gtk.VBox

        # Create GTK window.
        window = Gtk.Window()
        window.set_type_hint(Gdk.WindowType.TOPLEVEL)
        window.add_events(
            Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK
        )
        window.set_size_request(200, 100)
        window.set_resizable(False)
        window.set_title(_("Type Text"))
        window.connect("delete-event", lambda w, e: self.quit())
        window.connect("scroll-event", self.on_scroll)
        window.show()

        # Add common widgets to the window.
        vbox = self._add_vbox(window)
        self.label = self._add_label(vbox)
        button_hbox = self._add_hbox(vbox)
        validation_hbox = self._add_hbox(vbox)
        self.status = self._add_label(vbox)
        self.exit_button = self._add_button(vbox, "_Close")
        self.exit_button.connect("clicked", lambda w: self.quit())

        # Add widgets for each direction.
        self.icons = {}
        for direction in self.directions:
            self._add_label(button_hbox, direction.name)
            self.icons[direction] = self._add_image(
                validation_hbox, self.ICON_UNTESTED
            )

        self.show_text(
            _("Please move the mouse cursor to this window.")
            + "\n"
            + _("Then scroll in each direction on your touchpad.")
        )

    def _add_button(self, context, label):
        button = self.button_factory.new_with_mnemonic(label)
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

    def run(self):
        # Save touchpad settings.
        self.saved_edge_scrolling_enabled = self.touchpad_settings.get_boolean(
            "edge-scrolling-enabled"
        )
        self.saved_two_finger_enabled = self.touchpad_settings.get_boolean(
            "two-finger-scrolling-enabled"
        )

        # Set touchpad settings.
        if self.edge_scroll:
            self.touchpad_settings.set_boolean("edge-scrolling-enabled", True)
            self.touchpad_settings.set_boolean(
                "two-finger-scrolling-enabled", False
            )
        else:
            self.touchpad_settings.set_boolean(
                "two-finger-scrolling-enabled", True
            )
            self.touchpad_settings.set_boolean("edge-scrolling-enabled", False)
        Gtk.main()

    def quit(self):
        # Reset touchpad settings.
        self.touchpad_settings.set_boolean(
            "two-finger-scrolling-enabled", self.saved_two_finger_enabled
        )
        # GNOME does not like when both settings are set at the same time, so
        # waiting a bit.
        sleep(0.1)
        self.touchpad_settings.set_boolean(
            "edge-scrolling-enabled", self.saved_edge_scrolling_enabled
        )
        Gtk.main_quit()

    def show_text(self, text, widget=None):
        if widget is None:
            widget = self.label
        widget.set_text(text)

    def found_direction(self, direction):
        direction.tested = True
        self.icons[direction].set_from_icon_name(
            self.ICON_TESTED, size=self.ICON_SIZE
        )
        self.check_directions()

    def check_directions(self):
        if all([direction.tested for direction in self.directions]):
            self.show_text(
                _("All required directions have been tested!"), self.status
            )
            self.exit_code = EXIT_WITH_SUCCESS
            self.exit_button.grab_focus()

    def on_scroll(self, window, event):
        for direction in self.directions:
            scroll_delta, delta_x, delta_y = event.get_scroll_deltas()
            if scroll_delta:
                event_direction = None
                # Arbitrarily using 0.8, which requires a little bit of hand
                # movement on the touchpads used for testing.
                # Note that the directions are based on the default natural
                # scrolling settings in GNOME settings.
                if delta_x > 0.8:
                    event_direction = Direction("left")
                elif delta_x < -0.8:
                    event_direction = Direction("right")
                if delta_y > 0.8:
                    event_direction = Direction("up")
                elif delta_y < -0.8:
                    event_direction = Direction("down")
                if event_direction:
                    if direction.value == event_direction.value:
                        self.found_direction(direction)
                        break
        return True


def main(args):
    gettext.textdomain("checkbox")

    usage = """Usage: %prog DIRECTION... [--edge-scroll]"""
    parser = OptionParser(usage=usage)
    parser.add_option(
        "--edge-scroll",
        action="store_true",
        default=False,
        help="Force touchpad to use edge scrolling only",
    )
    (options, args) = parser.parse_args(args)

    if not args:
        parser.error("Must specify directions to test.")

    directions = []
    for arg in args:
        try:
            direction = Direction(arg)
        except AttributeError:
            parser.error("Unsupported direction: %s" % arg)
        directions.append(direction)

    scroller = GtkScroller(directions, edge_scroll=options.edge_scroll)
    try:
        scroller.run()
    except KeyboardInterrupt:
        scroller.show_text(_("Test interrupted"), scroller.status)
        scroller.quit()

    return scroller.exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
