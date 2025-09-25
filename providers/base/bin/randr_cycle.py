#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.


from checkbox_support.dbus.gnome_monitor import MutterDisplayMode as Mode
from checkbox_support.helpers import display_info
from fractions import Fraction
from typing import List
import subprocess
import argparse
import tarfile
import time
import sys
import os


def resolution_filter(modes: List[Mode]):
    """
    For filtering resolution then returning needed,
    Following will be ignored:
    1. aspect is too small
    2. the same resolution
    3. smaller width with the same aspect
    This function will be called by the cycle method in the
    checkbox_support.dbus.gnome_monitor

    :param modes:  The list of Mode that defined
                   in checkbox_support.dbus.gnome_monitor
    """
    new_modes = []
    tmp_resolution = []
    sort_modes = sorted(
        modes, key=lambda m: int(m.resolution.split("x")[0]), reverse=True
    )
    top_res_per_aspect = {}
    for m in sort_modes:
        width, height = [int(x) for x in m.resolution.split("x")]
        aspect = Fraction(width, height)
        # Igonre the too small one
        if width < 675 or width / aspect < 530:
            continue
        # Igonre the same one
        if m.resolution in tmp_resolution:
            continue
        # Only take the widthest one with the same aspect
        if aspect not in top_res_per_aspect:
            top_res_per_aspect[aspect] = (m, width)
            new_modes.append(m)
        else:
            pre_m, pre_width = top_res_per_aspect[aspect]
            if pre_width < width:
                # list of resolution is sorted and should not be here
                top_res_per_aspect[aspect] = width
                new_modes.append(m)
                new_modes.remove(pre_m)
        tmp_resolution.append(m.resolution)

    return new_modes


def action(filename, **kwargs):
    """
    For extra steps for each cycle.
    The extra steps is typing and moving mouse randomly
    then take a screenshot.
    This function will be called by the cycle method in the
    checkbox_support.dbus.gnome_monitor

    :param filename: The string is constructed by
                     [monitor name]_[resolution]_[transform]_.
    """
    print("Test: {}".format(filename), flush=True)
    if "path" in kwargs:
        path_and_filename = "{}/{}.jpg".format(kwargs.get("path"), filename)
    else:
        path_and_filename = "{}.jpg".format(filename)
    time.sleep(5)
    subprocess.check_output(["gnome-screenshot", "-f", path_and_filename])


class MonitorTest:
    def gen_screenshot_path(
        self, prefix: str, postfix: str, screenshot_dir: str
    ) -> str:
        """
        Generate the screenshot path and create the folder.
        If the keyword is not defined, it will check the suspend_stats to
        decide the keyowrd should be after_suspend or not

        :param keyword: the postfix for the path

        :param screenshot_dir: the dictionary for screenshot
        """
        path = ""
        if prefix and prefix != "":
            path = os.path.join(screenshot_dir, prefix + "_xrandr_screens")
        else:
            path = os.path.join(screenshot_dir, "xrandr_screens")

        if postfix and postfix != "":
            path = path + "_" + postfix
        else:
            # check the status is before or after suspend
            with open("/sys/power/suspend_stats/success", "r") as s:
                suspend_count = s.readline().strip("\n")
                if suspend_count != "0":
                    path = "{}_after_suspend".format(path)
        os.makedirs(path, exist_ok=True)

        return path

    def tar_screenshot_dir(self, path: str):
        """
        Tar up the screenshots for uploading.

        :param path: the dictionary for screenshot
        """
        try:
            with tarfile.open(path + ".tgz", "w:gz") as screen_tar:
                for screen in os.listdir(path):
                    screen_tar.add(path + "/" + screen, screen)
        except (IOError, OSError):
            pass

    def parse_args(self, args=sys.argv[1:]):
        """
        command line arguments parsing

        :param args: arguments from sys
        :type args: sys.argv
        """
        parser = argparse.ArgumentParser(
            prog="monitor tester",
            description="Test monitor that could rotate and change resoultion",
        )

        parser.add_argument(
            "-c",
            "--cycle",
            type=str,
            default="both",
            help="cycling resolution, transform or both(default: %(default)s)",
        )
        parser.add_argument(
            "--prefix",
            default="",
            help=(
                "A keyword to distinguish the screenshots "
                "taken in this run of the script(default: %(default)s)"
            ),
        )
        parser.add_argument(
            "--postfix",
            default="",
            help=(
                "A keyword to distinguish the screenshots "
                "taken in this run of the script(default: %(default)s)"
            ),
        )
        parser.add_argument(
            "--screenshot_dir",
            default=os.getenv("HOME", "~"),
            help=(
                "Specify a directory to store screenshots in. "
                "(default: %(default)s)"
            ),
        )

        return parser.parse_args(args)

    def main(self):
        args = self.parse_args()

        try:
            monitor_config = display_info.get_monitor_config()
        except ValueError as e:
            raise SystemExit("Current host is not support: {}".format(e))

        screenshot_path = self.gen_screenshot_path(
            args.prefix, args.postfix, args.screenshot_dir
        )
        if args.cycle == "resolution":
            monitor_config.cycle(
                cycle_resolutions=True,
                resolution_filter=resolution_filter,
                cycle_transforms=False,
                post_cycle_action=action,
                path=screenshot_path,
            )
        elif args.cycle == "transform":
            monitor_config.cycle(
                cycle_resolutions=False,
                resolution_filter=resolution_filter,
                cycle_transforms=True,
                post_cycle_action=action,
                path=screenshot_path,
            )
        else:
            monitor_config.cycle(
                cycle_resolutions=True,
                resolution_filter=resolution_filter,
                cycle_transforms=True,
                post_cycle_action=action,
                path=screenshot_path,
            )
        self.tar_screenshot_dir(screenshot_path)


if __name__ == "__main__":
    MonitorTest().main()
