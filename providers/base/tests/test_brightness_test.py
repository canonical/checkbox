import unittest
from unittest.mock import MagicMock, patch

from brightness_test import Brightness, main


class TestGetScale(unittest.TestCase):
    def test_reads_scale_file_content(self):
        b = Brightness.__new__(Brightness)
        with patch("brightness_test.Path.read_text", return_value="linear\n"):
            result = b.get_scale("/sys/class/backlight/intel_backlight")
        self.assertEqual(result, "linear\n")

    def test_reads_non_linear_scale(self):
        b = Brightness.__new__(Brightness)
        with patch("brightness_test.Path.read_text", return_value="non-linear\n"):
            result = b.get_scale("/sys/class/backlight/amdgpu_bl0")
        self.assertEqual(result, "non-linear\n")


class TestMainScaleBranch(unittest.TestCase):
    INTERFACE = "/sys/class/backlight/amdgpu_bl0"

    def _make_mock_brightness(self, scale_value, was_applied_return_value=0):
        mock_b = MagicMock()
        mock_b.interfaces = [self.INTERFACE]
        mock_b.get_actual_brightness.return_value = 100
        mock_b.get_max_brightness.return_value = 255
        mock_b.get_scale.return_value = scale_value
        mock_b.was_brightness_applied.return_value = was_applied_return_value
        return mock_b

    def _run_main(self, mock_b):
        with (
            patch("brightness_test.Brightness", return_value=mock_b),
            patch("brightness_test.os.geteuid", return_value=0),
            patch("brightness_test.time.sleep"),
        ):
            with self.assertRaises(SystemExit) as ctx:
                main()
        return ctx.exception.code

    def test_linear_scale_calls_check_and_exits_zero_on_success(self):
        mock_b = self._make_mock_brightness("linear", was_applied_return_value=0)
        rv = self._run_main(mock_b)
        mock_b.was_brightness_applied.assert_called_once_with(self.INTERFACE)
        self.assertEqual(rv, 0)

    def test_linear_scale_calls_check_and_exits_one_on_failure(self):
        mock_b = self._make_mock_brightness("linear", was_applied_return_value=1)
        rv = self._run_main(mock_b)
        mock_b.was_brightness_applied.assert_called_once_with(self.INTERFACE)
        self.assertEqual(rv, 1)

    def test_unknown_scale_calls_check_and_exits_zero(self):
        # intel case
        mock_b = self._make_mock_brightness("unknown", was_applied_return_value=0)
        rv = self._run_main(mock_b)
        mock_b.was_brightness_applied.assert_called_once_with(self.INTERFACE)
        self.assertEqual(rv, 0)

    def test_non_linear_scale_skips_check_and_exits_zero(self):
        # amd case
        mock_b = self._make_mock_brightness("non-linear", was_applied_return_value=1)
        rv = self._run_main(mock_b)
        mock_b.was_brightness_applied.assert_not_called()
        self.assertEqual(rv, 0)


if __name__ == "__main__":
    # verbosity=2 shows the test names when running locally
    unittest.main(verbosity=2)
