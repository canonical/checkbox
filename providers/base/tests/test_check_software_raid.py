import sys
import unittest
from unittest.mock import patch
import check_software_raid


class TestCheckSoftwareRAID(unittest.TestCase):

    def test_get_md_stat_intel_raid(self):

        expected_data = [{"device": "md126", "mode": "raid0"}]
        raid_data = check_software_raid.get_md_stat(
            "tests/test_data/mdstat_intel_rst.txt"
        )
        self.assertListEqual(raid_data, expected_data)

    def test_get_md_stat_multiple_raid(self):

        expected_data = [
            {"device": "md2", "mode": "raid1"},
            {"device": "md1", "mode": "raid0"},
        ]
        raid_data = check_software_raid.get_md_stat(
            "tests/test_data/mdstat_multiple_raid.txt"
        )
        self.assertListEqual(raid_data, expected_data)

    def test_get_md_stat_empty(self):

        raid_data = check_software_raid.get_md_stat(
            "tests/test_data/mdstat_none_raid.txt"
        )
        self.assertListEqual(raid_data, [])

    @patch("check_software_raid.dump_raid_info")
    @patch("check_software_raid.get_md_stat")
    def test_check_raid_mode_is_expected(self, mock_get_md, mock_dump_raid):

        mock_get_md.return_value = [
            {"device": "md2", "mode": "raid1"},
            {"device": "md1", "mode": "raid0"},
        ]

        check_software_raid.check_raid_mode_test("raid1 raid0")
        mock_get_md.assert_called_with()
        mock_dump_raid.assert_called_with(["md2", "md1"])

    @patch("check_software_raid.dump_raid_info")
    @patch("check_software_raid.get_md_stat")
    def test_check_raid_mode_param_with_redundant_space(
        self, mock_get_md, mock_dump_raid
    ):

        mock_get_md.return_value = [
            {"device": "md2", "mode": "raid1"},
            {"device": "md1", "mode": "raid0"},
        ]

        check_software_raid.check_raid_mode_test("  raid1  raid0  ")
        mock_get_md.assert_called_with()
        mock_dump_raid.assert_called_with(["md2", "md1"])

    @patch("check_software_raid.dump_raid_info")
    @patch("check_software_raid.get_md_stat")
    def test_check_raid_mode_is_not_expected(
        self, mock_get_md, mock_dump_raid
    ):

        mock_get_md.return_value = [
            {"device": "md2", "mode": "raid1"},
            {"device": "md1", "mode": "raid0"},
        ]

        with self.assertRaises(ValueError):
            check_software_raid.check_raid_mode_test("raid1")
            mock_get_md.assert_called_with()
            mock_dump_raid.assert_called_with()

    @patch("subprocess.run")
    def test_dump_raid_info(self, mock_run):

        check_software_raid.dump_raid_info(["md126", "md127"])
        self.assertEqual(mock_run.call_count, 2)


class TestArgumentParser(unittest.TestCase):

    def test_parser(self):
        sys.argv = ["check_software_raid.py", "--mode", "raid0 raid1"]
        args = check_software_raid.register_arguments()

        self.assertEqual(args.mode, "raid0 raid1")
