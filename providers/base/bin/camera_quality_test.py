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
from tempfile import NamedTemporaryFile


THRESHOLD = 60
TIMEOUT = 10
MIN_INTERVAL = 0.5
PLAINBOX_SESSION_SHARE = os.environ.get("PLAINBOX_SESSION_SHARE", "")

logger = logging.getLogger("camera_quality_test")


def save_image(image: np.ndarray, device: str):
    """Saves the image to the PLAINBOX_SESSION_SHARE directory if is set,
    otherwise it saves the image to a temporary file.

    Args:
        image (np.ndarray): image to save
        device (str): name of the video device

    """
    if PLAINBOX_SESSION_SHARE:
        filepath = os.path.join(
            PLAINBOX_SESSION_SHARE, "quality_image_{}.jpg".format(device)
        )
        cv2.imwrite(filepath, image)
        print("Saved image to {}".format(filepath))
    else:
        with NamedTemporaryFile(
            prefix="quality_image_{}".format(device),
            suffix=".jpg",
            delete=False,
        ) as f:
            cv2.imwrite(f.name, image)
            print("Saved image to {}".format(f.name))


def get_score_from_device(device: str, save: bool = False) -> float:
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

    save_image(image, device)

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

    args = parser.parse_args(argv)

    if args.file:
        img = cv2.imread(args.file)
        brisque = BRISQUE()
        score = brisque.score(img)
    else:
        score = get_score_from_device(args.device)

    return evaluate_score(score)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
