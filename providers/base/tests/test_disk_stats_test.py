import argparse
import textwrap
import unittest
from unittest.mock import MagicMock, patch

import disk_stats_test


class DiskStatsTest(unittest.TestCase):
    @patch("disk_stats_test.time.sleep", MagicMock())
    @patch("disk_stats_test.subprocess.run", MagicMock())
    @patch(
        "disk_stats_test.Path.stat",
        MagicMock(return_value=MagicMock(st_size=1)),
    )
    @patch("disk_stats_test.Path.is_file", MagicMock(return_value=True))
    @patch("disk_stats_test.Path.exists", MagicMock(return_value=True))
    @patch(
        "disk_stats_test.argparse.ArgumentParser.parse_args",
        MagicMock(return_value=argparse.Namespace(disk="fake0")),
    )
    @patch(
        "disk_stats_test.Path.read_text",
        MagicMock(
            side_effect=[
                textwrap.dedent("""\
                    major minor  #blocks  name
                    8        0  976762584 fake0
                """).strip(),
                textwrap.dedent("""\
                    8       0 fake0 100 0 800 20 50 0 400 10 0 30 30 0 0 0 0
                """).strip(),
                "100 0 800 20 50 0 400 10 0 30 30 0 0 0 0\n",
                textwrap.dedent("""\
                    8       0 fake0 101 0 808 21 50 0 400 10 0 31 31 0 0 0 0
                """).strip(),
                "101 0 808 21 50 0 400 10 0 31 31 0 0 0 0\n",
            ]
        ),
    )
    def test_fake_disk(self):
        disk_stats_test.main()
