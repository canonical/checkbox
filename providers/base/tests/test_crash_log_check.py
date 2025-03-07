from datetime import datetime
import unittest
from unittest.mock import patch
import crash_log_check as CLC
from os import stat_result


class CrashLogCheckTests(unittest.TestCase):
    def test_no_crash_file_path(self):
        with patch("os.listdir") as mock_list:
            mock_list.return_value = []
            self.assertEqual(CLC.main(), 0)

    def test_all_new_crash_files(self):
        with patch("os.listdir") as mock_listdir, patch(
            "os.stat"
        ) as mock_stat, patch(
            "crash_log_check.get_boot_time"
        ) as mock_get_boot_time:
            mock_listdir.return_value = ["crash1.crash", "crash2.crash"]

            def mock_stat_side_effect(filename: str) -> stat_result:
                if filename == "crash1.crash":
                    t1 = datetime.timestamp(datetime(2024, 8, 1, 5, 30, 5))
                    t2 = datetime.timestamp(datetime(2024, 8, 1, 5, 31, 2))
                    t3 = datetime.timestamp(datetime(2024, 8, 1, 5, 31, 1))
                    return stat_result(
                        # slightly obscure syntax, we fill the first 7 args
                        # with 0 because it's unused, then fill the last 3 spots
                        # with timestamps (atime, mtime, ctime)
                        # unwrap the 7-zeros array and flatten with * operator
                        [*[0] * 7, t1, t2, t3]
                    )
                if filename == "crash2.crash":
                    t1 = datetime.timestamp(datetime(2024, 8, 1, 5, 40, 5))
                    t2 = datetime.timestamp(datetime(2024, 8, 1, 5, 40, 2))
                    t3 = datetime.timestamp(datetime(2024, 8, 1, 5, 40, 1))
                    return stat_result(
                        [*[0] * 7, 1723092286, 1722484746, 1722594746]
                    )
                raise Exception("Unexpected use of this mock")

            mock_stat.side_effect = mock_stat_side_effect
            mock_get_boot_time.return_value = datetime(2024, 8, 1, 5, 30, 3)

            logs = CLC.get_crash_logs()

            self.assertListEqual(["crash1.crash", 'crash2.crash'], logs)

        # def test_mixed_timestamps(self):
        #     NotImplemented()
