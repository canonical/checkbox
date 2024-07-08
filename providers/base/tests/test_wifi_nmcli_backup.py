#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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


import unittest
from unittest.mock import patch, call, ANY

from wifi_nmcli_backup import (
    legacy_nmcli,
    save_connections,
    restore_connections,
)


class WifiNmcliBackupTests(unittest.TestCase):
    @patch("wifi_nmcli_backup.sp")
    def test_legacy_nmcli_true(self, subprocess_mock):
        subprocess_mock.check_output.return_value = (
            b"nmcli tool, version 1.11.3-5"
        )
        self.assertTrue(legacy_nmcli())

    @patch("wifi_nmcli_backup.sp")
    def test_legacy_nmcli_false(self, subprocess_mock):
        subprocess_mock.check_output.return_value = (
            b"nmcli tool, version 1.46.0-2"
        )
        self.assertFalse(legacy_nmcli())

    @patch("wifi_nmcli_backup.os.makedirs")
    @patch("wifi_nmcli_backup.print")
    def test_save_connections_empty_list(self, mock_print, mock_makedirs):
        save_connections([])
        mock_print.assert_called_once_with(
            "No stored 802.11 connections to save"
        )
        mock_makedirs.assert_called_once()

    @patch("wifi_nmcli_backup.os.makedirs")
    @patch("wifi_nmcli_backup.os.path.exists", return_value=True)
    def test_save_connections_savedir_exists(self, mock_makedirs, mock_exists):
        mock_makedirs.assert_not_called()

    @patch("wifi_nmcli_backup.os.path.exists", return_value=False)
    @patch("wifi_nmcli_backup.print")
    @patch("wifi_nmcli_backup.os.makedirs")
    def test_save_connections_non_existing_files(
        self, mock_makedirs, mock_print, mock_exists
    ):
        keyfile_list = [
            "/fake/path/to/connection1",
            "/fake/path/to/connection2",
        ]

        save_connections(keyfile_list)
        expected_calls = [
            call("Save connection {}".format(f)) for f in keyfile_list
        ]
        expected_calls += [
            call("  No stored connection found at {}".format(f))
            for f in keyfile_list
        ]
        mock_print.assert_has_calls(expected_calls, any_order=True)
        mock_makedirs.assert_called_once()

    @patch(
        "wifi_nmcli_backup.shutil.copy",
        return_value="/fake/backup/location/connection1",
    )
    @patch(
        "wifi_nmcli_backup.os.path.exists",
        side_effect=lambda path: True if "connection" in path else False,
    )
    @patch("wifi_nmcli_backup.print")
    @patch("wifi_nmcli_backup.os.makedirs")
    def test_save_connections_existing_files(
        self, mock_makedirs, mock_print, mock_exists, mock_copy
    ):
        keyfile_list = ["/etc/NetworkManager/system-connections/connection1"]
        save_connections(keyfile_list)
        mock_makedirs.assert_called_once()
        mock_copy.assert_called_once_with(
            "/etc/NetworkManager/system-connections/connection1", ANY
        )

        expected_print_calls = [
            call(
                "Save connection "
                "/etc/NetworkManager/system-connections/connection1"
            ),
            call(
                "  Found file "
                "/etc/NetworkManager/system-connections/connection1"
            ),
            call("  Saved copy at /fake/backup/location/connection1"),
        ]
        mock_print.assert_has_calls(expected_print_calls, any_order=True)

    @patch("wifi_nmcli_backup.print")
    @patch("wifi_nmcli_backup.glob.glob", return_value=[])
    def test_restore_connections_no_stored_connections(
        self, mock_glob, mock_print
    ):
        restore_connections()
        mock_print.assert_called_once_with(
            "No stored 802.11 connections found"
        )

    @patch("wifi_nmcli_backup.shutil.move")
    @patch("wifi_nmcli_backup.SAVE_DIR", "/stored-system-connections")
    @patch(
        "wifi_nmcli_backup.glob.glob",
        return_value=[
            "/stored-system-connections/etc/NetworkManager/system-connections"
            "/connection1.nmconnection",
            "/stored-system-connections/run/NetworkManager/system-connections"
            "/connection2.nmconnection",
        ],
    )
    @patch("wifi_nmcli_backup.print")
    def test_restore_connections_existing_files(
        self, mock_print, mock_glob, mock_move
    ):
        restore_connections()
        expected_calls = [
            call(
                "/stored-system-connections/etc/NetworkManager"
                "/system-connections/connection1.nmconnection",
                "/etc/NetworkManager/system-connections"
                "/connection1.nmconnection",
            ),
            call(
                "/stored-system-connections/run/NetworkManager"
                "/system-connections/connection2.nmconnection",
                "/run/NetworkManager/system-connections"
                "/connection2.nmconnection",
            ),
        ]

        mock_move.assert_has_calls(expected_calls, any_order=True)
