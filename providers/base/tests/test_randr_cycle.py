#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
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

from unittest.mock import patch, MagicMock, mock_open
import sys

sys.modules["dbus"] = MagicMock()
sys.modules["dbus.mainloop.glib"] = MagicMock()

from checkbox_support.dbus.gnome_monitor import MutterDisplayMode as Mode
from randr_cycle import resolution_filter, action, MonitorTest
import subprocess
import unittest
import os


class TestResolutionFilter(unittest.TestCase):
    def test_ignore_too_small(self):
        mode1 = Mode(
            id="1",
            width=500,
            height=300,
            refresh_rate=60,
            preferred_scale=1.0,
            supported_scales=[1.0, 2.0],
            properties={"is_preferred": True, "is_current": True},
        )
        mode2 = Mode(
            id="2",
            width=1024,
            height=768,
            refresh_rate=60,
            preferred_scale=1.0,
            supported_scales=[1.0, 2.0],
            properties={"is_preferred": False, "is_current": False},
        )
        modes = [mode1, mode2]

        filtered_modes = resolution_filter(modes)

        self.assertEqual(len(filtered_modes), 1)
        self.assertEqual(filtered_modes[0].resolution, "1024x768")

    def test_ignore_same_resolution(self):
        mode1 = Mode(
            id="1",
            width=1024,
            height=768,
            refresh_rate=60,
            preferred_scale=1.0,
            supported_scales=[1.0, 2.0],
            properties={"is_preferred": True, "is_current": True},
        )
        mode2 = Mode(
            id="2",
            width=1024,
            height=768,
            refresh_rate=60,
            preferred_scale=1.0,
            supported_scales=[1.0, 2.0],
            properties={"is_preferred": False, "is_current": False},
        )
        modes = [mode1, mode2]

        filtered_modes = resolution_filter(modes)

        self.assertEqual(len(filtered_modes), 1)
        self.assertEqual(filtered_modes[0].resolution, "1024x768")

    def test_ignore_smaller_width_same_aspect(self):
        mode1 = Mode(
            id="1",
            width=1024,
            height=768,
            refresh_rate=60,
            preferred_scale=1.0,
            supported_scales=[1.0, 2.0],
            properties={"is_preferred": False, "is_current": False},
        )  # Aspect ratio: 4/3
        mode2 = Mode(
            id="2",
            width=800,
            height=600,
            refresh_rate=60,
            preferred_scale=1.0,
            supported_scales=[1.0, 2.0],
            properties={"is_preferred": False, "is_current": False},
        )  # Aspect ratio: 4/3
        mode3 = Mode(
            id="3",
            width=900,
            height=675,
            refresh_rate=60,
            preferred_scale=1.0,
            supported_scales=[1.0, 2.0],
            properties={"is_preferred": False, "is_current": False},
        )  # Aspect ratio: 4/3
        modes = [mode1, mode2, mode3]

        filtered_modes = resolution_filter(modes)

        self.assertEqual(len(filtered_modes), 1)
        self.assertEqual(filtered_modes[0].resolution, "1024x768")

    def test_multiple_aspects(self):
        mode1 = Mode(
            id="1",
            width=1920,
            height=1080,
            refresh_rate=60,
            preferred_scale=1.0,
            supported_scales=[1.0, 2.0],
            properties={"is_preferred": True, "is_current": True},
        )  # Aspect ratio: 7/4
        mode2 = Mode(
            id="2",
            width=800,
            height=600,
            refresh_rate=60,
            preferred_scale=1.0,
            supported_scales=[1.0, 2.0],
            properties={"is_preferred": False, "is_current": False},
        )  # Aspect ratio: 4/3
        mode3 = Mode(
            id="3",
            width=900,
            height=675,
            refresh_rate=60,
            preferred_scale=1.0,
            supported_scales=[1.0, 2.0],
            properties={"is_preferred": False, "is_current": False},
        )  # Aspect ratio: 4/3
        modes = [mode1, mode2, mode3]

        filtered_modes = resolution_filter(modes)

        self.assertEqual(len(filtered_modes), 2)
        self.assertIn("1920x1080", [m.resolution for m in filtered_modes])
        self.assertIn("900x675", [m.resolution for m in filtered_modes])

    def test_empty_input(self):
        filtered_modes = resolution_filter([])
        self.assertEqual(filtered_modes, [])


class TestActionFunction(unittest.TestCase):
    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("time.sleep")
    def test_action_with_path(self, mock_sleep, mock_subprocess, mock_which):
        filename = "monitor_1920x1080_normal_"
        path = "/tmp/screenshots"
        mock_which.return_value = True
        action(filename, path=path)

        expected_path_and_filename = "{}/{}.jpg".format(path, filename)
        mock_subprocess.assert_called_once_with(
            ["gnome-screenshot", "-f", expected_path_and_filename], timeout=5
        )
        mock_sleep.assert_called_once_with(5)

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("time.sleep")
    def test_action_without_path(
        self, mock_sleep, mock_subprocess, mock_which
    ):
        filename = "monitor_1920x1080_normal_"
        mock_which.return_value = True
        action(filename)

        expected_path_and_filename = filename + ".jpg"
        mock_subprocess.assert_called_once_with(
            ["gnome-screenshot", "-f", expected_path_and_filename], timeout=5
        )
        mock_sleep.assert_called_once_with(5)

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("time.sleep")
    def test_action_without_gnome_screenshot_installed(
        self,
        mock_sleep: MagicMock,
        mock_subprocess: MagicMock,
        mock_which: MagicMock,
    ):
        filename = "monitor_1920x1080_normal_"
        mock_which.return_value = False
        action(filename)

        mock_subprocess.assert_not_called()
        mock_sleep.assert_called_once_with(5)


class TestIsSuspendSupport(unittest.TestCase):
    @patch("randr_cycle.get_manifest")
    def test_suspend_supported_when_manifest_has_key_true(
        self, mock_get_manifest
    ):
        mock_get_manifest.return_value = {
            "com.canonical.certification::has_suspend_support": True
        }
        mt = MonitorTest()
        self.assertTrue(mt.is_suspend_support())

    @patch("randr_cycle.get_manifest")
    def test_suspend_not_supported_when_manifest_has_key_false(
        self, mock_get_manifest
    ):
        mock_get_manifest.return_value = {
            "com.canonical.certification::has_suspend_support": False
        }
        mt = MonitorTest()
        self.assertFalse(mt.is_suspend_support())

    @patch("randr_cycle.get_manifest")
    def test_suspend_not_supported_when_manifest_missing_key(
        self, mock_get_manifest
    ):
        mock_get_manifest.return_value = {}
        mt = MonitorTest()
        self.assertFalse(mt.is_suspend_support())

    @patch("randr_cycle.get_manifest")
    def test_suspend_not_supported_when_manifest_has_other_keys(
        self, mock_get_manifest
    ):
        mock_get_manifest.return_value = {"other_key": True}
        mt = MonitorTest()
        self.assertFalse(mt.is_suspend_support())


class GenScreenshotPath(unittest.TestCase):
    """
    This function should generate dictionary such as
    [screenshot_dir]_[keyword]
    """

    @patch("randr_cycle.get_manifest")
    @patch("os.makedirs")
    def test_before_suspend_without_keyword(
        self, mock_mkdir, mock_get_manifest
    ):
        mock_get_manifest.return_value = {
            "com.canonical.certification::has_suspend_support": True
        }
        mt = MonitorTest()
        with patch("builtins.open", mock_open(read_data="0")) as mock_file:
            self.assertEqual(
                mt.gen_screenshot_path("", "", "test"), "test/xrandr_screens"
            )
        mock_file.assert_called_with("/sys/power/suspend_stats/success", "r")
        mock_mkdir.assert_called_with("test/xrandr_screens", exist_ok=True)

    @patch("randr_cycle.get_manifest")
    @patch("os.makedirs")
    def test_after_suspend_without_keyword(
        self, mock_mkdir, mock_get_manifest
    ):
        mock_get_manifest.return_value = {
            "com.canonical.certification::has_suspend_support": True
        }
        mt = MonitorTest()
        with patch("builtins.open", mock_open(read_data="1")) as mock_file:
            self.assertEqual(
                mt.gen_screenshot_path(None, "", "test"),
                "test/xrandr_screens_after_suspend",
            )
        mock_file.assert_called_with("/sys/power/suspend_stats/success", "r")
        mock_mkdir.assert_called_with(
            "test/xrandr_screens_after_suspend", exist_ok=True
        )

    @patch("randr_cycle.get_manifest")
    @patch("os.makedirs")
    def test_with_keyword(self, mock_mkdir, mock_get_manifest):
        mock_get_manifest.return_value = {}
        mt = MonitorTest()
        self.assertEqual(
            mt.gen_screenshot_path("", "key", "test"),
            "test/xrandr_screens_key",
        )
        mock_mkdir.assert_called_with("test/xrandr_screens_key", exist_ok=True)

        self.assertEqual(
            mt.gen_screenshot_path("1", "key", "test"),
            "test/1_xrandr_screens_key",
        )
        mock_mkdir.assert_called_with(
            "test/1_xrandr_screens_key", exist_ok=True
        )

    @patch("randr_cycle.get_manifest")
    @patch("os.makedirs")
    def test_without_suspend_support_and_no_postfix(
        self, mock_mkdir, mock_get_manifest
    ):
        mock_get_manifest.return_value = {}
        mt = MonitorTest()
        with patch("builtins.open", mock_open()) as mock_file:
            self.assertEqual(
                mt.gen_screenshot_path("", "", "test"),
                "test/xrandr_screens",
            )
        mock_file.assert_not_called()
        mock_mkdir.assert_called_with("test/xrandr_screens", exist_ok=True)

    @patch("randr_cycle.get_manifest")
    @patch("os.makedirs")
    def test_suspend_supported_but_suspend_stats_missing(
        self, mock_mkdir, mock_get_manifest
    ):
        mock_get_manifest.return_value = {
            "com.canonical.certification::has_suspend_support": True
        }
        mt = MonitorTest()
        with patch("builtins.open", side_effect=FileNotFoundError):
            self.assertEqual(
                mt.gen_screenshot_path("", "", "test"),
                "test/xrandr_screens",
            )
        mock_mkdir.assert_called_with("test/xrandr_screens", exist_ok=True)


class TestScreenshotTarring(unittest.TestCase):
    @patch("os.listdir")
    @patch("tarfile.open")
    @patch("os.path.join")
    def test_tar_screenshot_dir(self, mock_join, mock_tar_open, mock_listdir):

        mt = MonitorTest()
        path = "screenshots"
        mock_listdir.return_value = ["screenshot1.png", "screenshot2.png"]

        mock_tar = MagicMock()
        mock_tar_open.return_value.__enter__.return_value = mock_tar

        mock_join.side_effect = lambda *args: "/".join(args)

        mt.tar_screenshot_dir(path)

        mock_tar_open.assert_called_once_with("screenshots.tgz", "w:gz")
        self.assertEqual(mock_tar.add.call_count, 2)
        mock_tar.add.assert_any_call(
            "screenshots/screenshot1.png", "screenshot1.png"
        )
        mock_tar.add.assert_any_call(
            "screenshots/screenshot2.png", "screenshot2.png"
        )

    @patch("os.listdir")
    @patch("tarfile.open")
    def test_tar_screenshot_dir_io_error(self, mock_tar_open, mock_listdir):

        mt = MonitorTest()
        path = "screenshots"
        mock_listdir.return_value = ["screenshot1.png"]

        mock_tar_open.side_effect = IOError("Unable to open tar file")

        try:
            mt.tar_screenshot_dir(path)
            result = (
                True  # If no exception is raised, we consider it successful.
            )
        except Exception:
            result = False

        self.assertTrue(
            result
        )  # Ensure it handles IOError without raising an unhandled exception.


class ParseArgsTests(unittest.TestCase):
    def test_success(self):
        mt = MonitorTest()

        home = os.getenv("HOME", "~")
        # no arguments, load default
        args = []
        rv = mt.parse_args(args)
        self.assertEqual(rv.cycle, "both")
        self.assertEqual(rv.postfix, "")
        self.assertEqual(rv.screenshot_dir, home)

        # change cycle type
        args = ["--cycle", "resolution"]
        rv = mt.parse_args(args)
        self.assertEqual(rv.cycle, "resolution")
        self.assertEqual(rv.postfix, "")
        self.assertEqual(rv.screenshot_dir, home)

        # change keyword
        args = ["--postfix", "key"]
        rv = mt.parse_args(args)
        self.assertEqual(rv.cycle, "both")
        self.assertEqual(rv.postfix, "key")
        self.assertEqual(rv.screenshot_dir, home)

        # change screenshot_dir
        args = ["--screenshot_dir", "dir"]
        rv = mt.parse_args(args)
        self.assertEqual(rv.cycle, "both")
        self.assertEqual(rv.postfix, "")
        self.assertEqual(rv.screenshot_dir, "dir")

        # change all
        args = [
            "-c",
            "transform",
            "--prefix",
            "pre",
            "--postfix",
            "key",
            "--screenshot_dir",
            "dir",
        ]
        rv = mt.parse_args(args)
        self.assertEqual(rv.cycle, "transform")
        self.assertEqual(rv.prefix, "pre")
        self.assertEqual(rv.postfix, "key")
        self.assertEqual(rv.screenshot_dir, "dir")


class MainTests(unittest.TestCase):
    @patch("randr_cycle.MonitorTest.parse_args")
    @patch("checkbox_support.helpers.display_info.get_monitor_config")
    @patch("randr_cycle.MonitorTest.gen_screenshot_path")
    @patch("randr_cycle.MonitorTest.tar_screenshot_dir")
    def test_cycle_both(
        self, mock_dir, mock_path, mock_config, mock_parse_args
    ):
        args_mock = MagicMock()
        args_mock.cycle = "both"
        args_mock.keyword = ""
        args_mock.screenshot_dir = "test"
        mock_parse_args.return_value = args_mock

        mock_path.return_value = "test"

        monitor_config_mock = MagicMock()
        mock_config.return_value = monitor_config_mock

        self.assertEqual(MonitorTest().main(), None)
        monitor_config_mock.cycle.assert_called_with(
            cycle_resolutions=True,
            resolution_filter=resolution_filter,
            cycle_transforms=True,
            post_cycle_action=action,
            path="test",
        )

        mock_dir.assert_called_with("test")

    @patch("randr_cycle.MonitorTest.parse_args")
    @patch("checkbox_support.helpers.display_info.get_monitor_config")
    @patch("randr_cycle.MonitorTest.gen_screenshot_path")
    @patch("randr_cycle.MonitorTest.tar_screenshot_dir")
    def test_cycle_resolution(
        self, mock_dir, mock_path, mock_config, mock_parse_args
    ):
        args_mock = MagicMock()
        args_mock.cycle = "resolution"
        args_mock.keyword = ""
        args_mock.screenshot_dir = "test"
        mock_parse_args.return_value = args_mock

        mock_path.return_value = "test"

        monitor_config_mock = MagicMock()
        mock_config.return_value = monitor_config_mock

        self.assertEqual(MonitorTest().main(), None)
        monitor_config_mock.cycle.assert_called_with(
            cycle_resolutions=True,
            resolution_filter=resolution_filter,
            cycle_transforms=False,
            post_cycle_action=action,
            path="test",
        )

        mock_dir.assert_called_with("test")

    @patch("randr_cycle.MonitorTest.parse_args")
    @patch("checkbox_support.helpers.display_info.get_monitor_config")
    @patch("randr_cycle.MonitorTest.gen_screenshot_path")
    @patch("randr_cycle.MonitorTest.tar_screenshot_dir")
    def test_cycle_transform(
        self, mock_dir, mock_path, mock_config, mock_parse_args
    ):
        args_mock = MagicMock()
        args_mock.cycle = "transform"
        args_mock.keyword = ""
        args_mock.screenshot_dir = "test"
        mock_parse_args.return_value = args_mock

        mock_path.return_value = "test"

        monitor_config_mock = MagicMock()
        mock_config.return_value = monitor_config_mock

        self.assertEqual(MonitorTest().main(), None)
        monitor_config_mock.cycle.assert_called_with(
            cycle_resolutions=False,
            resolution_filter=resolution_filter,
            cycle_transforms=True,
            post_cycle_action=action,
            path="test",
        )

        mock_dir.assert_called_with("test")

    @patch("randr_cycle.MonitorTest.parse_args")
    @patch("checkbox_support.helpers.display_info.get_monitor_config")
    def test_get_monitor_config_fail(self, mock_config, mock_parse_args):
        args_mock = MagicMock()
        args_mock.cycle = "transform"
        args_mock.keyword = ""
        args_mock.screenshot_dir = "test"
        mock_parse_args.return_value = args_mock

        mock_config.side_effect = ValueError("Error")
        with self.assertRaisesRegex(
            SystemExit, "Current host is not support: Error"
        ):
            MonitorTest().main()


if __name__ == "__main__":
    unittest.main()
