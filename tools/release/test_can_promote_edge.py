import unittest
from unittest.mock import patch

import can_promote_edge


class TestCanPromoteEdge(unittest.TestCase):
    def test_get_latest_ok_head_ok(self):
        # get_lastest_ok is able to scroll back and find the most
        # recent passing build
        builds = [
            {"headSha": "abc", "conclusion": "failure"},
            {"headSha": "cde", "conclusion": "failure"},
            {"headSha": "correct_hash", "conclusion": "success"},
            {"headSha": "stale_hash", "conclusion": "success"},
        ]
        correct_hash = can_promote_edge.get_latest_ok_head(builds)
        self.assertEqual(correct_hash, "correct_hash")

    def test_get_latest_ok_head_fail(self):
        # if no build has passed in the last 20 run, fail gracefully
        builds = [
            {"headSha": "abc", "conclusion": "failure"},
            {"headSha": "cde", "conclusion": "failure"},
        ]
        with self.assertRaises(SystemExit):
            _ = can_promote_edge.get_latest_ok_head(builds)

    @patch("subprocess.check_output")
    def test_beta_validation_matches_successful_daily_ok(
        self, check_output_mock
    ):
        check_output_mock.side_effect = [
            '[{"headSha" : "correct_hash", "conclusion" : "success"}]',
            "correct_hash",
        ]

        can_promote_edge.main()

    @patch("subprocess.check_output")
    def test_beta_validation_matches_successful_daily_fail(
        self, check_output_mock
    ):
        check_output_mock.side_effect = [
            '[{"headSha" : "correct_hash", "conclusion" : "success"}]',
            "stale_hash",
        ]
        with self.assertRaises(SystemExit):
            can_promote_edge.main()
