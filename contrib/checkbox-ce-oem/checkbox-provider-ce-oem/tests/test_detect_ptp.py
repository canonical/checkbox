import unittest
from pathlib import Path
from unittest.mock import patch

import detect_ptp


class TestDetectPtp(unittest.TestCase):
    @patch("detect_ptp.find_ptp_device", return_value=Path("/dev/ptp0"))
    def test_interface_with_ptp_passes(self, mock_find):
        with patch("builtins.print") as mock_print:
            detect_ptp.main(["eth0"])
        mock_find.assert_called_once_with("eth0")
        mock_print.assert_called_once_with(
            "[ OK ] PTP device '/dev/ptp0' exists for 'eth0'"
        )

    @patch("detect_ptp.find_ptp_device", return_value=None)
    def test_interface_without_ptp_fails(self, mock_find):
        with self.assertRaises(SystemExit) as cm:
            detect_ptp.main(["eth0"])
        self.assertEqual(
            str(cm.exception), "'eth0' does not support hardware PTP"
        )

    def test_requires_exactly_one_interface(self):
        for argv in ([], ["eth0", "eth1"]):
            with self.assertRaises(SystemExit), patch("sys.stderr"):
                detect_ptp.parse_args(argv)


if __name__ == "__main__":
    unittest.main()
