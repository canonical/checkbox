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
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

from io import StringIO
from unittest import TestCase

from unittest.mock import MagicMock, patch

from checkbox_support.scripts.snap_install import install, main


class TestInstall(TestCase):

    def setUp(self):
        self.snapd = MagicMock()

    def test_install_when_snap_not_installed(self):
        self.snapd.list.return_value = None

        install("foo", self.snapd, channel="edge", revision=42)

        self.snapd.list.assert_called_once_with("foo")
        self.snapd.install.assert_called_once_with(
            "foo", channel="edge", revision=42
        )
        self.snapd.refresh.assert_not_called()

    def test_refresh_when_snap_installed(self):
        self.snapd.list.return_value = {"name": "foo"}

        install("foo", self.snapd)

        self.snapd.list.assert_called_once_with("foo")
        self.snapd.refresh.assert_called_once_with(
            "foo", channel="stable", revision=None
        )
        self.snapd.install.assert_not_called()

    @patch("checkbox_support.scripts.snap_install.Snapd")
    def test_install_uses_default_snapd(self, mock_snapd_cls):
        snapd = mock_snapd_cls.return_value
        snapd.list.return_value = None

        install("foo", channel="beta")

        mock_snapd_cls.assert_called_once_with()
        snapd.install.assert_called_once_with(
            "foo", channel="beta", revision=None
        )

    @patch("sys.stderr", new_callable=StringIO)
    @patch("time.sleep")
    def test_install_retries_then_raises(self, mock_sleep, mock_stderr):
        self.snapd.list.return_value = None
        self.snapd.install.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            install("foo", self.snapd)

        # The install() wrapper retries up to three attempts in total.
        self.assertEqual(self.snapd.install.call_count, 3)
        self.assertEqual(self.snapd.refresh.call_count, 0)
        self.assertIn("All the attempts have failed!", mock_stderr.getvalue())


class TestMain(TestCase):

    @patch("checkbox_support.scripts.snap_install.install")
    @patch("checkbox_support.scripts.snap_install.Snapd")
    def test_main_forwards_args(self, mock_snapd_cls, mock_install):
        main(["foo", "--channel", "edge", "--revision", "42"])

        snapd = mock_snapd_cls.return_value
        mock_install.assert_called_once_with(
            "foo", snapd, channel="edge", revision=42
        )
