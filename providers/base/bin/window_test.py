#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# window_test.py
#
# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
#
# Authors: Alberto Milone <alberto.milone@canonical.com>
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

import threading
import time
import os
import sys

from signal import SIGTSTP, SIGCONT, SIGTERM
from subprocess import check_call, check_output, Popen, PIPE
from argparse import ArgumentParser


class AppThread(threading.Thread):

    def __init__(self, app_name):
        self._appname = app_name
        self.stdout = None
        self.stderr = None
        self.pid = None
        threading.Thread.__init__(self)

    def run(self):
        proc = Popen(self._appname, stdout=PIPE, stderr=PIPE)
        self.pid = proc.pid
        print('  Starting "%s", PID: %d' % (self._appname, self.pid))
        self.stdout, self.stderr = proc.communicate()


def open_close_process(app, timeout):
    """Open and close a process after a timeout"""
    status = 0
    # Start the process in a separate thread
    app_thread = AppThread(app)
    app_thread.start()

    # Wait until we have a pid
    while app_thread.pid is None:
        continue
    pid = app_thread.pid

    # Wait a bit and kill the process
    time.sleep(timeout)
    print('  Killing "%s", PID: %d' % (app, pid))
    os.kill(pid, SIGTERM)

    if app_thread.stderr:
        print("Errors:\n%s" % app_thread.stderr, file=sys.stderr)
        status = 1

    time.sleep(timeout)

    return status


def open_close_multi_process(app, timeout, apps_num):
    """Open and close multiple processes after a timeout"""
    status = 0
    threads = []

    for thread in range(apps_num):
        app_thread = AppThread(app)
        app_thread.start()
        threads.append(app_thread)

    for thread in threads:
        # Wait until we have a pid
        while thread.pid is None:
            continue

    # Wait a bit and kill the process
    time.sleep(timeout)
    for thread in threads:
        print('  Killing "%s", PID: %d' % (app, thread.pid))
        os.kill(thread.pid, SIGTERM)
        if thread.stderr:
            print("Errors:\n%s" % thread.stderr, file=sys.stderr)
            status = 1

    time.sleep(timeout)

    return status


def open_suspend_close_process(app, timeout):
    """Open, suspend and close a process after a timeout"""
    status = 0
    # Start the process in a separate thread
    app_thread = AppThread(app)
    app_thread.start()

    # Wait until we have a pid
    while app_thread.pid is None:
        continue
    pid = app_thread.pid

    # Wait a bit and suspend the process
    time.sleep(timeout)
    print('  Suspending "%s", PID: %d' % (app, pid))
    os.kill(pid, SIGTSTP)

    # Wait a bit and resume the process
    time.sleep(timeout)
    print('  Resuming "%s", PID: %d' % (app, pid))
    os.kill(pid, SIGCONT)

    # Wait a bit and kill the process
    time.sleep(timeout)
    print('  Killing "%s", PID: %d' % (app, pid))
    os.kill(pid, SIGTERM)

    if app_thread.stderr:
        print("Errors:\n%s" % app_thread.stderr, file=sys.stderr)
        status = 1

    time.sleep(timeout)

    return status


def move_window(app, timeout):
    status = 0

    # Start the process in a separate thread
    app_thread = AppThread(app)
    app_thread.start()

    while app_thread.pid is None:
        continue

    pid = app_thread.pid

    time.sleep(3)

    window_list = check_output(["wmctrl", "-l"], universal_newlines=True)
    window_id = ""

    for line in window_list.split("\n"):
        if app in line:
            window_id = line.split()[0]

    if window_id:
        # Get the screen information from GDK
        from gi.repository import Gdk

        screen = Gdk.Screen.get_default()
        geom = screen.get_monitor_geometry(screen.get_primary_monitor())

        # Find out the window information from xwininfo
        win_x = ""
        win_y = ""
        win_width = ""
        win_height = ""

        for line in check_output(
            ["xwininfo", "-name", app], universal_newlines=True
        ).split("\n"):
            if "Absolute upper-left X" in line:
                win_x = line.split(": ")[-1].strip()
            elif "Absolute upper-left Y" in line:
                win_y = line.split(": ")[-1].strip()
            elif "Width" in line:
                win_width = line.split(": ")[-1].strip()
            elif "Height" in line:
                win_height = line.split(": ")[-1].strip()

        move_line = ["0", win_x, win_y, win_width, win_height]

        directions = {
            "RIGHT": geom.width,
            "DOWN": geom.height,
            "LEFT": win_x,
            "UP": win_y,
            "STOP": None,
        }
        current = "RIGHT"

        while current != "STOP":
            if current == "RIGHT":
                # Check if top right corner of window reached top right point
                if int(move_line[1]) + int(win_width) != directions[current]:
                    new_x = int(move_line[1]) + 1
                    move_line[1] = str(new_x)
                else:
                    current = "DOWN"
            elif current == "DOWN":
                if int(move_line[2]) + int(win_height) != directions[current]:
                    new_y = int(move_line[2]) + 1
                    move_line[2] = str(new_y)
                else:
                    current = "LEFT"
            elif current == "LEFT":
                if int(move_line[1]) != int(directions[current]):
                    new_x = int(move_line[1]) - 1
                    move_line[1] = str(new_x)
                else:
                    current = "UP"
            elif current == "UP":
                if int(move_line[2]) != int(directions[current]):
                    new_y = int(move_line[2]) - 1
                    move_line[2] = str(new_y)
                else:
                    current = "STOP"

            check_call(
                ["wmctrl", "-i", "-r", window_id, "-e", ",".join(move_line)]
            )

        os.kill(pid, SIGTERM)
    else:
        print("Could not get window handle for %s" % app, file=sys.stderr)
        status = 1

    return status


def print_open_close(iterations, timeout, *args):
    status = 0
    print("Opening and closing a 3D window")
    for it in range(iterations):
        print("Iteration %d of %d:" % (it + 1, iterations))
        exit_status = open_close_process("glxgears", timeout)
        if exit_status != 0:
            status = 1
    print("")
    return status


def print_suspend_resume(iterations, timeout, *args):
    status = 0
    print("Opening, suspending, resuming and closing a 3D window")
    for it in range(iterations):
        print("Iteration %d of %d:" % (it + 1, iterations))
        exit_status = open_suspend_close_process("glxgears", timeout)
        if exit_status != 0:
            status = 1
    print("")
    return status


def print_open_close_multi(iterations, timeout, windows_number):
    status = 0
    print(
        "Opening and closing %d 3D windows at the same time" % windows_number
    )
    for it in range(iterations):
        print("Iteration %d of %d:" % (it + 1, iterations))
        exit_status = open_close_multi_process(
            "glxgears", timeout, windows_number
        )
        if exit_status != 0:
            status = 1
    print("")
    return status


def print_move_window(iterations, timeout, *args):
    status = 0
    print("Moving a 3D window across the screen")

    for it in range(iterations):
        print("Iteration %d of %d:" % (it + 1, iterations))
        status = move_window("glxgears", timeout)

    print("")
    return status


def main():
    tests = {
        "open-close": print_open_close,
        "suspend-resume": print_suspend_resume,
        "open-close-multi": print_open_close_multi,
        "move": print_move_window,
    }

    parser = ArgumentParser(
        description="Script that performs window operation"
    )
    parser.add_argument(
        "-t",
        "--test",
        default="all",
        help="The name of the test to run. \
                              Available tests: \
                              %s, all. \
                              Default is all"
        % (", ".join(tests)),
    )
    parser.add_argument(
        "-i",
        "--iterations",
        type=int,
        default=1,
        help="The number of times to run the test. \
                              Default is 1",
    )
    parser.add_argument(
        "-a",
        "--application",
        default="glxgears",
        help='The 3D application to launch. \
                              Default is "glxgears"',
    )
    parser.add_argument(
        "-to",
        "--timeout",
        type=int,
        default=3,
        help="The time in seconds between each test. \
                              Default is 3",
    )
    parser.add_argument(
        "-w",
        "--windows-number",
        type=int,
        default=4,
        help="The number of windows to open.",
    )

    args = parser.parse_args()

    status = 0

    test = tests.get(args.test)

    if test:
        status = test(args.iterations, args.timeout, args.windows_number)
    else:
        if args.test == "all":
            for test in tests:
                exit_status = tests[test](
                    args.iterations, args.timeout, args.windows_number
                )
                if exit_status != 0:
                    status = exit_status
        else:
            parser.error(
                "-t or --test can only be used with one "
                "of the following tests: "
                "%s, all" % (", ".join(tests))
            )

    return status


if __name__ == "__main__":
    exit(main())
