import unittest
from unittest.mock import mock_open, patch
import dvfs_gpu_check_governors as dvfs


class TestDvfsGpuCheckGovernors(unittest.TestCase):

    def test_all_expected_governors(self):
        # Test when all expected governors are present
        governors = "userspace powersave performance simple_ondemand"
        with patch("builtins.open", mock_open(read_data=governors)):
            result = dvfs.test_sysfs_attrs_read("mt8365")
        self.assertEqual(result, 0)

        with patch("builtins.open", mock_open(read_data=governors)):
            result = dvfs.test_sysfs_attrs_read("mt8364")
        self.assertEqual(result, 0)

    def test_unexpected_governor(self):
        # Test when an unexpected governor is present
        governors = "userspace powersave performance unexpected_governor"
        with patch("builtins.open", mock_open(read_data=governors)):
            result = dvfs.test_sysfs_attrs_read("mt8365")
        self.assertEqual(result, 1)

    @patch("builtins.open", mock_open(read_data=""))
    def test_empty_file(self):
        # Test when the file is empty
        governors = ""
        with patch("builtins.open", mock_open(read_data=governors)):
            result = dvfs.test_sysfs_attrs_read("mt8365")
        self.assertEqual(result, 0)

    @patch("dvfs_gpu_check_governors.test_sysfs_attrs_read")
    def test_main(self, mock_attrs_read):
        mock_attrs_read.return_value = 0
        with patch("sys.argv", ["script_name", "mt8395"]):
            result = dvfs.main()
        self.assertEqual(mock_attrs_read.call_count, 1)
        self.assertEqual(result, None)

    @patch("dvfs_gpu_check_governors.test_sysfs_attrs_read")
    def test_main_bad_args(self, mock_attrs_read):
        with patch("sys.argv", ["script_name", "bad_soc"]):
            with self.assertRaises(SystemExit):
                dvfs.main()
        self.assertEqual(mock_attrs_read.call_count, 0)

    @patch("dvfs_gpu_check_governors.test_sysfs_attrs_read")
    def test_main_wrong_attrs(self, mock_attrs_read):
        mock_attrs_read.return_value = 1
        with patch("sys.argv", ["script_name", "mt8395"]):
            with self.assertRaises(SystemExit):
                dvfs.main()
        self.assertEqual(mock_attrs_read.call_count, 1)
        self.assertEqual(mock_attrs_read.call_count, 1)
