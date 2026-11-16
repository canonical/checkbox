import os
import unittest
from argparse import Namespace
from unittest.mock import call, patch

import sleep_time_check


class TestGetThresholds(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "SLEEP_THRESHOLD_OVERRIDE": "20",
            "RESUME_THRESHOLD_OVERRIDE": "15",
        },
        clear=True,
    )
    @patch("builtins.print")
    def test_environment_overrides_args_and_prints_warning(self, mock_print):
        args = Namespace(sleep_threshold=10, resume_threshold=5)

        thresholds = sleep_time_check.get_thresholds(args)

        self.assertEqual(thresholds, (20.0, 15.0))
        mock_print.assert_has_calls(
            [
                call("Overriding sleep threshold via environment: 20"),
                call("Overriding resume threshold via environment: 15"),
            ]
        )
