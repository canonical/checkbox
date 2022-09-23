#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  rotation_test
#
# This file is part of Checkbox.
#
# Copyright 2012-2019 Canonical Ltd.
#
# Authors: Alberto Milone <alberto.milone@canonical.com>
#          Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
import time
import subprocess
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

gi.require_version('Gdk', '3.0')
from gi.repository import Gdk  # noqa: E402


def main():
    """Run rotation cycling by running xrandr command."""
    screen = Gdk.Screen.get_default()
    output = screen.get_monitor_plug_name(screen.get_primary_monitor())
    print("Using output: {}".format(output))
    for rotation in ['right', 'inverted', 'left', 'normal']:
        if os.getenv('XDG_SESSION_TYPE') == 'wayland':
            subprocess.check_call(
                ['gnome-randr', 'modify', output, '--rotate', rotation])
        else:
            print("setting rotation to {}".format(rotation))
            subprocess.check_call(
                ['xrandr', '--output', output, '--rotation', rotation])
        time.sleep(8)


if __name__ == '__main__':
    exit(main())
