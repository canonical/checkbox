import io
import logging
import unittest
from unittest.mock import patch, mock_open, MagicMock

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
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    @patch("snap_update_test.Snapd.list")
    def test_guess_snaps(self, mock_snapd_list):
        mock_snapd_list.return_value = snapd_list_sample
        snaps = snap_update_test.guess_snaps()
        expected_snaps = ["pi-kernel", "snapd", "pi"]
        self.assertEqual(snaps, expected_snaps)

    @patch("snap_update_test.Snapd.list")
    def test_guess_snaps_nothing(self, mock_snapd_list):
        mock_snapd_list.return_value = snapd_list_no_kernel_snapd_gadget_snap
        snaps = snap_update_test.guess_snaps()
        self.assertEqual(snaps, [])

    @patch("snap_update_test.Path.glob")
    def test_get_snaps_base_rev(self, mock_glob):
        mock_glob.return_value = snapd_seed_glob_data
        snap_rev = snap_update_test.get_snaps_base_rev()
        self.assertEqual(len(snap_rev), 4)
        self.assertEqual(snap_rev["pc-kernel"], "1289")

    @patch("builtins.open", new_callable=mock_open)
    def test_load_change_info_file_not_found(self, mock_open):
        mock_open.side_effect = FileNotFoundError()
        with self.assertRaises(SystemExit):
            snap_update_test.load_change_info("/file/not/found")

    @patch("builtins.open", new_callable=mock_open)
    @patch("snap_update_test.json")
    def test_load_change_info(self, mock_json, mock_open):
        snap_update_test.load_change_info("test")
        self.assertTrue(mock_json.load.called)

    @patch("snap_update_test.print_resource_info")
    def test_main_print_resource(self, mock_print_resource_info):
        args = ["--resource"]
        snap_update_test.main(args)
        self.assertTrue(mock_print_resource_info.called)

    @patch("snap_update_test.SnapRefreshRevert")
    def test_main_refresh(self, mock_srr):
        args = ["--refresh", "--info-path", "/tmp/change.json", "chromium"]
        snap_update_test.main(args)
        instance = mock_srr.return_value
        self.assertTrue(instance.snap_refresh.called)

    @patch("snap_update_test.SnapRefreshRevert")
    def test_main_verify_refresh(self, mock_srr):
        args = [
            "--verify-refresh",
            "--info-path",
            "/tmp/change.json",
            "chromium",
        ]
        snap_update_test.main(args)
        instance = mock_srr.return_value
        instance.verify.assert_called_with("refresh")

    @patch("snap_update_test.SnapRefreshRevert")
    def test_main_revert(self, mock_srr):
        args = ["--revert", "--info-path", "/tmp/change.json", "chromium"]
        snap_update_test.main(args)
        instance = mock_srr.return_value
        self.assertTrue(instance.snap_revert.called)

    @patch("snap_update_test.SnapRefreshRevert")
    def test_main_verify_revert(self, mock_srr):
        args = [
            "--verify-revert",
            "--info-path",
            "/tmp/change.json",
            "chromium",
        ]
        snap_update_test.main(args)
        instance = mock_srr.return_value
        instance.verify.assert_called_with("revert")


class SnapInfoTests(unittest.TestCase):
    @patch("snap_update_test.get_snaps_base_rev")
    @patch("snap_update_test.Snapd")
    def test_init(self, mock_snapd, mock_base_revs):
        mock_base_revs.return_value = {"firefox": "2605"}
        mock_snapd.return_value.list.return_value = snapd_list_firefox_snap
        mock_snapd.return_value.find.return_value = snapd_find_firefox_snap

        snap_info = snap_update_test.SnapInfo("firefox")
        self.assertEqual(snap_info.installed_revision, "3026")
        self.assertEqual(snap_info.base_revision, "2605")
        self.assertEqual(snap_info.tracking_channel, "latest/stable")
        self.assertEqual(snap_info.tracking_prefix, "latest/")
        self.assertEqual(snap_info.stable_revision, "3068")
        self.assertEqual(snap_info.candidate_revision, "3068")
        self.assertEqual(snap_info.beta_revision, "3099")
        self.assertEqual(snap_info.edge_revision, "3102")

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_print_as_resource(self, mock_stdout):
        mock_self = MagicMock()
        snap_update_test.SnapInfo.print_as_resource(mock_self)
        self.assertIn("name:", mock_stdout.getvalue())
        self.assertIn("type:", mock_stdout.getvalue())
        self.assertIn("tracking:", mock_stdout.getvalue())
        self.assertIn("base_rev:", mock_stdout.getvalue())
        self.assertIn("stable_rev:", mock_stdout.getvalue())
        self.assertIn("candidate_rev:", mock_stdout.getvalue())
        self.assertIn("beta_rev:", mock_stdout.getvalue())
        self.assertIn("edge_rev:", mock_stdout.getvalue())
        self.assertIn("original_installed_rev:", mock_stdout.getvalue())
        # Make sure there is a blank line at the end, as this is required by
        # Checkbox resource jobs
        self.assertTrue(mock_stdout.getvalue().endswith("\n\n"))


class SnapRefreshRevertTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    @patch("snap_update_test.SnapInfo")
    @patch("snap_update_test.Snapd")
    def test_init(self, mock_snapd, mock_snapinfo):
        srr = snap_update_test.SnapRefreshRevert(
            name="test",
            revision="1",
            info_path="/test",
            timeout="10",
        )
        self.assertEqual(srr.name, "test")
        self.assertEqual(srr.path, "/test")
        self.assertEqual(srr.revision, "1")
        self.assertEqual(srr.timeout, "10")

    def test_snap_refresh_same_revision(self):
        mock_self = MagicMock()
        mock_self.revision = "1"
        mock_snap_info = MagicMock()
        mock_snap_info.installed_revision = "1"
        mock_self.snap_info = mock_snap_info
        with self.assertRaises(SystemExit):
            snap_update_test.SnapRefreshRevert.snap_refresh(mock_self)

    @patch("snap_update_test.save_change_info")
    def test_snap_refresh_different_revision(self, mock_save_change_info):
        mock_self = MagicMock()
        mock_self.revision = "1"
        mock_snap_info = MagicMock()
        mock_snap_info.installed_revision = "2"
        mock_self.snap_info = mock_snap_info
        snap_update_test.SnapRefreshRevert.snap_refresh(mock_self)
        self.assertTrue(mock_self.snapd.refresh.called)

    @patch("snap_update_test.Snapd.revert")
    @patch("snap_update_test.load_change_info")
    @patch("snap_update_test.save_change_info")
    def test_snap_revert(
        self, mock_save_change_info, mock_load_change_info, mock_snapd_revert
    ):
        mock_self = MagicMock()
        snap_update_test.SnapRefreshRevert.snap_revert(mock_self)
        self.assertTrue(snap_update_test.load_change_info.called)
        self.assertTrue(snap_update_test.save_change_info.called)

    def test_verify_invalid(self):
        mock_self = MagicMock()
        with self.assertRaises(SystemExit):
            snap_update_test.SnapRefreshRevert.verify(
                mock_self, type="invalid"
            )

    @patch("snap_update_test.load_change_info")
    def test_verify_refresh_wrong_revision(self, mock_load_change):
        mock_self = MagicMock()
        mock_load_change.return_value = {
            "change_id": "1",
            "destination_revision": "1",
        }
        mock_self.snapd.list.return_value = {"revision": "2"}
        with self.assertRaises(SystemExit):
            snap_update_test.SnapRefreshRevert.verify(
                mock_self, type="refresh"
            )

    @patch("snap_update_test.load_change_info")
    def test_verify_refresh_expected_revision(self, mock_load_change):
        mock_self = MagicMock()
        mock_load_change.return_value = {
            "change_id": "1",
            "destination_revision": "1",
        }
        mock_self.snapd.list.return_value = {"revision": "1"}
        snap_update_test.SnapRefreshRevert.verify(mock_self, type="refresh")

    @patch("snap_update_test.load_change_info")
    def test_verify_reverting_wrong_revision(self, mock_load_change):
        mock_self = MagicMock()
        mock_load_change.return_value = {
            "change_id": "1",
            "original_revision": "1",
        }
        mock_self.snapd.list.return_value = {"revision": "2"}
        with self.assertRaises(SystemExit):
            snap_update_test.SnapRefreshRevert.verify(mock_self, type="revert")

    def test_wait_for_snap_change(self):
        mock_self = MagicMock()
        mock_self.snapd.change.return_value = "Done"
        snap_update_test.SnapRefreshRevert.wait_for_snap_change(
            mock_self, change_id=1, type="refresh"
        )

    def test_wait_for_snap_change_error(self):
        mock_self = MagicMock()
        mock_self.snapd.change.return_value = "Error"
        mock_self.snapd.tasks.return_value = [
            {
                "id": "3285",
                "kind": "auto-connect",
                "log": ["ERROR cannot finish pi-kernel installation"],
                "progress": {"done": 1, "label": "", "total": 1},
                "ready-time": "2023-10-20T04:36:29.493419161Z",
                "spawn-time": "2023-10-20T04:34:44.614034129Z",
                "status": "Error",
                "summary": "Automatically connect eligible plugs and slots",
            }
        ]
        with self.assertRaises(SystemExit):
            snap_update_test.SnapRefreshRevert.wait_for_snap_change(
                mock_self, change_id=1, type="refresh"
            )

    def test_wait_for_snap_change_timeout(self):
        mock_self = MagicMock()
        mock_self.timeout = -1
        with self.assertRaises(SystemExit):
            snap_update_test.SnapRefreshRevert.wait_for_snap_change(
                mock_self, change_id=1, type="refresh"
            )

    @patch("snap_update_test.time.time")
    @patch("snap_update_test.time.sleep")
    def test_wait_for_snap_change_ongoing(self, mock_sleep, mock_time):
        mock_self = MagicMock()
        mock_self.timeout = 300
        mock_self.snapd.change.side_effect = ["Doing", "Done"]
        mock_time.return_value = 1
        snap_update_test.SnapRefreshRevert.wait_for_snap_change(
            mock_self, change_id=1, type="refresh"
        )
