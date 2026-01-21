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


from pathlib import Path, PosixPath
import unittest as ut
from unittest.mock import MagicMock, patch

import gl_support

TEST_DATA_DIR = Path(__file__).parent / "test_data"


class TestGLSupportTests(ut.TestCase):

    @patch.dict(
        "os.environ",
        {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "wayland",
        },
        clear=True,
    )
    @patch("sys.argv", ["gl_support_test.py"])
    @patch("platform.uname")
    @patch("subprocess.check_output")
    def test_happy_path(
        self,
        mock_check_output: MagicMock,
        mock_uname: MagicMock,
    ):
        for arch in "x86_64", "aarch64":
            mock_uname().machine = arch

            with (TEST_DATA_DIR / "glmark2_ok.txt").open() as f:
                mock_check_output.return_value = f.read()
                gl_support.main()

    @patch.dict(
        "os.environ",
        {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "wayland",
        },
        clear=True,
    )
    @patch("sys.argv", ["gl_support_test.py"])
    @patch("subprocess.check_output")
    def test_happy_path_es2(
        self,
        mock_check_output: MagicMock,
    ):

        with (TEST_DATA_DIR / "glmark2_es2_ok.txt").open() as f:
            mock_check_output.return_value = f.read()
            gl_support.main()

    @patch.dict(
        "os.environ",
        {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "wayland",
        },
        clear=True,
    )
    @patch("sys.argv", ["gl_support_test.py"])
    @patch("subprocess.check_output")
    def test_llvmpipe_path(
        self,
        mock_check_output: MagicMock,
    ):
        with (TEST_DATA_DIR / "glmark2_llvmpipe.txt").open() as f:
            mock_check_output.return_value = f.read()
            self.assertRaises(SystemExit, gl_support.main)

    @patch.dict(
        "os.environ",
        {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "wayland",
        },
        clear=True,
    )
    @patch("sys.argv", ["gl_support_test.py"])
    @patch("subprocess.check_output")
    def test_llvmpipe_path_es2(
        self,
        mock_check_output: MagicMock,
    ):
        with (TEST_DATA_DIR / "glmark2_es2_llvmpipe.txt").open() as f:
            mock_check_output.return_value = f.read()
            self.assertRaises(SystemExit, gl_support.main)

    @patch.dict(
        "os.environ",
        {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "wayland",
        },
        clear=True,
    )
    @patch("sys.argv", ["gl_support_test.py"])
    @patch("subprocess.check_output")
    def test_version_too_old_path_x86(
        self,
        mock_check_output: MagicMock,
    ):

        with (TEST_DATA_DIR / "glmark2_version_too_old.txt").open() as f:
            mock_check_output.return_value = f.read()
            with self.assertRaises(SystemExit) as ar:
                gl_support.main()
                self.assertEqual(
                    ar.msg,
                    "The minimum required OpenGL version is 3.0, but got 2.1",
                )

    @patch("gl_support.in_classic_snap")
    @patch("gl_support.GLSupportTester.pick_glmark2_executable")
    @patch("os.path.exists")
    @patch("os.path.islink")
    @patch("os.unlink")
    @patch("os.symlink")
    @patch("subprocess.check_output")
    def test_cleanup_glmark2_data_symlink(
        self,
        _: MagicMock,
        mock_symlink: MagicMock,
        mock_unlink: MagicMock,
        mock_islink: MagicMock,
        mock_path_exists: MagicMock,
        mock_pick_glmark2_executable: MagicMock,
        mock_in_classic_snap: MagicMock,
    ):
        mock_pick_glmark2_executable.return_value = "glmark2"
        mock_in_classic_snap.return_value = False
        for is_snap in (True, False):
            with patch.dict(
                "os.environ",
                {
                    "DISPLAY": ":0",
                    "XDG_SESSION_TYPE": "wayland",
                }
                | (
                    {
                        "CHECKBOX_RUNTIME": "\n".join(
                            [
                                "/snap/checkbox24/1437",
                                "/snap/checkbox/20486/checkbox-runtime",
                                "/snap/checkbox/20486/providers/blah-blah",
                            ]
                        ),
                        "SNAP": "/snap/checkbox/20486",
                    }
                    if is_snap
                    else {}
                ),
            ):
                mock_islink.return_value = is_snap
                # deb case, the file actually exists
                mock_path_exists.return_value = not is_snap

                gl_support.GLSupportTester().call_glmark2_validate()

                if is_snap:
                    mock_symlink.assert_called_once_with(
                        PosixPath(
                            "/snap/checkbox/20486/checkbox-runtime/usr/share/glmark2"
                        ),
                        PosixPath("/usr/share/glmark2"),
                        target_is_directory=True,
                    )

                    mock_unlink.assert_called_once_with(
                        PosixPath("/usr/share/glmark2")
                    )
                else:
                    mock_symlink.assert_not_called()
                    mock_unlink.assert_not_called()

                mock_symlink.reset_mock()
                mock_unlink.reset_mock()

    @patch("subprocess.run")
    @patch("os.environ")
    def test_is_hardware_renderer_available_bad_session_type(
        self,
        _: MagicMock,
        mock_env: MagicMock,
    ):
        mock_env["XDG_SESSION_TYPE"] = "tty"
        self.assertRaises(
            SystemExit, gl_support.GLSupportTester().call_glmark2_validate
        )

    @patch.dict(
        "os.environ",
        {
            "DISPLAY": ":0",
            "XDG_SESSION_TYPE": "wayland",
        },
        clear=True,
    )
    @patch("shutil.which")
    @patch("gl_support.GLSupportTester.pick_glmark2_executable")
    @patch("subprocess.check_output")
    def test_glmark2_cmd_override(
        self,
        mock_check_output: MagicMock,
        mock_pick_exec: MagicMock,
        mock_which: MagicMock,
    ):
        mock_which.return_value = None
        self.assertRaises(
            SystemExit,
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
