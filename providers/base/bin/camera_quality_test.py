#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2008-2023 Canonical Ltd.
# Written by:
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
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
#

import argparse
import time
import sys

import cv2
from numpy import isnan

from checkbox_support.vendor.brisque.brisque import BRISQUE
from tempfile import NamedTemporaryFile

THRESHOLD = 60


def get_image_from_device(device: str):
    # Set the video device
    index = int(device.replace("video", ""))
    cam = cv2.VideoCapture(index)

    if not cam.isOpened():
        print("Cannot open the selected device", file=sys.stderr)
        return None

    # Discard the frames for 4 seconds
    tmax = time.time() + 4
    while time.time() < tmax:
        if not cam.grab():
            print("Cannot read from the selected device", file=sys.stderr)
            return None

    # Get the image
    result, image = cam.read()
    cam.release()
    if not result:
        print("Cannot read from the selected device", file=sys.stderr)
        return None

    return image


def brisque(device: str = "video0", file: str = "", save: bool = False):
    """
    Captures an image to a file and computes the quality using the
    Blinded/Unreferenced Spatial Image Quality Evaluator (BRISQUE). If the
    score is below a certain threshold, the test passes.
    """

    brisque = BRISQUE()
    if file:
        score = brisque.score(file)

    else:
        image = get_image_from_device(device)
        if image is None:
            return 1

        # Create a temporary file
        f = NamedTemporaryFile(
            prefix="camera_test_brisque_%s_" % device,
            suffix=".jpg",
            delete=not save,
        )
        cv2.imwrite(f.name, image)
        if save:
            print("Image saved to %s" % f.name)

        # Compute the BRISQUE score
        score = brisque.score(f.name)
        f.close()

    if isnan(score):
        print("Unable to compute BRISQUE score", file=sys.stderr)
        return 1
    elif score > THRESHOLD:
        print("The BRISQUE score is too high: %s" % score, file=sys.stderr)
        return 1

    print("BRISQUE score: %s" % score)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the image quality test")
    parser.add_argument(
        "-d", "--device", default="video0", help="Device for the webcam to use"
    )
    parser.add_argument(
        "-f", "--file", default="", help="Parse a file instead of a device"
    )
    parser.add_argument(
        "-s",
        "--save",
        action="store_true",
        help="Keep the image file after the test",
    )
    args = parser.parse_args()

    sys.exit(brisque(args.device, args.file, args.save))
