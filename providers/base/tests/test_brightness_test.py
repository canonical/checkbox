import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from brightness_test import Brightness

SYSFS_PATH = "/sys/class/backlight"


class TestGetMaxBrightness(unittest.TestCase):
    def test_reads_max_brightness_file(self):
        b = Brightness.__new__(Brightness)
        with patch.object(b, "read_value", return_value=255) as mock_read:
            result = b.get_max_brightness(
                "/sys/class/backlight/intel_backlight"
            )
        mock_read.assert_called_once_with(
            "/sys/class/backlight/intel_backlight/max_brightness"
        )
        self.assertEqual(result, 255)


class TestGetActualBrightness(unittest.TestCase):
    def test_reads_actual_brightness_file(self):
        b = Brightness.__new__(Brightness)
        with patch.object(b, "read_value", return_value=128) as mock_read:
            result = b.get_actual_brightness(
                "/sys/class/backlight/intel_backlight"
            )
        mock_read.assert_called_once_with(
            "/sys/class/backlight/intel_backlight/actual_brightness"
        )
        self.assertEqual(result, 128)


class TestGetLastSetBrightness(unittest.TestCase):
    def test_reads_brightness_file(self):
        b = Brightness.__new__(Brightness)
        with patch.object(b, "read_value", return_value=64) as mock_read:
            result = b.get_last_set_brightness(
                "/sys/class/backlight/intel_backlight"
            )
        mock_read.assert_called_once_with(
            "/sys/class/backlight/intel_backlight/brightness"
        )
        self.assertEqual(result, 64)


class TestGetInterfacesFromPath(unittest.TestCase):
    def test_returns_empty_list_when_path_does_not_exist(self):
        with patch("brightness_test.os.path.isdir", return_value=False):
            b = Brightness(path="/nonexistent")
        self.assertEqual(b.interfaces, [])

    def test_returns_subdirectory_interfaces(self):
        dirs = [
            "/sys/class/backlight/intel_backlight",
            "/sys/class/backlight/acpi_video0",
        ]
        with (
            patch("brightness_test.os.path.isdir", return_value=True),
            patch(
                "brightness_test.glob",
                return_value=dirs,
            ),
        ):
            b = Brightness(path=SYSFS_PATH)
        self.assertEqual(b.interfaces, dirs)

    def test_excludes_non_directory_entries(self):
        entries = [
            "/sys/class/backlight/intel_backlight",
            "/sys/class/backlight/somefile",
        ]

        def _isdir(path):
            return path != "/sys/class/backlight/somefile"

        with (
            patch("brightness_test.os.path.isdir", side_effect=_isdir),
            patch(
                "brightness_test.glob",
                return_value=entries,
            ),
        ):
            b = Brightness(path=SYSFS_PATH)
        self.assertEqual(
            b.interfaces, ["/sys/class/backlight/intel_backlight"]
        )


class TestWasBrightnessApplied(unittest.TestCase):
    INTERFACE = "/sys/class/backlight/intel_backlight"

    def _make_brightness(
        self,
        actual_brightness: int,
        last_set_brightness: int,
    ):
        b = Brightness.__new__(Brightness)
        b.get_actual_brightness = MagicMock(return_value=actual_brightness)
        b.get_last_set_brightness = MagicMock(return_value=last_set_brightness)
        return b

    def test_happy_path(self):
        b = self._make_brightness(100, 100)
        self.assertEqual(b.was_brightness_applied(self.INTERFACE), 0)
        b = self._make_brightness(101, 100)
        self.assertEqual(b.was_brightness_applied(self.INTERFACE), 0)

    def test_difference_greater_than_one(self):
        b = self._make_brightness(103, 100)
        self.assertEqual(b.was_brightness_applied(self.INTERFACE), 1)


class TestGetScale(unittest.TestCase):
    def test_returns_path_to_scale_file(self):
        b = Brightness.__new__(Brightness)
        result = b.get_scale("/sys/class/backlight/intel_backlight")
        expected = Path("/sys/class/backlight/intel_backlight") / "scale"
        self.assertEqual(result, expected)


if __name__ == "__main__":
    # verbosity=2 shows the test names when running locally
    unittest.main(verbosity=2)
