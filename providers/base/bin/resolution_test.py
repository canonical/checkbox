#!/usr/bin/env python3

import gi
import sys

from argparse import ArgumentParser
from checkbox_support.helpers.release_info import get_release_info

# Define the Ubuntu release number where GTK4 needs to be used
# to handle resolution scaling correctly (starting from Ubuntu 25.04)
GTK4_UBUNTU_RELEASE = 25

# Import GTK/GDK based on the release version
release = int(get_release_info()["release"].split(".")[0])
if release >= GTK4_UBUNTU_RELEASE:
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gtk, Gdk

    Gtk.init()
else:
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk

def get_gobject_geometry(gobject, index=None):
    """Get the width and height of a given GDK object.

    :param gobject: Gdk.Screen or Gdk.Monitor object
    :param index: Index of the monitor
    :returns: Tuple with monitor geometry
    """
    if release >= GTK4_UBUNTU_RELEASE:
        geom = gobject.get_geometry()
        scale_factor = gobject.get_scale_factor()
        print(
            "Resolution is considering the following scale factor: %s"
            % (scale_factor),
        )
        return geom.width * scale_factor, geom.height * scale_factor
    else:
        geom = gobject.get_monitor_geometry(index)
        return geom.width, geom.height


def check_resolution():
    """Check the resolution of all connected monitors."""
    if release >= GTK4_UBUNTU_RELEASE:
        display = Gdk.Display.get_default()
        monitors = display.get_monitors()
        monitor_count = monitors.get_n_items()
        for i in range(monitor_count):
            monitor = monitors.get_item(i)
            width, height = get_gobject_geometry(monitor)
            print("Monitor %d:" % (i + 1))
            print("  %d x %d" % (width, height))
    else:
        screen = Gdk.Screen.get_default()
        for i in range(screen.get_n_monitors()):
            width, height = get_gobject_geometry(screen, i)
            print("Monitor %d:" % (i + 1))
            print("  %d x %d" % (width, height))


def compare_resolution(min_h, min_v):
    """Compare the resolution of the primary display against minimums."""
    if release >= GTK4_UBUNTU_RELEASE:
        display = Gdk.Display.get_default()
        monitors = display.get_monitors()
        primary_monitor = monitors.get_item(0)
        width, height = get_gobject_geometry(primary_monitor)
    else:
        screen = Gdk.Screen.get_default()
        width, height = get_gobject_geometry(
            screen, screen.get_primary_monitor()
        )

    print("Minimum acceptable display resolution: %d x %d" % (min_h, min_v))
    print("Detected display resolution: %d x %d" % (width, height))
    return width >= min_h and height >= min_v


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "--horizontal",
        type=int,
        default=0,
        help="Minimum acceptable horizontal resolution.",
    )
    parser.add_argument(
        "--vertical",
        type=int,
        default=0,
        help="Minimum acceptable vertical resolution.",
    )
    args = parser.parse_args()

    if (args.horizontal > 0) and (args.vertical > 0):
        return not compare_resolution(args.horizontal, args.vertical)
    else:
        check_resolution()

    return 0


if __name__ == "__main__":
    sys.exit(main())
