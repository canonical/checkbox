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
    def setUp(self) -> None:
        gl_support.RUNTIME_ROOT = ""

    @patch("sys.argv", ["gl_support_test.py"])
    @patch("platform.uname")
    @patch("gl_support.GLSupportTester.get_desktop_environment_variables")
    @patch("subprocess.check_output")
    @patch("os.getenv")
    def test_happy_path(
        self,
        mock_getenv: MagicMock,
        mock_check_output: MagicMock,
        mock_get_desktop_envs: MagicMock,
        mock_uname: MagicMock,
    ):
        mock_getenv.side_effect = lambda key: (
            ":0" if key == "DISPLAY" else "wayland"
        )
        for arch in "x86_64", "aarch64":
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
        mock_run.return_value = sp.CompletedProcess([], 1, "", "")
        self.assertRaises(
            RuntimeError,
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

    @patch("gl_support.GLSupportTester.pick_glmark2_executable")
    @patch("gl_support.GLSupportTester.get_desktop_environment_variables")
    @patch("os.path.exists")
    @patch("os.path.islink")
    @patch("os.unlink")
    @patch("os.symlink")
    @patch("subprocess.check_output")
    @patch("os.getenv")
    def test_cleanup_glmark2_data_symlink(
        self,
        mock_getenv: MagicMock,
        mock_check_output: MagicMock,
        mock_symlink: MagicMock,
        mock_unlink: MagicMock,
        mock_islink: MagicMock,
        mock_path_exists: MagicMock,
        mock_get_desktop_envs: MagicMock,
        mock_pick_glmark2_executable: MagicMock,
    ):
        def custom_env(key: str, is_snap: bool) -> str:
            if key == "CHECKBOX_RUNTIME":
                return "/snap/runtime/path/" if is_snap else ""

            raise Exception("unexpected use of this mock")

        mock_get_desktop_envs.return_value = {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "x11",
        }
        mock_pick_glmark2_executable.return_value = "glmark2"

        tester = gl_support.GLSupportTester()

        for is_snap in (True, False):
            mock_getenv.side_effect = lambda k: custom_env(k, is_snap)
            gl_support.RUNTIME_ROOT = custom_env("CHECKBOX_RUNTIME", is_snap)
            # RCT.SNAP = custom_env("SNAP", is_snap)
            mock_islink.return_value = is_snap
            # deb case, the file actually exists
            mock_path_exists.return_value = not is_snap

            tester.call_glmark2_validate()

            if is_snap:
                print("\n\n\n")
                print(gl_support.RUNTIME_ROOT, mock_path_exists.return_value)
                print(mock_symlink.call_args)
                print("\n\n\n")
                mock_symlink.assert_called_once_with(
                    "{}/usr/share/glmark2".format(gl_support.RUNTIME_ROOT),
                    "/usr/share/glmark2",
                    target_is_directory=True,
                )

                mock_unlink.assert_called_once_with("/usr/share/glmark2")
            else:
                mock_symlink.assert_not_called()
                mock_unlink.assert_not_called()

            mock_symlink.reset_mock()
            mock_unlink.reset_mock()
        gl_support.RUNTIME_ROOT = ""

    @patch("subprocess.run")
    @patch("gl_support.GLSupportTester.get_desktop_environment_variables")
    def test_is_hardware_renderer_available_bad_session_type(
        self,
        mock_get_desktop_envs: MagicMock,
        _: MagicMock,
    ):
        mock_get_desktop_envs.return_value = {
            "DISPLAY": "",
            "XDG_SESSION_TYPE": "tty",
        }
        self.assertRaises(
            ValueError, gl_support.GLSupportTester().call_glmark2_validate
        )

    @patch("shutil.which")
    @patch("gl_support.GLSupportTester.pick_glmark2_executable")
    @patch("gl_support.GLSupportTester.get_desktop_environment_variables")
    @patch("subprocess.check_output")
    @patch("os.getenv")
    def test_glmark2_cmd_override(
        self,
        mock_getenv: MagicMock,
        mock_check_output: MagicMock,
        mock_get_desktop_envs: MagicMock,
        mock_pick_exec: MagicMock,
        mock_which: MagicMock,
    ):
        mock_getenv.side_effect = lambda key: (
            ":0" if key == "DISPLAY" else "x11"
        )
        mock_get_desktop_envs.return_value = {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "x11",
        }
        mock_which.return_value = None
        self.assertRaises(
            FileNotFoundError,
            lambda: gl_support.GLSupportTester().call_glmark2_validate(
                "this-doesnt-exist"
            ),
        )

        mock_which.return_value = "/usr/bin/this-exists"
        mock_pick_exec.reset_mock()
        gl_support.GLSupportTester().call_glmark2_validate("this-exists")
        # [0] first call -> [0] first argument -> [0] first list element
        self.assertEqual(mock_check_output.call_args[0][0][0], "this-exists")

    def test_pick_es2_for_all_non_x86(self):
        self.assertEqual(
            gl_support.GLSupportTester().pick_glmark2_executable(
                "wayland", "mips"
            ),
            "glmark2-es2-wayland",
        )
        self.assertEqual(
            gl_support.GLSupportTester().pick_glmark2_executable(
                "x11", "aarch64"
            ),
            "glmark2-es2",
        )


if __name__ == "__main__":
    ut.main()
