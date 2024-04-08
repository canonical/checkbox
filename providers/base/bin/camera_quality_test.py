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
from collections import deque
import logging
import os
import time
import sys

import cv2
import numpy as np

from checkbox_support.vendor.brisque.brisque import BRISQUE
from checkbox_support.helpers.timeout import timeout


THRESHOLD = 60
TIMEOUT = 10
MIN_INTERVAL = 0.5

logger = logging.getLogger("camera_quality_test")


def save_image(image: np.ndarray, device: str, output: str):
    """Saves the image from a video device to a the output directory.

    Args:
        image (np.ndarray): image to save
        device (str): name of the video device
        output (str): output directory
    """
    filepath = os.path.join(output, "quality_image_{}.jpg".format(device))
    # Check if the output directory exists
    if not os.path.exists(output):
        msg = "Output directory does not exist: {}".format(output)
        raise RuntimeError(msg)
    if not cv2.imwrite(filepath, image):
        msg = "Error while saving the image"
        raise RuntimeError(msg)
    print("Saved image to {}".format(filepath))


def get_score_from_device(device: str, output: str = "") -> float:
    """
    "This function calculates the BRISQUE score for images captured by a
    specified device within a given time window. If the score stabilizes
    during this period, the function returns this stable value. If the score
    does not stabilize within the time window, the function will return the
    last computed score."

    :param device:
        The device to use for the webcam
    :return:
        The BRISQUE score for the image
    :raises RuntimeError:
        If the device cannot be opened or read
    """
    brisque = BRISQUE()

    # Set the video device
    index = int(device.replace("video", ""))
    cam = cv2.VideoCapture(index)

    if not cam.isOpened():
        msg = "Cannot open the selected device: {}".format(device)
        raise RuntimeError(msg)

    # Compute the score for some time and check if it stabilizes
    scores = deque(maxlen=4)
    tmax = time.time() + TIMEOUT
    iter_count = 0

    # We compute the score for at most TIMEOUT seconds. If the computation is
    # too slow, we iterate at least two times.
    while time.time() < tmax or iter_count < 2:
        # Compute the time for each iteration
        start_compute = time.time()

        # Compute the score
        result, image = cam.read()
        if not result:
            msg = "Cannot read from the selected device: {}".format(device)
            raise RuntimeError(msg)
        score = brisque.score(image)

        compute_time = time.time() - start_compute

        # If the computation time is smaller than the minimum interval for
        # this iteration, we wait for the remaining time to have enough
        # time between iterations.
        if compute_time < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - compute_time)

        # If the deviation of the scores is low enough for the last 4
        # iterations, we can stop.
        if len(scores) == 4 and np.std(scores) < 0.5:
            break

        scores.append(score)
        iter_count += 1

    if output:
        save_image(image, device, output)

    # Release the video device
    cam.release()
    return score


def evaluate_score(score: float) -> int:
    """
    Evaluate the BRISQUE score for an image and checks if it is below the
    threshold value.

    :param score:
        The BRISQUE score to be evaluated
    :returns:
        0 if the test passes, 1 otherwise
    """

    if np.isnan(score):
        msg = "Unable to compute BRISQUE score"
        logger.error(msg)
        return 1

    elif score > THRESHOLD:
        msg = "The BRISQUE score is too high: {} > {}".format(score, THRESHOLD)
        logger.error(msg)
        return 1

    print("BRISQUE score: {}".format(score))
    return 0


@timeout(120)
def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description="Run the image quality test")
    parser.add_argument(
        "-d", "--device", default="video0", help="Device for the webcam to use"
    )
    parser.add_argument(
        "-f", "--file", default="", help="Parse a file instead of a device"
    )
    parser.add_argument("-o", "--output", default="", help="Output directory")

    args = parser.parse_args(argv)

    if args.file:
        img = cv2.imread(args.file)
        brisque = BRISQUE()
        score = brisque.score(img)
    else:
        score = get_score_from_device(args.device, args.output)

    return evaluate_score(score)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
