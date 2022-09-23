#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2022 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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

import argparse
import os
import subprocess
import sys
import tarfile
import time

from collections import OrderedDict
from fractions import Fraction

parser = argparse.ArgumentParser()
parser.add_argument('--keyword', default='',
                    help=('A keyword to distinguish the screenshots '
                          'taken in this run of the script'))
parser.add_argument('--screenshot-dir',
                    default=os.environ['HOME'],
                    help=('Specify a directory to store screenshots in. '
                          'Default is %(default)s'))
args = parser.parse_args()

randrinfo = subprocess.Popen(
    'gnome-randr', shell=True, stdout=subprocess.PIPE)
output = randrinfo.communicate()[0].decode().split('\n')

monitor = ''
monitors = dict()
highest_modes = []     # list of highest-res modes for each aspect ratio
current_modes = []     # remember the user's current settings for cleanup later
failures = 0           # count the number of failed modesets

for line in output:
    # Ignore Interlaced modes that are indicated by presence of a
    # trailing 'i' character.
    if ':' in line or line == '' or 'i@' in line:
        continue
    if not (line.startswith(' ') or line.startswith('\t')):
        try:
            monitor = line.split()[0]
            monitors[monitor] = OrderedDict()
            continue
        except IndexError:
            continue
    if monitor:
        modeline = line.split()
        try:
            mode, resolution, rate = modeline[:3]
            width, height = [int(x) for x in resolution.split('x')]
            aspect = Fraction(width, height)
            if width < 675 or width / aspect < 530:
                continue
            if resolution in monitors[monitor]:
                existing_rate = monitors[monitor][resolution][4]
                if rate < existing_rate:
                    continue
            monitors[monitor][resolution] = (width, aspect, mode, rate)
        except IndexError:
            continue

for monitor in monitors.keys():
    # let's create a dict of aspect_ratio:largest_width for each display
    # (width, because it's easier to compare simple ints when looking for the
    # highest value).
    top_res_per_aspect = OrderedDict()
    connected = False
    for resolution in monitors[monitor]:
        width, aspect, mode, rate = monitors[monitor][resolution]
        cur_max = top_res_per_aspect.get(aspect, 0)
        top_res_per_aspect[aspect] = max(cur_max, width)
        if '*' in rate:
            connected = True
            current_modes.append((monitor, resolution, mode, rate))
    if not connected:
        continue
    for aspect_ratio, max_width in reversed(top_res_per_aspect.items()):
        for resolution in monitors[monitor]:
            width, aspect, mode, rate = monitors[monitor][resolution]
            if aspect == aspect_ratio and width == max_width:
                highest_modes.append((monitor, resolution, mode, rate))

screenshot_path = os.path.join(args.screenshot_dir, 'xrandr_screens')

if args.keyword:
    screenshot_path = screenshot_path + '_' + args.keyword
os.makedirs(screenshot_path, exist_ok=True)

for monitor, resolution, mode, rate in highest_modes + current_modes:
    rate = rate.replace('+', '').replace('*', '')
    print("Set mode {}@{} for output {}".format(resolution, rate, monitor),
          flush=True)
    cmd = 'gnome-randr modify ' + monitor + ' -m ' + mode
    try:
        subprocess.run(cmd, check=True, shell=True, stdout=subprocess.PIPE)
        mode_string = monitor + '_' + resolution
        filename = os.path.join(screenshot_path, mode_string + '.jpg')
        cmd = 'gnome-screenshot -f ' + filename
        result = subprocess.run(cmd, shell=True, check=False)
        if result.returncode != 0:
            print("Could not capture screenshot -\n"
                  "you may need to install the package 'gnome-screenshot'.",
                  file=sys.stderr, flush=True)
    except subprocess.CalledProcessError:
        failures = failures + 1
        print('Failed to set mode {} for output {}:'.format(mode, monitor),
              file=sys.stderr, flush=True)
        print('    {}'.format(cmd), file=sys.stderr, flush=True)
    time.sleep(8)  # let the hardware recover a bit

# Tar up the screenshots for uploading
try:
    with tarfile.open(screenshot_path + '.tgz', 'w:gz') as screen_tar:
        for screen in os.listdir(screenshot_path):
            screen_tar.add(screenshot_path + '/' + screen, screen)
except (IOError, OSError):
    pass

if failures != 0:
    exit(1)
else:
    exit(0)
