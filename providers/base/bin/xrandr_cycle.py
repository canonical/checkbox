#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import tarfile
import time

from fractions import Fraction
from collections import OrderedDict

parser = argparse.ArgumentParser()
parser.add_argument('--keyword', default='',
                    help=('A keyword to distinguish the screenshots '
                          'taken in this run of the script'))
parser.add_argument('--screenshot-dir',
                    default=os.environ['HOME'],
                    help=('Specify a directory to store screenshots in. '
                          'Default is %(default)s'))
args = parser.parse_args()


device_context = ''    # track what device's modes we are looking at
modes = []             # keep track of all the devices and modes discovered
highest_modes = []     # list of highest-res modes for each aspect ratio
current_modes = []     # remember the user's current settings for cleanup later
failures = 0           # count the number of failed modesets
failure_messages = []  # remember which modes failed
success_messages = []  # remember which modes succeeded

# Run xrandr and ask it what devices and modes are supported
xrandrinfo = subprocess.Popen(
    'xrandr -q --verbose', shell=True, stdout=subprocess.PIPE)
output = xrandrinfo.communicate()[0].decode().split('\n')


# The results from xrandr are given in terms of the available display devices.
# One device can have zero or more associated modes.  Unfortunately xrandr
# indicates this through indentation and is kinda wordy, so we have to keep
# track of the context we see mode names in as we parse the results.

for line in output:
    # I haven't seen any blank lines in xrandr's output in my tests, but meh
    if line == '':
        break

    # luckily the various data from xrandr are separated by whitespace...
    foo = line.split()

    # Check to see if the second word in the line indicates a new context
    #  -- if so, keep track of the context of the device we're seeing
    if len(foo) >= 2:  # throw out any weirdly formatted lines
        if foo[1] == 'disconnected':
            # we have a new context, but it should be ignored
            device_context = ''
        if foo[1] == 'connected':
            # we have a new context that we want to test
            device_context = foo[0]
        elif device_context != '':  # we've previously seen a 'connected' dev
            # mode names seem to always be of the format [horiz]x[vert]
            # (there can be non-mode information inside of a device context!)
            x_pos = foo[0].find('x')
            # for a resolution there has to be at least 3 chars:
            # a digit, an x, and a digit
            if x_pos > 0 and x_pos < len(foo[0]) - 1:
                if 'DoubleScan' in foo:
                    # xrandr lists DoubleScan resolutions but cannot set them
                    # so for the purposes of this test let's not use them
                    continue
                if foo[0][x_pos-1].isdigit() and foo[0][x_pos+1].isdigit():
                    modes.append((device_context, foo[0]))
            # we also want to remember what the current mode is, which xrandr
            # marks with a '*' character, so we can set things back the way
            # we found them at the end:
            if "*current" in foo:
                current_modes.append((device_context, foo[0]))
# let's create a dict of aspect_ratio:largest_width for each display
# (width, because it's easier to compare simple ints when looking for the
# highest value). Ignore Interlaced modes that are indicated by presence of a
# trailing 'i' character.
top_res_per_aspect = OrderedDict()
for adapter, mode in modes:
    try:
        if mode[-1] == 'i':
            continue
        width, height = [int(x) for x in mode.split('x')]
        aspect = Fraction(width, height)
        if adapter not in top_res_per_aspect:
            top_res_per_aspect[adapter] = OrderedDict()
        cur_max = top_res_per_aspect[adapter].get(aspect, 0)
        top_res_per_aspect[adapter][aspect] = max(cur_max, width)
    except Exception as exc:
        print("Error parsing %s: %s" % (mode, exc))

highest_modes = []
for adapter, params in top_res_per_aspect.items():
    for aspect, width in params.items():
        # xrandr can list modes that are unsupported, unity-control-center
        # defines minimum width and height, below which the resolution
        # is not listed as a choice in display settings panel in UCC
        # see should_show_resolution function in cc-display-panel.c
        # from lp:unity-control-center
        if width < 675 or width / aspect < 530:
            continue
        mode = '{}x{}'.format(width, width/aspect)
        highest_modes.append((adapter, mode))

# Now we have a list of the modes we need to test.  So let's do just that.
screenshot_path = os.path.join(args.screenshot_dir, 'xrandr_screens')

if args.keyword:
    screenshot_path = screenshot_path + '_' + args.keyword
os.makedirs(screenshot_path, exist_ok=True)

for mode in highest_modes:
    message = 'Set mode ' + mode[1] + ' for output ' + mode[0]
    print(message, flush=True)
    cmd = 'xrandr --output ' + mode[0] + ' --mode ' + mode[1]
    retval = subprocess.call(cmd, shell=True)
    if retval != 0:
        failures = failures + 1
        message = 'Failed to set mode ' + mode[1] + ' for output ' + mode[0]
        print(message, file=sys.stderr, flush=True)
    else:
        mode_string = mode[0] + '_' + mode[1]
        filename = os.path.join(screenshot_path, mode_string + '.jpg')
        cmd = 'gnome-screenshot -f ' + filename
        result = subprocess.run(cmd, shell=True, check=False)
        if result.returncode != 0:
            print("Could not capture screenshot -\n"
                  "you may need to install the package 'gnome-screenshot'.",
                  file=sys.stderr, flush=True)
    time.sleep(8)  # let the hardware recover a bit

# Put things back the way we found them

for mode in current_modes:
    cmd = 'xrandr --output ' + mode[0] + ' --mode ' + mode[1]
    subprocess.call(cmd, shell=True)

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
