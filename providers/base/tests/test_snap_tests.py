#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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
#

import os
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

import snap_tests


class SnapTestsUtilityTests(unittest.TestCase):
    def test_pretty_exit(self):

        @snap_tests.pretty_exit_async_exception
        def f():
            raise snap_tests.AsyncException("Test text")

        with self.assertRaises(SystemExit) as e:
            f()
        self.assertIn("Test text", str(e.exception))

    def test_remove_if_present(self):
        snapd_mock = MagicMock()
        snapd_mock.list.return_value = True
        snap_tests.remove_if_present(snapd_mock, "snap_name")
        self.assertTrue(snapd_mock.remove.called)

        snapd_mock = MagicMock()
        snapd_mock.list.return_value = None
        snap_tests.remove_if_present(snapd_mock, "snap_name")
        self.assertFalse(snapd_mock.remove.called)

    @patch("snap_tests.Snapd")
    def test_get_snapd_client(self, Snapd_mock):
        snapd = snap_tests.get_snapd_client()
        self.assertTrue(Snapd_mock.called)
        self.assertEqual(Snapd_mock(), snapd)


class SnapCommandsTests(unittest.TestCase):
    @patch("snap_tests.Snapd")
    def test_snap_search(self, Snapd_mock):
        s = Snapd_mock()
        s.find.return_value = [
            {
                "id": "some_id",
                "name": "some_name",
                "developer": "some_developer",
            }
        ]

        self.assertEqual(snap_tests.SnapSearch().invoked(), 0)

        s.find.return_value = []
        self.assertEqual(snap_tests.SnapSearch().invoked(), 1)

    @patch("snap_tests.Snapd")
    @patch("sys.argv")
    @patch("argparse.ArgumentParser")
    def test_snap_install(self, AP_mock, argv_mock, Snapd_mock):
        s = Snapd_mock()
        s.list.return_value = [{"name": snap_tests.TEST_SNAP}]

        self.assertEqual(snap_tests.SnapInstall().invoked(), 0)

        s.list.return_value = []
        self.assertEqual(snap_tests.SnapInstall().invoked(), 1)

    @patch("snap_tests.Snapd")
    def test_snap_refresh(self, Snapd_mock):
        s = Snapd_mock()
        s.list.return_value = {"revision": "100"}
        self.assertEqual(snap_tests.SnapRefresh().invoked(), 1)

        s.list.side_effect = [None, {"revision": "1"}, {"revision": "2"}]
        self.assertEqual(snap_tests.SnapRefresh().invoked(), 0)

    @patch("snap_tests.Snapd")
    def test_snap_revert(self, Snapd_mock):
        s = Snapd_mock()
        s.list.side_effect = [
            None,
            {"revision": "2"},
            {"revision": "1"},
        ]
        s.info.return_value = {
            "channels": {"latest/stable": {"revision": "1"}}
        }
        self.assertEqual(snap_tests.SnapRevert().invoked(), 0)

        s.list.side_effect = [
            None,
            {"revision": "2"},
            {"revision": "2"},
        ]
        self.assertEqual(snap_tests.SnapRevert().invoked(), 1)

    @patch("snap_tests.Snapd")
    def test_snap_remove(self, Snapd_mock):
        s = Snapd_mock()
        s.list.side_effect = [True, []]
        self.assertEqual(snap_tests.SnapRemove().invoked(), 0)

        s.list.side_effect = [True, [{"name": snap_tests.TEST_SNAP}]]
        self.assertEqual(snap_tests.SnapRemove().invoked(), 1)

    @patch("snap_tests.Snapd")
    def test_snap_reupdate(self, Snapd_mock):
        s = Snapd_mock()
        s.list.side_effect = [None]
        s.info.return_value = {"channels": {"latest/edge": {"revision": "5"}}}
        s.list.side_effect = [None, {"revision": "5"}]
        self.assertIsNone(snap_tests.SnapReupdate().invoked())

        s.list.side_effect = [None, {"revision": "99"}]
        self.assertEqual(snap_tests.SnapReupdate().invoked(), 1)
