import unittest
from unittest.mock import patch, MagicMock
import tempfile
import os

from bin.gst_encoder_quality import (
    build_pipeline,
    validate_output,
    ENCODER_MAP,
    SUPPORTED_CODECS,
)


class TestBuildPipeline(unittest.TestCase):
    def test_build_pipeline_h264(self):
        pipeline = build_pipeline("h264", 1920, 1080, 30, 60, "/tmp/test.mkv")
        self.assertIn("gst-launch-1.0", pipeline)
        self.assertIn("videotestsrc", pipeline)
        self.assertIn("vah264enc", pipeline)
        self.assertIn("num-buffers=60", pipeline)

    def test_build_pipeline_h265(self):
        pipeline = build_pipeline("h265", 1280, 720, 60, 120, "/tmp/test.mkv")
        self.assertIn("vah265enc", pipeline)
        self.assertIn("num-buffers=120", pipeline)

    def test_build_pipeline_jpeg(self):
        pipeline = build_pipeline("jpeg", 1920, 1080, 30, 1, "/tmp/test.jpg")
        self.assertIn("jpegenc", pipeline)
        self.assertIn("num-buffers=1", pipeline)
        self.assertIn("framerate=1/1", pipeline)

    def test_build_pipeline_av1(self):
        pipeline = build_pipeline("av1", 1920, 1080, 30, 60, "/tmp/test.mkv")
        self.assertIn("vaav1enc", pipeline)

    def test_all_codecs_have_pipeline(self):
        for codec in SUPPORTED_CODECS:
            with self.subTest(codec=codec):
                pipeline = build_pipeline(
                    codec, 640, 480, 30, 10, "/tmp/test.mkv"
                )
                self.assertIn(ENCODER_MAP[codec], pipeline)

    def test_pipeline_includes_caps(self):
        pipeline = build_pipeline("h264", 1920, 1080, 30, 60, "/tmp/test.mkv")
        self.assertIn("video/x-raw", pipeline)
        self.assertIn("width=1920", pipeline)
        self.assertIn("height=1080", pipeline)
        self.assertIn("framerate=30/1", pipeline)


class TestValidateOutput(unittest.TestCase):
    def test_validate_output_exists(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test data")
            path = f.name
        try:
            self.assertTrue(validate_output(path))
        finally:
            os.unlink(path)

    def test_validate_output_empty(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            self.assertFalse(validate_output(path))
        finally:
            os.unlink(path)

    def test_validate_output_not_found(self):
        self.assertFalse(validate_output("/nonexistent/file.mkv"))


class TestMain(unittest.TestCase):
    @patch("bin.gst_encoder_quality.subprocess.run")
    @patch("bin.gst_encoder_quality.validate_output")
    @patch("bin.gst_encoder_quality.tempfile.mktemp")
    @patch("bin.gst_encoder_quality.os.unlink")
    def test_main_success(
        self, mock_unlink, mock_mktemp, mock_validate, mock_run
    ):
        mock_mktemp.return_value = "/tmp/test_output.mkv"
        mock_run.return_value = MagicMock(returncode=0)
        mock_validate.return_value = True

        from bin.gst_encoder_quality import main
        import sys

        sys.argv = ["gst_encoder_quality.py", "--codec", "h264"]

        main()
        mock_run.assert_called_once()
        mock_validate.assert_called_once_with("/tmp/test_output.mkv")
        mock_unlink.assert_called_once_with("/tmp/test_output.mkv")

    @patch("bin.gst_encoder_quality.subprocess.run")
    @patch("bin.gst_encoder_quality.validate_output")
    def test_main_pipeline_failure(self, mock_validate, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="error"
        )

        from bin.gst_encoder_quality import main
        import sys

        sys.argv = ["gst_encoder_quality.py", "--codec", "h264"]

        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)

    @patch("bin.gst_encoder_quality.subprocess.run")
    @patch("bin.gst_encoder_quality.validate_output")
    def test_main_validation_failure(self, mock_validate, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        mock_validate.return_value = False

        from bin.gst_encoder_quality import main
        import sys

        sys.argv = ["gst_encoder_quality.py", "--codec", "h264"]

        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
