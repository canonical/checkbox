#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
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

import os
import unittest
from unittest.mock import patch

import cv2

from bin.camera_quality_test import brisque

default_dir = os.path.join(os.path.dirname(__file__), "../data")
data_dir = os.getenv("PLAINBOX_PROVIDER_DATA", default=default_dir)


class CameraQualityTests(unittest.TestCase):
    """This class provides test cases for the camera_quality_test module."""

    # Setup the patch for all the tests
    def setUp(self):
        self.patcher = patch("cv2.VideoCapture")
        self.mock_capture = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_device_not_opened(self):
        """
        The test should fail if the camera device is not opened.
        """

        # Set the mock
        self.mock_capture.return_value.isOpened.return_value = False

        assert brisque() == 1

    def test_grab_not_available(self):
        """
        The test should fail if the camera device can't grab an image.
        """

        # Set the mock
        self.mock_capture.return_value.isOpened.return_value = True
        self.mock_capture.return_value.grab.return_value = False

        assert brisque() == 1

    def test_image_not_read(self):
        """
        The test should fail if the camera device can't read the image.
        """

        # Set the mock
        self.mock_capture.return_value.isOpened.return_value = True
        self.mock_capture.return_value.grab.return_value = True
        self.mock_capture.return_value.read.return_value = (False, None)

        assert brisque() == 1

    def test_good_image_from_camera(self):
        """
        Check if the test passes with a valid image.
        """
        # Set the mock
        img_path = os.path.join(data_dir, "images/image_quality_good.jpg")
        img = cv2.imread(img_path)
        self.mock_capture.return_value.isOpened.return_value = True
        self.mock_capture.return_value.grab.return_value = True
        self.mock_capture.return_value.read.return_value = (True, img)

        assert brisque() == 0
        assert brisque(save=True) == 0

    def test_good_image_from_file(self):
        """
        Check if the test passes with a valid image from a file.
        """

        img_path = os.path.join(data_dir, "images/image_quality_good.jpg")

        assert brisque(file=img_path) == 0

    def test_bad_image_from_file(self):
        """
        Check if the test fails with a bad image.
        """

        # Set the mock
        img_path = os.path.join(data_dir, "images/image_quality_bad.jpg")

        assert brisque(file=img_path) == 1

    def test_invalid_image_from_file(self):
        """
        Check if the test fails with a plain image.
        """

        # Set the mock
        img_path = os.path.join(data_dir, "images/image_quality_plain.jpg")

        assert brisque(file=img_path) == 1
