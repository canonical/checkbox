import io
import logging
import unittest
from unittest.mock import patch, mock_open

import snap_update_test

from test_data.snap_update_test_data import (
    snapd_list_sample,
    snapd_list_no_kernel_snapd_gadget_snap,
    snapd_seed_glob_data,
    snapd_list_firefox_snap,
    snapd_find_firefox_snap,
    snap_info_pi_kernel,
)


class SnapUpdateTests(unittest.TestCase):
    @patch("snap_update_test.Snapd.list")
    def test_guess_snaps(self, mock_snapd_list):
        mock_snapd_list.return_value = snapd_list_sample
        snaps = snap_update_test.guess_snaps()
        expected_snaps = {"kernel": "pi-kernel", "snapd": "snapd", "gadget": "pi"}
        self.assertEqual(snaps, expected_snaps)

    @patch("snap_update_test.Snapd.list")
    def test_guess_snaps_nothing(self, mock_snapd_list):
        mock_snapd_list.return_value = snapd_list_no_kernel_snapd_gadget_snap
        snaps = snap_update_test.guess_snaps()
        self.assertEqual(snaps, {})

    @patch("snap_update_test.glob")
    def test_get_snap_base_rev(self, mock_glob):
        mock_glob.return_value = snapd_seed_glob_data
        snap_rev = snap_update_test.get_snap_base_rev()
        self.assertEqual(len(snap_rev), 4)
        self.assertEqual(snap_rev["pc-kernel"], "1289")

    @patch("snap_update_test.get_snap_base_rev")
    @patch("snap_update_test.Snapd.list")
    @patch("snap_update_test.Snapd.find")
    def test_get_snap_info(self, mock_snapd_find, mock_snapd_list, mock_base_revs):
        mock_base_revs.return_value = {"firefox": "2605"}
        mock_snapd_list.return_value = snapd_list_firefox_snap
        mock_snapd_find.return_value = snapd_find_firefox_snap
        expected_snap_info = {
            "installed_revision": "3026",
            "base_revision": "2605",
            "name": "firefox",
            "type": "app",
            "revisions": {
                "esr/candidate": "3052",
                "esr/stable": "3052",
                "latest/beta": "3099",
                "latest/candidate": "3068",
                "latest/edge": "3102",
                "latest/stable": "3068",
            },
            "tracking_channel": "latest/stable",
            "tracking_prefix": "latest/",
        }

        snap_info = snap_update_test.get_snap_info("firefox")
        self.assertEqual(snap_info, expected_snap_info)

    @patch("snap_update_test.get_snap_info")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_print_resource_info(self, mock_stdout, mock_snap_info):
        mock_snap_info.return_value = snap_info_pi_kernel
        expected_output = (
            "name: pi-kernel\ntype: kernel\n"
            "tracking: 22/stable\nbase_rev: 567\nstable_rev: 658\n"
            "candidate_rev: 663\nbeta_rev: 663\nedge_rev: 663\n"
            "original_installed_rev: 567\n\n"
        )
        snap_update_test.print_resource_info()
        self.assertEqual(mock_stdout.getvalue(), expected_output)


class SnapRefreshRevertTests(unittest.TestCase):
    @patch("snap_update_test.Snapd")
    @patch("snap_update_test.get_snap_info")
    def test_snap_refresh_same_revision(self, mock_snap_info, mock_snapd):
        mock_snap_info.return_value = {"installed_revision": "132"}
        srr = snap_update_test.SnapRefreshRevert(
            name="test", rev="132", info_path="/test/info"
        )
        logging.disable(logging.CRITICAL)
        self.assertEqual(srr.snap_refresh(), 1)

    @patch("builtins.open", new_callable=mock_open)
    @patch("snap_update_test.Snapd.refresh")
    @patch("snap_update_test.get_snap_info")
    def test_snap_refresh_different_revision(
        self, mock_snap_info, mock_snapd_refresh, mock_file
    ):
        mock_snap_info.return_value = {
            "installed_revision": "132",
            "tracking_channel": "22/beta",
        }
        mock_snapd_refresh.return_value = {"change": "1"}
        srr = snap_update_test.SnapRefreshRevert(
            name="test", rev="137", info_path="/test/info"
        )
        self.assertEqual(srr.snap_refresh(), 0)

    @patch("builtins.open", new_callable=mock_open)
    @patch("snap_update_test.Snapd.list")
    @patch("snap_update_test.Snapd.change")
    @patch("snap_update_test.json.load")
    @patch("snap_update_test.get_snap_info")
    def test_verify_refresh_ok(
        self,
        mock_snap_info,
        mock_json_load,
        mock_snapd_change,
        mock_snapd_list,
        mock_file,
    ):
        mock_snap_info.return_value = {
            "name": "test-snap",
            "installed_revision": "132",
            "tracking_channel": "22/beta",
        }
        mock_json_load.return_value = {
            "refresh_id": "1",
            "name": "test-snap",
            "destination_revision": "2",
        }
        mock_snapd_change.return_value = "Done"
        mock_snapd_list.return_value = {"revision": "2"}
        srr = snap_update_test.SnapRefreshRevert(
            name="test-snap", rev="2", info_path="/test/info"
        )
        self.assertEqual(srr.verify_refresh(), 0)

    @patch("builtins.open", new_callable=mock_open)
    @patch("snap_update_test.Snapd.list")
    @patch("snap_update_test.Snapd.change")
    @patch("snap_update_test.json.load")
    @patch("snap_update_test.get_snap_info")
    def test_verify_refresh_nok(
        self,
        mock_snap_info,
        mock_json_load,
        mock_snapd_change,
        mock_snapd_list,
        mock_file,
    ):
        mock_snap_info.return_value = {
            "name": "test-snap",
            "installed_revision": "132",
            "tracking_channel": "22/beta",
        }
        mock_json_load.return_value = {
            "refresh_id": "1",
            "name": "test-snap",
            "destination_revision": "2",
        }
        mock_snapd_change.return_value = "Done"
        mock_snapd_list.return_value = {"revision": "1"}
        srr = snap_update_test.SnapRefreshRevert(
            name="test-snap", rev="2", info_path="/test/info"
        )

        logging.disable(logging.CRITICAL)
        self.assertEqual(srr.verify_refresh(), 1)

    @patch("builtins.open", new_callable=mock_open)
    @patch("snap_update_test.Snapd.list")
    @patch("snap_update_test.Snapd.change")
    @patch("snap_update_test.json.load")
    @patch("snap_update_test.get_snap_info")
    def test_verify_revert_ok(
        self,
        mock_snap_info,
        mock_json_load,
        mock_snapd_change,
        mock_snapd_list,
        mock_file,
    ):
        mock_snap_info.return_value = {
            "name": "test-snap",
            "installed_revision": "132",
            "tracking_channel": "22/beta",
        }
        mock_json_load.return_value = {
            "revert_id": "1",
            "name": "test-snap",
            "original_revision": "2",
        }
        mock_snapd_change.return_value = "Done"
        mock_snapd_list.return_value = {"revision": "2"}
        srr = snap_update_test.SnapRefreshRevert(
            name="test-snap", rev="2", info_path="/test/info"
        )
        self.assertEqual(srr.verify_revert(), 0)

    @patch("builtins.open", new_callable=mock_open)
    @patch("snap_update_test.Snapd.list")
    @patch("snap_update_test.Snapd.change")
    @patch("snap_update_test.json.load")
    @patch("snap_update_test.get_snap_info")
    def test_verify_revert_nok(
        self,
        mock_snap_info,
        mock_json_load,
        mock_snapd_change,
        mock_snapd_list,
        mock_file,
    ):
        mock_snap_info.return_value = {
            "name": "test-snap",
            "installed_revision": "132",
            "tracking_channel": "22/beta",
        }
        mock_json_load.return_value = {
            "revert_id": "1",
            "name": "test-snap",
            "original_revision": "2",
        }
        mock_snapd_change.return_value = "Done"
        mock_snapd_list.return_value = {"revision": "1"}
        srr = snap_update_test.SnapRefreshRevert(
            name="test-snap", rev="2", info_path="/test/info"
        )
        logging.disable(logging.CRITICAL)
        self.assertEqual(srr.verify_revert(), 1)

    @patch("snap_update_test.Snapd.revert")
    @patch("snap_update_test.get_snap_info")
    def test_snap_revert(self, mock_snap_info, mock_snapd_revert):
        mock_file_data = (
            '{"name": "test-snap", "original_revision": "10", '
            '"destination_revision": "20", "refresh_id": "80"}'
        )
        mock_snapd_revert.return_value = {"change": 99}
        srr = snap_update_test.SnapRefreshRevert(
            name="test-snap", rev="2", info_path="/test/info"
        )
        mock_snap_info.return_value = {
            "name": "test-snap",
            "installed_revision": "132",
            "tracking_channel": "22/beta",
        }
        with patch("builtins.open", mock_open(read_data=mock_file_data)) as m:
            srr.snap_revert()
            mock_snapd_revert.assert_called()
            m.assert_called_with("/test/info", "w")
