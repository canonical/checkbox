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
    @patch("subprocess.check_output")
    @patch("time.sleep")
    def test_action_with_path(self, mock_sleep, mock_subprocess):
        filename = "monitor_1920x1080_normal_"
        path = "/tmp/screenshots"
        action(filename, path=path)

        expected_path_and_filename = "{}/{}.jpg".format(path, filename)
        mock_subprocess.assert_called_once_with(
            ["gnome-screenshot", "-f", expected_path_and_filename]
        )
        mock_sleep.assert_called_once_with(5)

    @patch("subprocess.check_output")
    @patch("time.sleep")
    def test_action_without_path(self, mock_sleep, mock_subprocess):
        filename = "monitor_1920x1080_normal_"
        action(filename)

        expected_path_and_filename = filename + ".jpg"
        mock_subprocess.assert_called_once_with(
            ["gnome-screenshot", "-f", expected_path_and_filename]
        )
        mock_sleep.assert_called_once_with(5)

    @patch("subprocess.check_output")
    @patch("time.sleep")
    def test_action_subprocess_error(self, mock_sleep, mock_subprocess):
        filename = "monitor_1920x1080_normal_"
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            1, "gnome-screenshot"
        )

        with self.assertRaises(subprocess.CalledProcessError):
            action(filename)


class GenScreenshotPath(unittest.TestCase):
    """
    This function should generate dictionary such as
    [screenshot_dir]_[keyword]
    """

    @patch("os.makedirs")
    def test_before_suspend_without_keyword(self, mock_mkdir):

        mt = MonitorTest()
        with patch("builtins.open", mock_open(read_data="0")) as mock_file:
            self.assertEqual(
                mt.gen_screenshot_path("", "", "test"), "test/xrandr_screens"
            )
        mock_file.assert_called_with("/sys/power/suspend_stats/success", "r")
        mock_mkdir.assert_called_with("test/xrandr_screens", exist_ok=True)

    @patch("os.makedirs")
    def test_after_suspend_without_keyword(self, mock_mkdir):

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

    @patch("os.makedirs")
    def test_with_keyword(self, mock_mkdir):

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
