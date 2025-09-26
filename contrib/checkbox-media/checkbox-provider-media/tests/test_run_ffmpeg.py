#!/usr/bin/python3

import unittest
import os
from unittest.mock import patch
import subprocess

from run_ffmpeg import (
    has_profile_and_entrypoint,
    get_all_trace_contents,
    check_success,
    cleanup,
    run_ffmpeg,
    ffmpeg_encode_command,
    ffmpeg_decode_command,
    RESOURCES_DIR,
)


class TestRunFFmpeg(unittest.TestCase):
    def test_has_profile_and_entrypoint(self):

        cases = {
            "1 entry + prof": {
                "entrypoint": "1",
                "profile": "3",
                "entry_in_text": "1",
                "prof_in_text": "3",
                "expected_result": True,
            },
            "Multi entry + prof": {
                "entrypoint": "1,2,3,4,5",
                "profile": "3,7,11",
                "entry_in_text": "4",
                "prof_in_text": "7",
                "expected_result": True,
            },
            "Multi entry + 1 prof": {
                "entrypoint": "1,2,3,4,5",
                "profile": "11",
                "entry_in_text": "4",
                "prof_in_text": "11",
                "expected_result": True,
            },
            "1 entry + multi prof": {
                "entrypoint": "1",
                "profile": "3,7,11",
                "entry_in_text": "1",
                "prof_in_text": "3",
                "expected_result": True,
            },
            "multi entry + 1 prof": {
                "entrypoint": "1,2,3",
                "profile": "3",
                "entry_in_text": "3",
                "prof_in_text": "3",
                "expected_result": True,
            },
            "Wrong profile": {
                "entrypoint": "1",
                "profile": "11",
                "entry_in_text": "1",
                "prof_in_text": "7",
                "expected_result": False,
            },
            "No libva.trace text": {
                "entrypoint": "1",
                "profile": "11",
                "expected_result": False,
            },
        }

        all_tests_pass = True
        for case in cases:
            if "prof_in_text" in cases[case]:
                # sub in our text values for profile and entrypoint
                prof_in_text = cases[case]["prof_in_text"]
                entry_in_text = cases[case]["entry_in_text"]
                text = f"""
                This is a multiline string
                Which should contain the needed substrings
                entrypoint = {entry_in_text}
                to confirm hardware encode/decode
                profile = {prof_in_text}
                for single entrypoints and profiles
                """
            else:
                # The value returned by get_all_trace_contents if no traces
                text = ""

            profile = cases[case]["profile"]
            entrypoint = cases[case]["entrypoint"]
            result = has_profile_and_entrypoint(text, profile, entrypoint)

            expected_result = cases[case]["expected_result"]
            if result is expected_result:
                print(f"PASS: {case}")
            else:
                all_tests_pass = False
                print(f"FAIL: {case}")

        self.assertTrue(all_tests_pass)

    def test_get_all_trace_contents(self):
        test_file_num = 3
        base_phrase = "I test therefore I am"
        base_filename = "fake_libva.trace"

        control = []
        for i in range(test_file_num):
            filename = base_filename + f"{i}"
            phrase = base_phrase + f"{i}"
            with open(filename, "w") as f:
                f.write(phrase)
                # The newline is added to separate different traces
                control.append(phrase + "\n")

        # Test the expected lines are in the trace contents string
        result = get_all_trace_contents("./", trace_filename=base_filename)
        for line in control:
            self.assertIn(line, result)

        # Ensure duplicates are not added
        filelines = []
        for line in result.splitlines():
            filelines.append(line + "\n")

        self.assertEqual(set(filelines), set(control))

        # Remove test files
        for i in range(test_file_num):
            filename = base_filename + f"{i}"
            os.remove(filename)

        result = get_all_trace_contents("./", trace_filename=base_filename)

        # No trace files should return a blank string
        self.assertEqual(result, "")

    def test_cleanup(self):
        video_extensions = ["mp4", "mkv", "mpg", "yuv"]
        base_tracename = f"{RESOURCES_DIR}libva.trace"

        i = 0
        for extension in video_extensions:
            # Create empty video file
            open(f"output.{extension}", "w").close()
            # Create empty trace file
            open(base_tracename + f"{i}", "w").close()

            # Make sure the files exist now
            self.assertTrue(os.path.exists(f"output.{extension}"))
            self.assertTrue(base_tracename + f"{i}")
            i += 1

        cleanup()

        # Make sure the files do not exist anymore
        i = 0
        for extension in video_extensions:
            self.assertFalse(os.path.exists(f"output.{extension}"))
            self.assertFalse(os.path.exists(base_tracename + f"{i}"))
            i += 1

    @patch("run_ffmpeg.get_all_trace_contents")
    @patch("run_ffmpeg.has_profile_and_entrypoint")
    def test_check_success_succeeded_case(self, mock_has_pe, mock_get_trace):
        process = subprocess.CompletedProcess(
            args=["ffmpeg"], returncode=0, stdout="ffmpeg OK", stderr=""
        )

        mock_get_trace.return_value = "trace content"
        mock_has_pe.return_value = True

        result = check_success(process, "1", "1", "decode")
        self.assertTrue(result)

    @patch("run_ffmpeg.get_all_trace_contents")
    @patch("run_ffmpeg.has_profile_and_entrypoint")
    def test_check_success_hw_acceleration_not_detected(
        self, mock_has_pe, mock_get_trace
    ):
        process = subprocess.CompletedProcess(
            args=["ffmpeg"], returncode=0, stdout="ffmpeg OK", stderr=""
        )

        mock_get_trace.return_value = "trace content"
        mock_has_pe.return_value = False

        result = check_success(process, "1", "1", "encode")
        self.assertFalse(result)

    @patch("run_ffmpeg.get_all_trace_contents")
    @patch("run_ffmpeg.has_profile_and_entrypoint")
    def test_check_success_ffmpeg_command_failed(
        self, mock_has_pe, mock_get_trace
    ):
        process = subprocess.CompletedProcess(
            args=["ffmpeg"], returncode=1, stdout="output", stderr="error"
        )

        mock_get_trace.return_value = "trace content"
        mock_has_pe.return_value = True

        result = check_success(process, "1", "1", "decode")
        self.assertFalse(result)

    @patch("run_ffmpeg.check_success")
    @patch("run_ffmpeg.cleanup")
    @patch("run_ffmpeg.subprocess.run")
    def test_run_ffmpeg_decode_success(
        self, mock_run, mock_cleanup, mock_check_succ
    ):
        video_filepath = "filepath"
        libva_profile = "1"
        libva_entrypoint = "1"
        operation = "decode"

        mock_run.return_value = "ffmpeg output"
        mock_check_succ.return_value = True

        with self.assertRaises(SystemExit) as cm:
            run_ffmpeg(
                video_filepath, libva_profile, libva_entrypoint, operation
            )

        self.assertEqual(cm.exception.code, 0)

        mock_run.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch("run_ffmpeg.check_success")
    @patch("run_ffmpeg.cleanup")
    @patch("run_ffmpeg.subprocess.run")
    def test_run_ffmpeg_decode_failure(
        self, mock_run, mock_cleanup, mock_check_succ
    ):
        video_filepath = "filepath"
        libva_profile = "1"
        libva_entrypoint = "1"
        operation = "decode"

        mock_run.return_value = "ffmpeg output"
        mock_check_succ.return_value = False

        with self.assertRaises(SystemExit) as cm:
            run_ffmpeg(
                video_filepath, libva_profile, libva_entrypoint, operation
            )

        self.assertNotEqual(cm.exception.code, 0)

        mock_run.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch("run_ffmpeg.check_success")
    @patch("run_ffmpeg.cleanup")
    @patch("run_ffmpeg.subprocess.run")
    def test_run_ffmpeg_encode_success(
        self, mock_run, mock_cleanup, mock_check_succ
    ):
        video_filepath = "filepath"
        libva_profile = "1"
        libva_entrypoint = "1"
        operation = "encode"
        ffmpeg_output_codec = "VP9"
        output_container = "mp4"

        mock_run.return_value = "ffmpeg output"
        mock_check_succ.return_value = True

        with self.assertRaises(SystemExit) as cm:
            run_ffmpeg(
                video_filepath,
                libva_profile,
                libva_entrypoint,
                operation,
                ffmpeg_output_codec,
                output_container,
            )

        self.assertEqual(cm.exception.code, 0)

        mock_run.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch("run_ffmpeg.check_success")
    @patch("run_ffmpeg.cleanup")
    @patch("run_ffmpeg.subprocess.run")
    def test_run_ffmpeg_encode_failure(
        self, mock_run, mock_cleanup, mock_check_succ
    ):
        video_filepath = "filepath"
        libva_profile = "1"
        libva_entrypoint = "1"
        operation = "encode"
        ffmpeg_output_codec = "VP9"
        output_container = "mp4"

        mock_run.return_value = "ffmpeg output"
        mock_check_succ.return_value = False

        with self.assertRaises(SystemExit) as cm:
            run_ffmpeg(
                video_filepath,
                libva_profile,
                libva_entrypoint,
                operation,
                ffmpeg_output_codec,
                output_container,
            )

        self.assertNotEqual(cm.exception.code, 0)

        mock_run.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch("run_ffmpeg.RESOURCES_DIR", "/mock/resources/")
    def test_ffmpeg_decode_command(self):
        input_file = "input.mp4"
        expected = [
            "ffmpeg",
            "-hwaccel",
            "vaapi",
            "-vaapi_device",
            "/dev/dri/renderD128",
            "-hide_banner",
            "-loglevel",
            "info",
            "-i",
            input_file,
            "-t",
            "5",
            "-pix_fmt",
            "yuv420p",
            "-f",
            "rawvideo",
            "-vsync",
            "1",
            "-y",
            "/mock/resources/out.yuv",
        ]

        result = ffmpeg_decode_command(input_file)
        self.assertEqual(result, expected)

    @patch("run_ffmpeg.RESOURCES_DIR", "/mock/resources/")
    def test_ffmpeg_encode_command(self):
        input_file = "input.yuv"
        codec = "h264_vaapi"
        container = "mp4"

        expected = [
            "ffmpeg",
            "-hwaccel",
            "vaapi",
            "-vaapi_device",
            "/dev/dri/renderD128",
            "-hide_banner",
            "-loglevel",
            "info",
            "-i",
            input_file,
            "-rc_mode",
            "CQP",
            "-low_power",
            "1",
            "-c:v",
            codec,
            "-vf",
            "format=nv12,hwupload",
            "/mock/resources/output.mp4",
            "-y",
        ]

        result = ffmpeg_encode_command(input_file, codec, container)
        self.assertEqual(result, expected)
