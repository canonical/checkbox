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
            args = psnr_args()
            self.assertEqual(args.reference_file, "ref.mp4")
            self.assertEqual(args.test_file, "test.mp4")
            self.assertFalse(args.show_psnr_each_frame)

    def test_psnr_args_with_custom_args(self):
        with patch(
            "sys.argv",
            ["psnr.py", "ref.mp4", "test.mp4", "-s"],
        ):
            args = psnr_args()
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

    @patch("checkbox_support.scripts.psnr._get_psnr")
    @patch("checkbox_support.scripts.psnr._get_frame_resolution")
    @patch("checkbox_support.scripts.psnr.cv2.VideoCapture")
    def test_get_average_psnr(
        self, mock_VideoCapture, mock_get_frame_resolution, mock_get_psnr
    ):
        # Setup
        reference_file_path = "reference.mp4"
        test_file_path = "test.mp4"
        total_frame_count = 5
        mock_capt_refrnc = MagicMock()
        mock_capt_undTst = MagicMock()

        mock_VideoCapture.side_effect = [mock_capt_refrnc, mock_capt_undTst]

        mock_capt_refrnc.isOpened.return_value = True
        mock_capt_undTst.isOpened.return_value = True

        mock_get_frame_resolution.return_value = (1920, 1080)

        mock_capt_refrnc.get.return_value = total_frame_count

        mock_capt_refrnc.read.return_value = (True, "frameReference")
        mock_capt_undTst.read.return_value = (True, "frameUnderTest")

        mock_get_psnr.return_value = 30

        # Code under test
        avg_psnr, psnr_array = get_average_psnr(
            reference_file_path, test_file_path
        )

        # Assertions
        expected_psnr_array = np.array([30] * total_frame_count)
        expected_avg_psnr = np.mean(expected_psnr_array)

        self.assertEqual(len(psnr_array), total_frame_count)
        self.assertTrue(np.array_equal(psnr_array, expected_psnr_array))
        self.assertEqual(avg_psnr, expected_avg_psnr)

        # Ensure mocks were called correctly
        mock_VideoCapture.assert_any_call(reference_file_path)
        mock_VideoCapture.assert_any_call(test_file_path)
        self.assertEqual(mock_capt_refrnc.isOpened.call_count, 1)
        self.assertEqual(mock_capt_undTst.isOpened.call_count, 1)
        self.assertEqual(mock_get_frame_resolution.call_count, 2)
        self.assertEqual(mock_capt_refrnc.get.call_count, 1)
        self.assertEqual(mock_capt_refrnc.read.call_count, total_frame_count)
        self.assertEqual(mock_capt_undTst.read.call_count, total_frame_count)
        self.assertEqual(mock_get_psnr.call_count, total_frame_count)


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
