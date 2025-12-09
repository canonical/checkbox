#!/usr/bin/env python3

import unittest
from unittest.mock import patch, MagicMock, call
import subprocess
import logging
import sys
import os
import graphics_test


class TestGraphicsTest(unittest.TestCase):
    def setUp(self):
        # Suppress logging output during tests
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        # Re-enable logging
        logging.disable(logging.NOTSET)

    @patch("logging.basicConfig")
    def test_setup_logging(self, mock_basic_config):
        graphics_test.setup_logging(verbose=False)
        mock_basic_config.assert_called_with(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )

        graphics_test.setup_logging(verbose=True)
        mock_basic_config.assert_called_with(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )

    @patch("subprocess.check_output")
    def test_is_ubuntu_frame_active_true(self, mock_check_output):
        self.assertTrue(graphics_test.is_ubuntu_frame_active())
        mock_check_output.assert_called_with(["pgrep", "-if", "ubuntu-frame"])

    @patch(
        "subprocess.check_output",
        side_effect=subprocess.CalledProcessError(1, "cmd"),
    )
    def test_is_ubuntu_frame_active_false(self, mock_check_output):
        self.assertFalse(graphics_test.is_ubuntu_frame_active())
        mock_check_output.assert_called_with(["pgrep", "-if", "ubuntu-frame"])

    @patch("graphics_test.is_ubuntu_frame_active", return_value=True)
    @patch("subprocess.run")
    def test_ubuntu_frame_launching_already_active(
        self, mock_run, mock_is_active
    ):
        self.assertEqual(graphics_test.test_ubuntu_frame_launching(), 0)
        mock_is_active.assert_called_once()
        mock_run.assert_called_with(
            ["journalctl", "-b", "0", "-g", "ubuntu-frame"]
        )

    @patch("graphics_test.is_ubuntu_frame_active", return_value=False)
    @patch("subprocess.run")
    def test_ubuntu_frame_launching_timeout(self, mock_run, mock_is_active):
        mock_run.side_effect = subprocess.CalledProcessError(124, "cmd")
        self.assertEqual(graphics_test.test_ubuntu_frame_launching(), 0)
        mock_is_active.assert_called_once()
        mock_run.assert_called_with(
            ["timeout", "20s", "ubuntu-frame"],
            check=True,
            capture_output=True,
        )

    @patch("graphics_test.is_ubuntu_frame_active", return_value=False)
    @patch("subprocess.run")
    def test_ubuntu_frame_launching_fail(self, mock_run, mock_is_active):
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
        self.assertEqual(graphics_test.test_ubuntu_frame_launching(), 1)
        mock_is_active.assert_called_once()

    @patch("os.environ.get")
    @patch("time.sleep")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    @patch("graphics_test.is_ubuntu_frame_active")
    def test_glmark2_success(
        self,
        mock_is_active,
        mock_popen,
        mock_run,
        mock_sleep,
        mock_env_get,
    ):
        mock_is_active.side_effect = [False, True]
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.stdout = [
            "GL_VENDOR:     TestVendor",
            "GL_RENDERER:   TestRenderer",
        ]
        mock_popen.return_value = mock_proc
        mock_env_get.side_effect = ["TestVendor", "TestRenderer"]

        self.assertEqual(graphics_test.test_glmark2_es2_wayland(), 0)
        mock_popen.assert_any_call(
            ["ubuntu-frame"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        mock_run.assert_called_with(["kill", "1234"])

    @patch("subprocess.Popen")
    @patch("graphics_test.is_ubuntu_frame_active", return_value=True)
    @patch("os.environ.get", return_value=None)
    def test_glmark2_no_env_vars(
        self, mock_env_get, mock_is_active, mock_popen
    ):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc
        self.assertEqual(graphics_test.test_glmark2_es2_wayland(), 1)

    @patch("os.environ.get")
    @patch("subprocess.Popen")
    @patch("graphics_test.is_ubuntu_frame_active", return_value=True)
    def test_glmark2_wrong_vendor(
        self, mock_is_active, mock_popen, mock_env_get
    ):
        mock_proc = MagicMock()
        mock_proc.stdout = ["GL_VENDOR: WrongVendor"]
        mock_popen.return_value = mock_proc
        mock_env_get.side_effect = ["CorrectVendor", "TestRenderer"]

        self.assertEqual(graphics_test.test_glmark2_es2_wayland(), 1)

    @patch("os.environ.get")
    @patch("subprocess.Popen")
    @patch("graphics_test.is_ubuntu_frame_active", return_value=True)
    def test_glmark2_wrong_renderer(
        self, mock_is_active, mock_popen, mock_env_get
    ):
        mock_proc = MagicMock()
        mock_proc.stdout = [
            "GL_VENDOR:     TestVendor",
            "GL_RENDERER:   WrongRenderer",
        ]
        mock_popen.return_value = mock_proc
        mock_env_get.side_effect = ["TestVendor", "CorrectRenderer"]

        self.assertEqual(graphics_test.test_glmark2_es2_wayland(), 1)

    @patch("graphics_test.logger.info")
    def test_help_function(self, mock_logger_info):
        graphics_test.help_function()
        self.assertGreater(mock_logger_info.call_count, 2)

    @patch("graphics_test.help_function")
    def test_main_no_args(self, mock_help):
        with patch("sys.argv", ["script.py"]):
            with self.assertRaises(SystemExit) as cm:
                graphics_test.main()
        mock_help.assert_called_once()
        self.assertEqual(cm.exception.code, 1)

    @patch("sys.exit")
    @patch("graphics_test.test_ubuntu_frame_launching", return_value=0)
    def test_main_frame_arg(self, mock_test_func, mock_exit):
        with patch("sys.argv", ["script.py", "frame"]):
            graphics_test.main()
            mock_test_func.assert_called_once()
            mock_exit.assert_called_with(0)

    @patch("sys.exit")
    @patch("graphics_test.test_glmark2_es2_wayland", return_value=0)
    def test_main_glmark2_arg(self, mock_test_func, mock_exit):
        with patch("sys.argv", ["script.py", "glmark2"]):
            graphics_test.main()
            mock_test_func.assert_called_once()
            mock_exit.assert_called_with(0)

    @patch("sys.exit")
    @patch("graphics_test.help_function")
    def test_main_invalid_arg(self, mock_help, mock_exit):
        with patch("sys.argv", ["script.py", "invalid"]):
            graphics_test.main()
            mock_help.assert_called_once()
            mock_exit.assert_called_with(1)


if __name__ == "__main__":
    # Add the script's directory to the Python path
    # to allow importing graphics_test
    script_dir = os.path.dirname(__file__)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    unittest.main(verbosity=2)
