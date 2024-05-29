import unittest
import numpy as np
from unittest.mock import patch
from argparse import Namespace
from io import StringIO

from checkbox_support.scripts.psnr import (
    main,
    psnr_args,
    _get_psnr,
    get_average_psnr,
    _get_frame_resolution,
)


class TestPSNRArgs(unittest.TestCase):

    @patch("checkbox_support.scripts.psnr.argparse.ArgumentParser.parse_args")
    def test_psnr_args_with_defaults(self, mock_parse_args):
        mock_parse_args.return_value = Namespace(
            reference_file="ref.mp4",
            test_file="test.mp4",
            show_psnr_each_frame=False,
        )
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


class TestGetAveragePSNR(unittest.TestCase):
    def test_get_average_psnr_file_not_found(self):
        with patch(
            "checkbox_support.scripts.psnr.cv2.VideoCapture"
        ) as mock_videocapture:
            mock_capture = mock_videocapture.return_value
            mock_capture.isOpened.return_value = False
            with self.assertRaises(SystemExit):
                get_average_psnr("nonexistent_file.mp4", "test_file.mp4")

    @patch("checkbox_support.scripts.psnr._get_frame_resolution")
    @patch("checkbox_support.scripts.psnr.cv2.VideoCapture")
    def test_get_average_psnr_different_dimensions(
        self, mock_videocapture, mock_get_frame_resolution
    ):
        mock_capture_ref = mock_videocapture.return_value
        mock_capture_test = mock_videocapture.return_value
        mock_capture_test.isOpened.return_value = True
        mock_capture_ref.isOpened.return_value = True
        mock_get_frame_resolution.side_effect = [(100, 100), (100, 150)]

        with self.assertRaises(SystemExit) as cm:
            get_average_psnr("ref_file.mp4", "test_file.mp4")

        self.assertEqual(
            str(cm.exception), "Error: Files have different dimensions."
        )


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
