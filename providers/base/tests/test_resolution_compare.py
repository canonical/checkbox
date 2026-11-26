# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
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
# along with Checkbox. If not, see <http://www.gnu.org/licenses/>.

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules["dbus"] = MagicMock()
sys.modules["dbus.mainloop.glib"] = MagicMock()
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()

import resolution_compare  # noqa: E402


class TestGetResolutions(unittest.TestCase):
    @patch("checkbox_support.helpers.display_info.get_monitor_config")
    def test_uses_monitor_config(self, mock_get_monitor_config):
        mock_config = mock_get_monitor_config.return_value
        mock_config.get_current_resolutions.return_value = {
            "eDP-1": "1920x1080"
        }

        self.assertEqual(
            resolution_compare.get_resolutions(), {"eDP-1": "1920x1080"}
        )


class TestFormatResolutions(unittest.TestCase):
    def test_sorted_by_connector(self):
        output = resolution_compare.format_resolutions(
            {"HDMI-1": "1280x720", "DP-1": "2560x1440", "eDP-1": "1920x1080"}
        )

        self.assertEqual(
            output,
            "DP-1: 2560x1440\nHDMI-1: 1280x720\neDP-1: 1920x1080\n",
        )

    def test_empty(self):
        self.assertEqual(resolution_compare.format_resolutions({}), "")


class TestLoadResolutions(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "resolutions.txt"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_skips_blank_lines(self):
        self.path.write_text("eDP-1: 1920x1080\n\nHDMI-1: 1280x720\n")

        self.assertEqual(
            resolution_compare.load_resolutions(self.path),
            {"eDP-1": "1920x1080", "HDMI-1": "1280x720"},
        )

    def test_round_trip_with_format(self):
        resolutions = {"eDP-1": "1920x1080", "HDMI-1": "1280x720"}
        self.path.write_text(
            resolution_compare.format_resolutions(resolutions)
        )

        self.assertEqual(
            resolution_compare.load_resolutions(self.path), resolutions
        )


@patch("sys.stdout", new_callable=io.StringIO)
@patch("resolution_compare.get_resolutions")
class TestRecord(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "resolutions.txt"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_writes_and_prints(self, mock_get_resolutions, mock_stdout):
        mock_get_resolutions.return_value = {
            "HDMI-1": "1280x720",
            "eDP-1": "1920x1080",
        }

        resolution_compare.record(self.path)

        expected = "HDMI-1: 1280x720\neDP-1: 1920x1080\n"
        self.assertEqual(self.path.read_text(), expected)
        self.assertEqual(mock_stdout.getvalue(), expected)


@patch("sys.stdout", new_callable=io.StringIO)
@patch("resolution_compare.get_resolutions")
class TestCompare(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "resolutions.txt"
        self.path.write_text("HDMI-1: 1280x720\neDP-1: 1920x1080\n")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_match(self, mock_get_resolutions, mock_stdout):
        mock_get_resolutions.return_value = {
            "eDP-1": "1920x1080",
            "HDMI-1": "1280x720",
        }

        resolution_compare.compare(self.path)

        self.assertIn("Resolutions match.", mock_stdout.getvalue())

    def test_resolution_changed(self, mock_get_resolutions, mock_stdout):
        mock_get_resolutions.return_value = {
            "eDP-1": "1280x800",
            "HDMI-1": "1280x720",
        }

        with self.assertRaises(SystemExit) as cm:
            resolution_compare.compare(self.path)

        self.assertEqual(
            str(cm.exception),
            "eDP-1: resolution changed from 1920x1080 to 1280x800",
        )

    def test_monitor_missing(self, mock_get_resolutions, mock_stdout):
        mock_get_resolutions.return_value = {"eDP-1": "1920x1080"}

        with self.assertRaises(SystemExit) as cm:
            resolution_compare.compare(self.path)

        self.assertEqual(
            str(cm.exception),
            "HDMI-1: was 1280x720, now missing or inactive",
        )

    def test_new_monitor(self, mock_get_resolutions, mock_stdout):
        mock_get_resolutions.return_value = {
            "eDP-1": "1920x1080",
            "HDMI-1": "1280x720",
            "DP-1": "2560x1440",
        }

        with self.assertRaises(SystemExit) as cm:
            resolution_compare.compare(self.path)

        self.assertEqual(
            str(cm.exception),
            "DP-1: new monitor, not recorded before (2560x1440)",
        )

    def test_reports_all_errors(self, mock_get_resolutions, mock_stdout):
        mock_get_resolutions.return_value = {
            "eDP-1": "1280x800",
            "DP-1": "2560x1440",
        }

        with self.assertRaises(SystemExit) as cm:
            resolution_compare.compare(self.path)

        self.assertEqual(
            str(cm.exception).splitlines(),
            [
                "DP-1: new monitor, not recorded before (2560x1440)",
                "HDMI-1: was 1280x720, now missing or inactive",
                "eDP-1: resolution changed from 1920x1080 to 1280x800",
            ],
        )
        self.assertNotIn("Resolutions match.", mock_stdout.getvalue())


class TestParseArgs(unittest.TestCase):
    def test_record(self):
        args = resolution_compare.parse_args(["record", "/tmp/out.txt"])

        self.assertEqual(args.action, "record")
        self.assertEqual(args.file, Path("/tmp/out.txt"))

    def test_compare(self):
        args = resolution_compare.parse_args(["compare", "/tmp/out.txt"])

        self.assertEqual(args.action, "compare")
        self.assertEqual(args.file, Path("/tmp/out.txt"))

    @patch("sys.stderr", new_callable=io.StringIO)
    def test_action_required(self, mock_stderr):
        with self.assertRaises(SystemExit):
            resolution_compare.parse_args([])

    @patch("sys.stderr", new_callable=io.StringIO)
    def test_file_required(self, mock_stderr):
        with self.assertRaises(SystemExit):
            resolution_compare.parse_args(["record"])


@patch("resolution_compare.compare")
@patch("resolution_compare.record")
class TestMain(unittest.TestCase):
    def test_record(self, mock_record, mock_compare):
        resolution_compare.main(["record", "/tmp/out.txt"])

        mock_record.assert_called_once_with(Path("/tmp/out.txt"))
        mock_compare.assert_not_called()

    def test_compare(self, mock_record, mock_compare):
        resolution_compare.main(["compare", "/tmp/out.txt"])

        mock_compare.assert_called_once_with(Path("/tmp/out.txt"))
        mock_record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
