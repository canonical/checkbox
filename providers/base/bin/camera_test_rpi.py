#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2020 Canonical Ltd.
# Written by:
#   Jonathan Cave <jonathan.cave@canonical.com>
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
import sys
import time

import picamera

# resolutions and framerates corresponding to sensor modes at:
# https://picamera.readthedocs.io/en/release-1.13/fov.html#camera-modes
test_res = [
    ((1920, 1080), 2),
    ((2592, 1944), 2),
    ((2592, 1944), (1, 8)),
    ((1296, 972), 5),
    ((1296, 730), 20),
    ((640, 480), 50),
    ((640, 480), 80),
]


def capture():
    path = os.path.expandvars('$PLAINBOX_SESSION_SHARE')
    print('Images will be written to:\n{}\n'.format(path), flush=True)
    for mode_no, (res, fr) in enumerate(test_res):
        with picamera.PiCamera(resolution=res, framerate=fr) as camera:
            print('Camera initialised, wait to settle...', flush=True)
            time.sleep(2)
            print('Resolution: {}'.format(camera.resolution))
            print('Framerate: {}'.format(camera.framerate))
            file = 'picam_{}.jpg'.format(mode_no+1)
            camera.capture(os.path.join(path, file))
            print('Image {} captured\n'.format(file))


def main():
    parser = argparse.ArgumentParser(description='PiCamera Tests')
    parser.add_argument('--device', default="/dev/vchiq", type=str)
    args = parser.parse_args()
    print('Resolutions test on device: {}'.format(args.device), flush=True)
    return capture()


if __name__ == "__main__":
    sys.exit(main())
