#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
#   Zhongning Li <zhongning.li@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import pathlib
import subprocess as sp
import unittest as ut
from unittest.mock import MagicMock, patch

import gl_support

TEST_DATA_DIR = pathlib.Path(__file__).parent / "test_data"


class TestGLSupportTests(ut.TestCase):
    @patch("sys.argv", ["gl_support_test.py"])
    @patch("platform.uname")
    @patch("gl_support.GLSupportTester.get_desktop_environment_variables")
    @patch("subprocess.check_output")
    @patch("os.getenv")
    def test_happy_path_x86(
        self,
        mock_getenv: MagicMock,
        mock_check_output: MagicMock,
        mock_get_desktop_envs: MagicMock,
        mock_uname: MagicMock,
    ):
        mock_getenv.side_effect = lambda key: (
            ":0" if key == "DISPLAY" else "wayland"
        )
        mock_uname().machine = "x86_64"
        mock_get_desktop_envs.return_value = {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "wayland",
        }

        with (TEST_DATA_DIR / "glmark2_ok.txt").open() as f:
            mock_check_output.return_value = f.read()
            gl_support.main()

    @patch("sys.argv", ["gl_support_test.py"])
    @patch("gl_support.GLSupportTester.get_desktop_environment_variables")
    @patch("subprocess.check_output")
    @patch("os.getenv")
    def test_happy_path_es2(
        self,
        mock_getenv: MagicMock,
        mock_check_output: MagicMock,
        mock_get_desktop_envs: MagicMock,
    ):
        mock_getenv.side_effect = lambda key: (
            ":0" if key == "DISPLAY" else "x11"
        )
        mock_get_desktop_envs.return_value = {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "x11",
        }

        with (TEST_DATA_DIR / "glmark2_es2_ok.txt").open() as f:
            mock_check_output.return_value = f.read()
            gl_support.main()

    @patch("sys.argv", ["gl_support_test.py"])
    @patch("gl_support.GLSupportTester.get_desktop_environment_variables")
    @patch("subprocess.check_output")
    @patch("os.getenv")
    def test_llvmpipe_path(
        self,
        mock_getenv: MagicMock,
        mock_check_output: MagicMock,
        mock_get_desktop_envs: MagicMock,
    ):
        mock_getenv.side_effect = lambda key: (
            ":0" if key == "DISPLAY" else "x11"
        )
        mock_get_desktop_envs.return_value = {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "x11",
        }

        with (TEST_DATA_DIR / "glmark2_llvmpipe.txt").open() as f:
            mock_check_output.return_value = f.read()
            self.assertRaises(ValueError, gl_support.main)

    @patch("sys.argv", ["gl_support_test.py"])
    @patch("gl_support.GLSupportTester.get_desktop_environment_variables")
    @patch("subprocess.check_output")
    @patch("os.getenv")
    def test_llvmpipe_path_es2(
        self,
        mock_getenv: MagicMock,
        mock_check_output: MagicMock,
        mock_get_desktop_envs: MagicMock,
    ):
        mock_getenv.side_effect = lambda key: (
            ":0" if key == "DISPLAY" else "x11"
        )
        mock_get_desktop_envs.return_value = {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "x11",
        }

        with (TEST_DATA_DIR / "glmark2_es2_llvmpipe.txt").open() as f:
            mock_check_output.return_value = f.read()
            self.assertRaises(ValueError, gl_support.main)

    @patch("sys.argv", ["gl_support_test.py"])
    @patch("gl_support.GLSupportTester.get_desktop_environment_variables")
    @patch("subprocess.check_output")
    @patch("os.getenv")
    def test_version_too_old_path_x86(
        self,
        mock_getenv: MagicMock,
        mock_check_output: MagicMock,
        mock_get_desktop_envs: MagicMock,
    ):
        mock_getenv.side_effect = lambda key: (
            ":0" if key == "DISPLAY" else "x11"
        )
        mock_get_desktop_envs.return_value = {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "x11",
        }

        with (TEST_DATA_DIR / "glmark2_version_too_old.txt").open() as f:
            mock_check_output.return_value = f.read()
            with self.assertRaises(ValueError) as ar:
                gl_support.main()
                self.assertEqual(
                    ar.msg,
                    "The minimum required OpenGL version is 3.0, but got 2.1",
                )

    @patch("subprocess.run")
    def test_get_desktop_env_vars_no_desktop_session(
        self, mock_run: MagicMock
    ):
        mock_run.side_effect = sp.CalledProcessError(1, "")
        self.assertRaises(
            sp.CalledProcessError,
            gl_support.GLSupportTester().get_desktop_environment_variables,
        )

    @patch("subprocess.check_output")
    @patch("subprocess.run")
    def test_get_desktop_env_vars_happy_path(
        self, mock_run: MagicMock, mock_check_output: MagicMock
    ):
        mock_run.return_value = sp.CompletedProcess([], 0, "12345")
        mock_check_output.return_value = "\0".join(
            [
                "XDG_CONFIG_DIRS=/etc/xdg/xdg-ubuntu:/etc/xdg",
                "XDG_CURRENT_DESKTOP=ubuntu:GNOME",
                "XDG_SESSION_CLASS=user",
                "XDG_SESSION_DESKTOP=ubuntu-wayland",
                "XDG_SESSION_TYPE=wayland",
            ]
        )

        out = gl_support.GLSupportTester().get_desktop_environment_variables()

        self.assertIsNotNone(out)
        self.assertDictEqual(
            out,  # type: ignore
            {
                "XDG_CONFIG_DIRS": "/etc/xdg/xdg-ubuntu:/etc/xdg",
                "XDG_CURRENT_DESKTOP": "ubuntu:GNOME",
                "XDG_SESSION_CLASS": "user",
                "XDG_SESSION_DESKTOP": "ubuntu-wayland",
                "XDG_SESSION_TYPE": "wayland",
            },
        )


if __name__ == "__main__":
    ut.main()
