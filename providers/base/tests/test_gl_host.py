#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Shane McKee <shane.mckee@canonical.com>
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

import unittest
from unittest.mock import MagicMock, mock_open, patch

import gl_host
from gl_host import OpenGLError


class TestHasDrmGpu(unittest.TestCase):
    @patch("os.listdir", side_effect=OSError("permission denied"))
    def test_raises_when_drm_unreadable(self, _listdir):
        with self.assertRaises(OpenGLError):
            gl_host._has_drm_gpu()

    @patch("os.listdir", return_value=[])
    def test_returns_false_when_no_cards(self, _listdir):
        self.assertFalse(gl_host._has_drm_gpu())

    @patch("os.listdir", return_value=["card0", "card0-HDMI-1"])
    @patch(
        "builtins.open",
        mock_open(read_data="0x8086\n"),
    )
    def test_returns_true_for_known_vendor(self, _listdir):
        self.assertTrue(gl_host._has_drm_gpu())

    @patch("os.listdir", return_value=["card0"])
    @patch(
        "builtins.open",
        mock_open(read_data="0xdead\n"),
    )
    def test_returns_false_for_unknown_vendor(self, _listdir):
        self.assertFalse(gl_host._has_drm_gpu())

    @patch("os.listdir", return_value=["card0"])
    @patch("builtins.open", side_effect=OSError("no such file"))
    def test_skips_unreadable_card(self, _listdir, _open):
        self.assertFalse(gl_host._has_drm_gpu())


class TestCmdResource(unittest.TestCase):
    @patch("gl_host._has_drm_gpu", return_value=True)
    def test_returns_none_when_gpu_found(self, _has):
        self.assertIsNone(gl_host.cmd_resource())

    @patch("gl_host._has_drm_gpu", return_value=False)
    def test_raises_when_no_gpu(self, _has):
        with self.assertRaises(OpenGLError):
            gl_host.cmd_resource()

    @patch("gl_host._has_drm_gpu", side_effect=OpenGLError("drm unreadable"))
    def test_propagates_drm_error(self, _has):
        with self.assertRaises(OpenGLError):
            gl_host.cmd_resource()


class TestCmdValidateInstall(unittest.TestCase):
    @patch("os.path.isfile", return_value=True)
    @patch("gl_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_returns_none_when_egl_found(self, _arch, _isfile):
        self.assertIsNone(gl_host.cmd_validate_install())

    @patch("os.path.isfile", return_value=False)
    @patch("gl_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_raises_when_egl_not_found(self, _arch, _isfile):
        with self.assertRaises(OpenGLError):
            gl_host.cmd_validate_install()

    @patch("os.path.isfile", return_value=True)
    @patch("gl_host.get_arch_triple", return_value="x86_64-linux-gnu")
    def test_checks_correct_path(self, _arch, mock_isfile):
        gl_host.cmd_validate_install()
        mock_isfile.assert_called_once_with(
            "/usr/lib/x86_64-linux-gnu/libEGL.so.1"
        )


class TestCmdRunTest(unittest.TestCase):
    SNAP = "/snap/opengl-cts/current"

    @patch("subprocess.run")
    def test_passes_test_args_to_snap_binary(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        gl_host.cmd_run_test(["--deqp-case=KHR-GLES32.info.*"])
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "{}/test".format(self.SNAP))
        self.assertIn("--no-confinement", cmd)
        self.assertIn("--deqp-case=KHR-GLES32.info.*", cmd)

    @patch("subprocess.run")
    def test_sets_snap_env(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        gl_host.cmd_run_test(["--deqp-case=KHR-GLES32.info.*"])
        self.assertEqual(mock_run.call_args[1]["env"]["SNAP"], self.SNAP)

    @patch("subprocess.run")
    def test_returns_subprocess_returncode(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        self.assertEqual(
            gl_host.cmd_run_test(["--deqp-case=KHR-GLES32.info.*"]), 1
        )


class TestMain(unittest.TestCase):
    @patch("gl_host.cmd_resource", return_value=None)
    def test_dispatches_resource(self, mock_cmd):
        with patch("sys.argv", ["gl_host.py", "resource"]):
            self.assertEqual(gl_host.main(), 0)
        self.assertEqual(mock_cmd.call_count, 1)

    @patch("gl_host.cmd_validate_install", return_value=None)
    def test_dispatches_validate_install(self, mock_cmd):
        with patch("sys.argv", ["gl_host.py", "validate-install"]):
            self.assertEqual(gl_host.main(), 0)
        self.assertEqual(mock_cmd.call_count, 1)

    @patch("gl_host.cmd_run_test", return_value=0)
    def test_dispatches_run_test_with_args(self, mock_cmd):
        with patch(
            "sys.argv",
            ["gl_host.py", "run-test", "--deqp-case=KHR-GLES32.info.*"],
        ):
            self.assertEqual(gl_host.main(), 0)
        mock_cmd.assert_called_once_with(["--deqp-case=KHR-GLES32.info.*"])

    def test_returns_1_with_no_args(self):
        with patch("sys.argv", ["gl_host.py"]):
            self.assertEqual(gl_host.main(), 1)

    @patch(
        "gl_host.cmd_resource",
        side_effect=OpenGLError("No known GPU found"),
    )
    def test_returns_1_on_opengl_error(self, _cmd):
        with patch("sys.argv", ["gl_host.py", "resource"]):
            self.assertEqual(gl_host.main(), 1)

    @patch(
        "gl_host.cmd_validate_install",
        side_effect=RuntimeError("could not determine multiarch triple"),
    )
    def test_returns_1_on_runtime_error(self, _cmd):
        with patch("sys.argv", ["gl_host.py", "validate-install"]):
            self.assertEqual(gl_host.main(), 1)


if __name__ == "__main__":
    unittest.main()
