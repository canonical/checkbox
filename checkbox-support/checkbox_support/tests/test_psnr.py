import unittest
import numpy as np
from unittest.mock import patch, MagicMock
from argparse import Namespace
from io import StringIO

from checkbox_support.scripts.psnr import (
    main,
    psnr_args,
    _get_psnr,
    get_average_psnr,
    _get_frame_resolution,
)


def create_image_helper_function(width, height, color):
    """Creates an image with the specified color."""
    return np.full((height, width, 3), color, dtype=np.uint8)


class TestPSNRArgs(unittest.TestCase):

    def test_psnr_args_with_defaults(self):
        with patch(
            "sys.argv",
            ["psnr.py", "ref.mp4", "test.mp4"],
        ):
            args = psnr_args().parse_args()
            self.assertEqual(args.reference_file, "ref.mp4")
            self.assertEqual(args.test_file, "test.mp4")
            self.assertFalse(args.show_psnr_each_frame)

    @patch("checkbox_support.scripts.psnr.argparse.ArgumentParser.parse_args")
    def test_psnr_args_with_custom_args(self, mock_parse_args):
        mock_parse_args.return_value = Namespace(
            reference_file="ref.jpg",
            test_file="test.jpg",
            show_psnr_each_frame=True,
        )

        args = psnr_args().parse_args()

        self.assertEqual(args.reference_file, "ref.jpg")
        self.assertEqual(args.test_file, "test.jpg")
        self.assertTrue(args.show_psnr_each_frame)


class TestGetFrameResolution(unittest.TestCase):
    @patch("checkbox_support.scripts.psnr.cv2.VideoCapture")
    def test_get_frame_resolution(self, mock_videocapture):
        mock_capture = mock_videocapture.return_value
        mock_capture.get.side_effect = [100, 200]
        width, height = _get_frame_resolution(mock_capture)
        self.assertEqual(width, 100)
        self.assertEqual(height, 200)


class TestGetPSNR(unittest.TestCase):

    def create_image(self, width, height, color):
        """Creates an image with the specified color."""
        return np.full((height, width, 3), color, dtype=np.uint8)

    def test_identical_images(self):
        img1 = self.create_image(100, 100, 255)
        img2 = self.create_image(100, 100, 255)
        self.assertEqual(_get_psnr(img1, img2), 0.0)

    def test_different_images(self):
        img1 = self.create_image(100, 100, 255)
        img2 = self.create_image(100, 100, 0)
       self.assertNotEqual(_get_psnr(img1, img2), 0.0)
       self.assertLessEqual(_get_psnr(img1, img2), 50.0)


class TestGetAveragePSNR(unittest.TestCase):
    @patch("checkbox_support.scripts.psnr.cv2.VideoCapture")
    def test_get_average_psnr_file_not_found(self, mock_vc):
        mock_vc.return_value.isOpened.return_value = False
        with self.assertRaises(SystemExit):
            get_average_psnr("nonexistent_file.mp4", "test_file.mp4")

    @patch("checkbox_support.scripts.psnr.cv2.VideoCapture")
    def test_zero_frames(self, mock_vc):
        mock_vc.return_value.isOpened.return_value = True
        mock_vc.return_value.get.return_value = 0  # Zero frames in the video
        with self.assertRaises(SystemExit):
            get_average_psnr("ref.mp4", "test.mp4")

        with self.assertRaises(SystemExit):
            get_average_psnr("ref.mp4", "test.mp4")

    @patch("checkbox_support.scripts.psnr._get_frame_resolution")
    @patch("checkbox_support.scripts.psnr.cv2.VideoCapture")
    def test_get_average_psnr_different_dimensions(
        self, mock_vc, mock_get_frame_resolution
    ):
        mock_vc.return_value.isOpened.return_value = True
        mock_get_frame_resolution.side_effect = [(100, 100), (100, 150)]

        with self.assertRaises(SystemExit):
            get_average_psnr("ref_file.mp4", "test_file.mp4")

    @patch("checkbox_support.scripts.psnr.cv2.VideoCapture")
    @patch("checkbox_support.scripts.psnr._get_psnr")
    @patch("checkbox_support.scripts.psnr._get_frame_resolution")
    def test_get_average_psnr(
        self, mock_get_frame_resolution, mock_get_psnr, mock_VideoCapture
    ):
        # Create a mock VideoCapture object
        mock_video_capture = MagicMock()
        mock_VideoCapture.return_value = mock_video_capture

        # Mock the behavior of isOpened()
        mock_video_capture.isOpened.return_value = True

        # Mock the frame resolution getter
        mock_video_capture.get.return_value = 10
        mock_video_capture.read.side_effect = [
            (True, create_image_helper_function(100, 100, 255))
        ] * 20

        # Mock _get_psnr to return a specific value
        mock_get_psnr.return_value = 30.0

        avg_psnr, psnr_each_frame = get_average_psnr("ref.mp4", "test.mp4")

        self.assertEqual(avg_psnr, 30.0)
        self.assertEqual(psnr_each_frame, [30.0] * 10)


class TestMainFunction(unittest.TestCase):

    @patch("sys.stdout", new_callable=StringIO)
    @patch("checkbox_support.scripts.psnr.get_average_psnr")
    @patch("checkbox_support.scripts.psnr.argparse.ArgumentParser.parse_args")
    def test_main_prints_avg_psnr(
        self, mock_parse_args, mock_get_average_psnr, mock_stdout
    ):
        mock_parse_args.return_value = Namespace(
            reference_file="ref.mp4",
            test_file="test.mp4",
            show_psnr_each_frame=False,
        )

        mock_get_average_psnr.return_value = (30.0, [28.5, 31.2, 29.8])

        main()

        expected_output = "Average PSNR:  30.0\n"
        self.assertEqual(mock_stdout.getvalue(), expected_output)
        mock_get_average_psnr.assert_called_once_with("ref.mp4", "test.mp4")

    @patch("sys.stdout", new_callable=StringIO)
    @patch("checkbox_support.scripts.psnr.get_average_psnr")
    @patch("checkbox_support.scripts.psnr.argparse.ArgumentParser.parse_args")
    def test_main_prints_psnr_each_frame(
        self, mock_parse_args, mock_get_average_psnr, mock_stdout
    ):
        mock_parse_args.return_value = Namespace(
            reference_file="ref_file",
            test_file="test_file",
            show_psnr_each_frame=True,
        )

        mock_get_average_psnr.return_value = (30.0, [28.5, 31.2, 29.8])

        main()

        expected_output = (
            "Average PSNR:  30.0\nPSNR each frame:  [28.5, 31.2, 29.8]\n"
        )
        self.assertEqual(mock_stdout.getvalue(), expected_output)
        mock_get_average_psnr.assert_called_once_with("ref_file", "test_file")


if __name__ == "__main__":
    unittest.main()
