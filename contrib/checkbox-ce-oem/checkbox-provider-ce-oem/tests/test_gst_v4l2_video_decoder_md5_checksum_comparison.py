import logging
import sys
import subprocess
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock, mock_open, call
from gst_v4l2_video_decoder_md5_checksum_comparison import (
    build_gst_command,
    extract_the_md5_checksum,
    get_md5_checksum_from_command,
    validate_video_decoder_md5_checksum
)


class TestBuildGstCommand(unittest.TestCase):
    def test_build_gst_command_vp8_vp9_decoder(self):
        # Test case 1: VP8/VP9 decoder
        gst_bin = "gst-launch-1.0"
        golden_sample_path = "/path/to/golden/sample.mp4"
        decoder = "v4l2vp8dec"
        color_space = "I420"

        expected_command = (
            "gst-launch-1.0 -v filesrc location=/path/to/golden/sample.mp4 ! "
            "parsebin ! v4l2vp8dec ! v4l2convert ! "
            "checksumsink hash=0 sync=false"
        )
        command = build_gst_command(
            gst_bin, golden_sample_path, decoder, color_space
        )
        self.assertEqual(command, expected_command)

    def test_build_gst_command_other_decoder(self):
        gst_bin = "gst-launch-1.0"
        golden_sample_path = "/path/to/golden/sample.mp4"
        decoder = "v4l2h264dec"
        color_space = "NV12"

        expected_command = (
            "gst-launch-1.0 -v filesrc location=/path/to/golden/sample.mp4 ! "
            "parsebin ! v4l2h264dec ! v4l2convert ! "
            "video/x-raw,format=NV12 ! checksumsink hash=0 sync=false"
        )
        command = build_gst_command(
            gst_bin, golden_sample_path, decoder, color_space
        )
        self.assertEqual(command, expected_command)


class TestExtractTheMD5Checksum(unittest.TestCase):
    def test_extract_the_md5_checksum_multiple(self):
        input_str = """
Pipeline is PREROLLED ...
Setting pipeline to PLAYING ...
Redistribute latency...
New clock: GstSystemClock
0:00:00.000000000 00402d37c1a1c9a887cf8c06e1046489
0:00:00.033333333 52e92b8dbafc0ed038e89d0196326c57
0:00:00.066666666 6f9edba153b10ffc17a14ac0b8eade4f
0:00:00.100000000 2981ace12393b0e89b1e0a44698c5df8
0:00:00.133333333 6286c1207577e76dc690715669a4d890
Got EOS from element "pipeline0".
Execution ended after 0:00:00.768310428
Setting pipeline to NULL ...
Freeing pipeline ...
"""
        expected_output = "\n".join([
            "00402d37c1a1c9a887cf8c06e1046489",
            "52e92b8dbafc0ed038e89d0196326c57",
            "6f9edba153b10ffc17a14ac0b8eade4f",
            "2981ace12393b0e89b1e0a44698c5df8",
            "6286c1207577e76dc690715669a4d890\n",
        ])
        actual_output = extract_the_md5_checksum(input_str)
        self.assertEqual(actual_output, expected_output)

    def test_extract_the_md5_checksum_none(self):
        input_str = "This is a string without any MD5 checksums."
        expected_output = ""
        actual_output = extract_the_md5_checksum(input_str)
        self.assertEqual(actual_output, expected_output)


class TestGetMD5ChecksumFromCommand(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_stdout = sys.stdout
        suppress_text = StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        sys.stdout = cls.original_stdout
        logging.disable(logging.NOTSET)

    @patch(
        "gst_v4l2_video_decoder_md5_checksum_comparison."
        "extract_the_md5_checksum"
    )
    @patch("subprocess.run")
    def test_get_md5_checksum_from_command_success(
        self,
        mock_subprocess_run,
        mock_extract_the_md5_checksum
    ):
        cmd = "123 success command"
        expected_md5_checksum = "fake md5 12345abcf35"
        mock_extract_the_md5_checksum.return_value = expected_md5_checksum

        mock_subprocess_run.return_value = MagicMock(
            returncode=0,
            stdout="0:00:00.000000000 = fake md5 12345abcf35"
        )

        md5_checksum = get_md5_checksum_from_command(cmd)

        self.assertEqual(md5_checksum, expected_md5_checksum)
        mock_extract_the_md5_checksum.assert_called_once_with(
            mock_subprocess_run.return_value.stdout
        )
        mock_subprocess_run.assert_called_once_with(
            ["123", "success", "command"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", timeout=30
        )

    @patch("subprocess.run")
    def test_get_md5_checksum_from_command_failure(self, mock_subprocess_run):
        cmd = "Failure Command"

        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            returncode=100, cmd=cmd, stderr="Command failed"
        )

        with self.assertRaises(SystemExit) as cm:
            get_md5_checksum_from_command(cmd)
        self.assertEqual(cm.exception.code, 100)
        mock_subprocess_run.assert_called_once_with(
            ["Failure", "Command"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", timeout=30
        )


class TestValidateVideoDecoderMD5Checksum(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_stdout = sys.stdout
        suppress_text = StringIO()
        sys.stdout = suppress_text
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        sys.stdout = cls.original_stdout
        logging.disable(logging.NOTSET)

    @patch("os.path.exists")
    @patch(
        "gst_v4l2_video_decoder_md5_checksum_comparison."
        "build_gst_command"
    )
    @patch(
        "gst_v4l2_video_decoder_md5_checksum_comparison."
        "get_md5_checksum_from_command"
    )
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="golden_md5_checksum"
    )
    def test_validate_video_decoder_md5_checksum_success(
        self,
        mock_open,
        mock_get_md5_checksum_from_command,
        mock_build_gst_command,
        mock_os_path_exists
    ):
        args = type("", (), {
            "golden_sample_path": "golden_sample.mp4",
            "golden_sample_md5_checksum_path": "my_test.md5",
            "decoder_plugin": "fake_decoder",
            "color_space": "NN"
        })()

        mock_os_path_exists.side_effect = [True, True]
        mock_get_md5_checksum_from_command.return_value = "golden_md5_checksum"
        mock_build_gst_command.return_value = "my testing command"

        validate_video_decoder_md5_checksum(args)

        mock_os_path_exists.assert_has_calls([
            call("golden_sample.mp4"),
            call("my_test.md5")
        ])
        mock_get_md5_checksum_from_command.assert_called_once_with(
            "my testing command"
        )
        mock_open.assert_called_once_with(
            "my_test.md5", mode="r", encoding="UTF-8")

    @patch("os.path.exists")
    @patch(
        "gst_v4l2_video_decoder_md5_checksum_comparison."
        "get_md5_checksum_from_command"
    )
    @patch("builtins.open", new_callable=mock_open)
    def test_validate_video_decoder_md5_checksum_golden_sample_not_found(
        self,
        mock_open,
        mock_get_md5_checksum_from_command,
        mock_os_path_exists
    ):
        # Arrange
        args = type("", (), {
            "golden_sample_path": "non_exist_golden_sample.mp4",
            "golden_sample_md5_checksum_path": "golden_sample.md5",
            "decoder_plugin": "fake_decoder",
            "color_space": "NN"
        })()

        mock_os_path_exists.side_effect = [False]

        # Act and Assert
        with self.assertRaises(SystemExit) as cm:
            validate_video_decoder_md5_checksum(args)
        self.assertEqual(
            cm.exception.code,
            "Golden Sample 'non_exist_golden_sample.mp4' doesn't exist"
        )
        mock_os_path_exists.assert_has_calls([
            call("non_exist_golden_sample.mp4")
        ])
        mock_get_md5_checksum_from_command.assert_not_called()
        mock_open.assert_not_called()

    @patch("os.path.exists")
    @patch(
        "gst_v4l2_video_decoder_md5_checksum_comparison."
        "get_md5_checksum_from_command"
    )
    @patch("builtins.open", new_callable=mock_open)
    def test_validate_video_decoder_md5_checksum_golden_md5_checksum_not_found(
        self,
        mock_open,
        mock_get_md5_checksum_from_command,
        mock_os_path_exists
    ):
        args = type("", (), {
            "golden_sample_path": "golden_sample.mp4",
            "golden_sample_md5_checksum_path": "non_exist_golden_sample.md5",
            "decoder_plugin": "fake_decoder",
            "color_space": "NN"
        })()

        mock_os_path_exists.side_effect = [True, False]

        with self.assertRaises(SystemExit) as cm:
            validate_video_decoder_md5_checksum(args)
        self.assertEqual(
            cm.exception.code,
            ("Golden Sample's MD5 checksum 'non_exist_golden_sample.md5'"
             " doesn't exist")
        )
        mock_os_path_exists.assert_has_calls([
            call("golden_sample.mp4"),
            call("non_exist_golden_sample.md5")
        ])
        mock_get_md5_checksum_from_command.assert_not_called()
        mock_open.assert_not_called()

    @patch("os.path.exists")
    @patch(
        "gst_v4l2_video_decoder_md5_checksum_comparison."
        "build_gst_command"
    )
    @patch(
        "gst_v4l2_video_decoder_md5_checksum_comparison."
        "get_md5_checksum_from_command"
    )
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="different_golden_md5_checksum"
    )
    def test_validate_video_decoder_md5_checksum_failure(
        self,
        mock_open,
        mock_get_md5_checksum_from_command,
        mock_build_gst_command,
        mock_os_path_exists
    ):
        args = type("", (), {
            "golden_sample_path": "golden_sample.mp4",
            "golden_sample_md5_checksum_path": "golden_sample.md5",
            "decoder_plugin": "fake_decoder",
            "color_space": "NN"
        })()

        mock_os_path_exists.side_effect = [True, True]
        mock_get_md5_checksum_from_command.return_value = "md5_checksum"
        mock_build_gst_command.return_value = "my testing command"

        # Act and Assert
        with self.assertRaises(SystemExit) as cm:
            validate_video_decoder_md5_checksum(args)
        self.assertEqual(
            cm.exception.code,
            "Failed. MD5 checksum is not same as Golden Sample"
        )
        mock_os_path_exists.assert_has_calls([
            call("golden_sample.mp4"),
            call("golden_sample.md5")
        ])
        mock_get_md5_checksum_from_command.assert_called_once_with(
            "my testing command"
        )
        mock_open.assert_called_once_with(
            "golden_sample.md5",
            mode="r",
            encoding="UTF-8"
        )


if __name__ == "__main__":
    unittest.main()
