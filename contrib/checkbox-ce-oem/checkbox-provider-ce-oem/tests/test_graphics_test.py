#!/usr/bin/env python3

import unittest
from unittest.mock import patch, MagicMock
import subprocess
import logging
import sys
import os
from io import StringIO
import graphics_test


class TestGraphicsTest(unittest.TestCase):
    def setUp(self):
        # Suppress logging output during tests
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        # Re-enable logging
        logging.disable(logging.NOTSET)

    @patch("logging.basicConfig")
    def test_debug_logging(self, mock_basic_config):
        graphics_test.debug_logging(verbose=False)
        mock_basic_config.assert_called_with(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )

        graphics_test.debug_logging(verbose=True)
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
        self.assertEqual(mock_is_active.call_count, 1)
        mock_run.assert_called_with(
            ["journalctl", "-b", "0", "-g", "ubuntu-frame"]
        )

    @patch("graphics_test.is_ubuntu_frame_active", return_value=False)
    @patch("subprocess.run")
    def test_ubuntu_frame_launching_timeout(self, mock_run, mock_is_active):
        mock_run.side_effect = subprocess.CalledProcessError(124, "cmd")
        self.assertEqual(graphics_test.test_ubuntu_frame_launching(), 0)
        self.assertEqual(mock_is_active.call_count, 1)
        mock_run.assert_called_with(
            ["timeout", "20s", "ubuntu-frame"],
            check=True,
            stdout=unittest.mock.ANY,
            stderr=unittest.mock.ANY,
        )

    @patch("graphics_test.is_ubuntu_frame_active", return_value=False)
    @patch("subprocess.run")
    def test_ubuntu_frame_launching_fail(self, mock_run, mock_is_active):
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
        self.assertEqual(graphics_test.test_ubuntu_frame_launching(), 1)
        self.assertEqual(mock_is_active.call_count, 1)

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
            stdout=unittest.mock.ANY,
            stderr=unittest.mock.ANY,
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

    @patch("sys.stderr", new_callable=StringIO)
    def test_main_no_args(self, mock_stderr):
        with patch("sys.argv", ["script.py"]):
            with self.assertRaises(SystemExit) as cm:
                graphics_test.main()
        self.assertEqual(cm.exception.code, 2)

    @patch("sys.exit")
    @patch("graphics_test.test_ubuntu_frame_launching", return_value=0)
    def test_main_frame_arg(self, mock_test_frame, mock_exit):
        with patch("sys.argv", ["script.py", "frame"]):
            graphics_test.main()
        self.assertEqual(mock_test_frame.call_count, 1)
        mock_exit.assert_called_with(0)

    @patch("sys.exit")
    @patch("graphics_test.test_glmark2_es2_wayland", return_value=0)
    def test_main_glmark2_arg(self, mock_test_glmark2, mock_exit):
        with patch("sys.argv", ["script.py", "glmark2"]):
            graphics_test.main()
        self.assertEqual(mock_test_glmark2.call_count, 1)
        mock_exit.assert_called_with(0)

    @patch("sys.stderr", new_callable=StringIO)
    def test_main_invalid_arg(self, mock_stderr):
        with patch("sys.argv", ["script.py", "invalid"]):
            with self.assertRaises(SystemExit) as cm:
                graphics_test.main()
        self.assertEqual(cm.exception.code, 2)

    @patch("sys.exit")
    @patch("graphics_test.test_ubuntu_frame_launching")
    @patch("graphics_test.debug_logging")
    def test_main_debug_arg(
        self, mock_debug_logging, mock_test_frame, mock_exit
    ):
        with patch("sys.argv", ["script.py", "frame", "--debug"]):
            graphics_test.main()
        mock_debug_logging.assert_called_with(True)
        self.assertEqual(mock_test_frame.call_count, 1)
        mock_exit.assert_called_with(mock_test_frame.return_value)

        # Reset mock and test without --debug
        mock_debug_logging.reset_mock()
        mock_test_frame.reset_mock()
        mock_exit.reset_mock()

        with patch("sys.argv", ["script.py", "frame"]):
            graphics_test.main()
        mock_debug_logging.assert_called_with(False)
        self.assertEqual(mock_test_frame.call_count, 1)
        mock_exit.assert_called_with(mock_test_frame.return_value)


if __name__ == "__main__":
    script_dir = os.path.dirname(__file__)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    unittest.main(verbosity=2)
