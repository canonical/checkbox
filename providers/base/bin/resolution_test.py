#!/usr/bin/env python3

import gi
import sys
import tkinter as tk

from argparse import ArgumentParser

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk  # noqa: E402


def check_resolution():
    screen = Gdk.Screen.get_default()
    n = screen.get_n_monitors()
    for i in range(n):
        geom = screen.get_monitor_geometry(i)
        print("Monitor %d:" % (i + 1))
        print("  %d x %d" % (geom.width, geom.height))


def compare_resolution(min_h, min_v):
    try:
        root = tk.Tk()
    except tk.TclError as e:
        print(e)
        print("Are you sure the device is logged in and has a screen?")
    width = root.winfo_screenwidth()
    height = root.winfo_screenheight()
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
