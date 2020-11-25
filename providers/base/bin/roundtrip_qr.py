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


import os
import random
import string
import time
import subprocess as sp
import sys

import pyqrcode
import zbar
from PIL import Image


def capture_rpi(name):
    import picamera
    file = os.path.join(os.path.expandvars(
        '$PLAINBOX_SESSION_SHARE'), '{}_qrcapture.png'.format(name))
    with picamera.PiCamera() as camera:
        time.sleep(2)
        camera.capture(file)
    return file


def capture_webcam(name):
    file = os.path.join(os.path.expandvars(
        '$PLAINBOX_SESSION_SHARE'), '{}_qrcapture.jpg'.format(name))
    cmd = ('gst-launch-1.0 v4l2src device=/dev/{} num-buffers=1 ! jpegenc !'
           'filesink location={}').format(name, file)
    try:
        sp.check_call(cmd, shell=True)
    except (sp.CalledProcessError, OSError) as e:
        print(e)
        raise SystemExit('ERROR: failed to capture image')
    return file


def generate_data():
    return ''.join(random.choice(string.ascii_letters) for i in range(10))


def generate_qr_code(data):
    return pyqrcode.create(data)


def display_code(qr):
    with open('/dev/tty0', 'wb+', buffering=0) as term:
        # clear the tty so the qr is always printed at the top of the sceen
        term.write(str.encode('\033c'))
        # print the qr code
        term.write(qr.terminal(quiet_zone=1).encode())


def decode_image(filename):
    scanner = zbar.ImageScanner()
    scanner.parse_config('enable')
    pil = Image.open(filename).convert('L')
    width, height = pil.size
    raw = pil.tobytes()
    image = zbar.Image(width, height, 'Y800', raw)
    scanner.scan(image)
    result = None
    for code in image:
        result = code.data
    del(image)
    if result is None:
        raise SystemExit('ERROR: no qrcodes decoded')
    return result


def main():
    if len(sys.argv) != 2:
        raise SystemExit('ERROR: expected a device name')
    name = sys.argv[1]
    print('Testing device name: {}\n'.format(name))

    test_str = generate_data()
    print('Input string: {}'.format(test_str), flush=True)

    print('Generating QR code...', flush=True)
    qr = generate_qr_code(test_str)

    print('Displaying on screen', flush=True)
    display_code(qr)

    print('Capture image of screen', flush=True)
    if name == 'vchiq':
        file = capture_rpi(name)
    else:
        file = capture_webcam(name)
    print('Image {} captured'.format(file))

    print('Decoding image file', flush=True)
    result = decode_image(file)
    print('Decoded data: {}'.format(result))

    if result != test_str:
        raise SystemExit('FAIL: decoded data does not match input')
    print('PASS: decoded data and input match')


if __name__ == '__main__':
    main()
