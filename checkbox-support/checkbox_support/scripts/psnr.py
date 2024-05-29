#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
# Written by:
#   Patrick Chang <patrick.chang@canonical.com>
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
# Reference the PSNR algorithm below
# - https://docs.opencv.org/3.4/d5/dc4/tutorial_video_input_psnr_ssim.html

import cv2
import numpy as np
import argparse
from typing import Tuple, List


def psnr_args() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser for the PSNR calculation script.

    Returns:
        ArgumentParser: The configured argument parser
    """
    parser = argparse.ArgumentParser(
        description=(
            "Calculate PSNR between two files." " File can be image or video."
        )
    )
    parser.add_argument(
        "reference_file", type=str, help="Path to the reference file"
    )
    parser.add_argument("test_file", type=str, help="Path to the test file")
    parser.add_argument(
        "-s",
        "--show_psnr_each_frame",
        action="store_true",
        default=False,
        help="Absolutely always show command output",
    )
    return parser


def _get_psnr(I1: np.ndarray, I2: np.ndarray) -> float:
    """
    Calculate the Peak Signal-to-Noise Ratio (PSNR) between two frames.

    Args:
        I1 (np.ndarray): Reference frame.
        I2 (np.ndarray): Frame to be compared with the reference.

    Returns:
        float: PSNR value indicating the quality of I2 compared to I1.
    """
    # Calculate the absolute difference
    s1 = cv2.absdiff(I1, I2)
    # cannot make a square on 8 bits
    s1 = np.float32(s1)
    # Calculate squared differences
    s1 = s1 * s1
    # Sum of squared differences per channel
    sse = s1.sum()
    # sum channels
    if sse <= 1e-10:
        # for small values return zero
        return 0.0
    else:
        shape = I1.shape
        mse = 1.0 * sse / (shape[0] * shape[1] * shape[2])
        psnr = 10.0 * np.log10((255 * 255) / mse)
    return psnr


def _get_frame_resolution(capture) -> Tuple[int, int]:
    return (
        int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    )


def get_average_psnr(
    reference_file_path: str, test_file_path: str
) -> Tuple[float, List[float]]:
    """
    Calculate the average PSNR and PSNR for each frame between two files.
    Files can be image or video.

    Args:
        reference_file_path (str): Path to the reference file.
        test_file_path (str): Path to the test file.

    Returns:
        Tuple[float, List[float]]: A tuple containing the average PSNR value
        and a list of PSNR values for each frame.
    """
    capt_refrnc = cv2.VideoCapture(reference_file_path)
    capt_undTst = cv2.VideoCapture(test_file_path)

    if not capt_refrnc.isOpened() or not capt_undTst.isOpened():
        raise SystemExit("Error: Could not open reference or test file.")

    ref_size = _get_frame_resolution(capt_refrnc)
    test_size = _get_frame_resolution(capt_undTst)

    if ref_size != test_size:
        raise SystemExit("Error: Files have different dimensions.")

    total_frame_count = int(capt_refrnc.get(cv2.CAP_PROP_FRAME_COUNT))
    avg_psnr = 0.0
    psnr_each_frame = []

    for _ in range(total_frame_count):
        _, frameReference = capt_refrnc.read()
        _, frameUnderTest = capt_undTst.read()
        psnr = _get_psnr(frameReference, frameUnderTest)
        psnr_each_frame.append(psnr)
        avg_psnr += psnr

    avg_psnr /= total_frame_count
    return avg_psnr, psnr_each_frame


def main() -> None:
    args = psnr_args().parse_args()
    avg_psnr, psnr_each_frame = get_average_psnr(
        args.reference_file, args.test_file
    )
    print("Average PSNR: ", avg_psnr)
    if args.show_psnr_each_frame:
        print("PSNR each frame: ", psnr_each_frame)


if __name__ == "__main__":
    main()
