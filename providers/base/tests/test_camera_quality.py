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
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

import cv2
import numpy as np

import camera_quality_test as cqt


default_dir = Path(__file__).parent.joinpath("../data")
data_dir = Path(os.getenv("PLAINBOX_PROVIDER_DATA", default=default_dir))

score_path = "checkbox_support.vendor.brisque.brisque.BRISQUE.score"


@patch("camera_quality_test.TIMEOUT", new=0.05)
@patch("camera_quality_test.MIN_INTERVAL", new=0.01)
@patch("builtins.print", new=MagicMock())
class CameraQualityTests(unittest.TestCase):
    """This class provides test cases for the camera_quality_test module."""

    # Setup the patch for all the tests
    def setUp(self):
        # Patch the VideoCapture
        self.cv_patcher = patch("cv2.VideoCapture")
        self.mock_capture = self.cv_patcher.start()
        self.img_path = str(data_dir / "images/image_quality_good.jpg")
        self.img = cv2.imread(self.img_path)

    def tearDown(self):
        self.cv_patcher.stop()

    @patch(score_path)
    def test_get_score_from_file(self, mock_score):
        """
        The test should pass if a good image is read from a file.
        """
        mock_score.return_value = 10

        result = cqt.main(["-f", self.img_path])
        self.assertEqual(result, 0)
        self.assertTrue(mock_score.called)

    @patch("camera_quality_test.get_score_from_device")
    def test_get_score_from_device(self, mock_score):
        """
        The test should pass if a good image is read from a device.
        """
        mock_score.return_value = 10

        result = cqt.main(["-d", "video0"])
        self.assertEqual(result, 0)
        mock_score.assert_called_with("video0")

    @patch("logging.Logger.error", new=MagicMock())
    def test_quality_evaluation(self):
        """
        The test should pass if the image is good and fails if it has bad
        quality.
        """

        result = cqt.main(["-f", self.img_path])
        self.assertEqual(result, 0, "Good image should pass the test")

        bad_img_path = str(data_dir / "images/image_quality_bad.jpg")
        result = cqt.main(["-f", bad_img_path])
        self.assertEqual(result, 1, "Bad quality image should fail the test")

        plain_img_path = str(data_dir / "images/image_quality_plain.jpg")
        result = cqt.main(["-f", plain_img_path])
        self.assertEqual(result, 1, "Plain image should fail the test")

    def test_device_not_opened(self):
        """
        The test should fail if the camera device is not opened.
        """

        self.mock_capture.return_value.isOpened.return_value = False
        self.assertRaises(RuntimeError, cqt.get_score_from_device, "video0")

    def test_image_not_read(self):
        """
        The test should fail if the camera cannot read an image.
        """

        self.mock_capture.return_value.isOpened.return_value = True
        self.mock_capture.return_value.read.return_value = (False, None)

        self.assertRaises(RuntimeError, cqt.get_score_from_device, "video0")

    @patch(score_path)
    @patch("camera_quality_test.save_image", new=MagicMock())
    def test_stable_image_from_cam(self, mock_score):
        """
        The test should pass with a good still image.
        """

        self.mock_capture.return_value.isOpened.return_value = True
        self.mock_capture.return_value.read.return_value = (True, None)
        mock_score.return_value = 10

        self.assertEqual(cqt.get_score_from_device("video0"), 10)

    @patch(score_path)
    @patch("camera_quality_test.save_image", new=MagicMock())
    def test_unstable_image_from_cam(self, mock_score):
        """
        The test should pass with a good still image.
        """

        self.mock_capture.return_value.isOpened.return_value = True
        self.mock_capture.return_value.read.return_value = (True, None)
        mock_score.side_effect = [10, 20, 10, 20, 10, 10]

        self.assertEqual(cqt.get_score_from_device("video0"), 10)

    @patch(score_path)
    @patch("camera_quality_test.save_image", new=MagicMock())
    def test_slow_brisque_calculation(self, mock_score):
        """
        The test should iterate at least two times even if the computation time
        is longer than the timeout.
        """

        self.mock_capture.return_value.isOpened.return_value = True
        self.mock_capture.return_value.read.return_value = (True, None)
        mock_score.return_value = 10

        # Set the timeout and the min interval to 0 to force the iteration
        with patch("camera_quality_test.TIMEOUT", new=0.0), patch(
            "camera_quality_test.MIN_INTERVAL", new=0.0
        ):
            self.assertEqual(cqt.get_score_from_device("video0"), 10)
            self.assertEqual(mock_score.call_count, 2)

    @patch("cv2.imwrite")
    @patch("camera_quality_test.PLAINBOX_SESSION_SHARE", "/tmp")
    def test_save_image_with_sesion_share_defined(self, mock_imwrite):
        """
        The test should pass with a good still image.
        """
        # create an empty image
        img = np.zeros((100, 100, 3))
        cqt.save_image(img, "video0")
        mock_imwrite.assert_called_with("/tmp/quality_image_video0.jpg", img)

    @patch("cv2.imwrite")
    @patch("camera_quality_test.PLAINBOX_SESSION_SHARE", "")
    @patch("camera_quality_test.NamedTemporaryFile")
    def test_save_image_without_sesion_share_defined(
        self, mock_tempfile, mock_imwrite
    ):
        """
        The test should pass with a good still image.
        """
        # create an empty image
        img = []
        mock_tempfile.return_value.__enter__.return_value.name = (
            "/tmp/quality_image_video0.jpg"
        )
        cqt.save_image(img, "video0")
        mock_tempfile.assert_called_with(
            prefix="quality_image_video0", suffix=".jpg", delete=False
        )
        mock_imwrite.assert_called_with("/tmp/quality_image_video0.jpg", img)
