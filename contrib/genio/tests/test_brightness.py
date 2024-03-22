import unittest
import os
from unittest.mock import patch, mock_open, MagicMock
from brightness_test import Brightness, main


class TestBrightness(unittest.TestCase):

    def test_init(self):
        mock_brightness = MagicMock()
        mock_brightness._get_interfaces_from_path.return_value = [
            "/sys/class/backlight/interface1",
            "/sys/class/backlight/interface2",
        ]
        Brightness.__init__(mock_brightness)
        self.assertEqual(
            mock_brightness.interfaces,
            [
                "/sys/class/backlight/interface1",
                "/sys/class/backlight/interface2",
            ],
        )

    def test_read_value(self):
        mock_brightness = MagicMock()
        data = "100\n"
        with patch("builtins.open", mock_open(read_data=data)):
            self.assertEqual(
                Brightness.read_value(mock_brightness, "test_path"), 100
            )

        # The test raises a value error if the data is None
        file = None
        with self.assertRaises(ValueError):
            Brightness.read_value(mock_brightness, file)

        # The test can handle a file object
        mock_file = MagicMock()
        mock_file.write = ""
        mock_file.readlines.return_value = ["100\n"]
        self.assertEqual(
            Brightness.read_value(mock_brightness, mock_file), 100
        )

    @patch("builtins.open")
    def test_write_value(self, mock_open):
        mock_brightness = MagicMock()
        mock_file = MagicMock()
        mock_open.return_value = mock_file

        Brightness.write_value(mock_brightness, 100, "test_path")
        mock_open.assert_called_once_with("test_path", "w")
        mock_file.write.assert_called_once_with("100")

        # The file is opened in append mode if the test argument is True
        Brightness.write_value(mock_brightness, 100, "test_path", True)
        mock_open.assert_called_with("test_path", "a")

        # The test can handle a file object
        Brightness.write_value(mock_brightness, 100, mock_file)
        mock_file.write.assert_called_with("100")

    def test_get_max_brightness(self):
        mock_brightness = MagicMock()
        mock_brightness.read_value.return_value = 100
        self.assertEqual(
            Brightness.get_max_brightness(mock_brightness, "test_path"), 100
        )

    def test_get_actual_brightness(self):
        mock_brightness = MagicMock()
        mock_brightness.read_value.return_value = 100
        self.assertEqual(
            Brightness.get_actual_brightness(mock_brightness, "test_path"), 100
        )

    def test_get_last_set_brightness(self):
        mock_brightness = MagicMock()
        mock_brightness.read_value.return_value = 100
        self.assertEqual(
            Brightness.get_last_set_brightness(mock_brightness, "test_path"),
            100,
        )

    @patch("os.path.isdir")
    @patch("brightness_test.glob")
    def test_get_interfaces_from_path(self, mock_glob, mock_isdir):
        mock_brightness = MagicMock()
        mock_brightness.sysfs_path = "/sys/class/backlight"
        mock_isdir.return_value = True
        mock_glob.return_value = ["/sys/class/backlight/interface1"]
        self.assertEqual(
            Brightness._get_interfaces_from_path(
                mock_brightness,
            ),
            ["/sys/class/backlight/interface1"],
        )

        # Returns an empty list if the path is not a directory
        mock_isdir.return_value = False
        self.assertEqual(
            Brightness._get_interfaces_from_path(
                mock_brightness,
            ),
            [],
        )

        # Returns an empty list if there are no directories in the path
        mock_isdir.side_effect = [True, False]
        self.assertEqual(
            Brightness._get_interfaces_from_path(
                mock_brightness,
            ),
            [],
        )

    def test_was_brightness_applied(self):
        mock_brightness = MagicMock()
        mock_brightness.get_actual_brightness.return_value = 100
        mock_brightness.get_last_set_brightness.return_value = 100
        self.assertEqual(
            Brightness.was_brightness_applied(mock_brightness, "test_path"), 0
        )

        mock_brightness.get_actual_brightness.return_value = 100
        mock_brightness.get_last_set_brightness.return_value = 105
        self.assertEqual(
            Brightness.was_brightness_applied(mock_brightness, "test_path"), 1
        )

    @patch("time.sleep", MagicMock())
    def test_brightness(self):
        mock_brightness = MagicMock()
        mock_brightness.interfaces = [
            "/sys/class/backlight/interface1",
            "/sys/class/backlight/interface2",
        ]
        mock_brightness.get_actual_brightness.return_value = 100
        mock_brightness.get_max_brightness.return_value = 200
        mock_brightness.was_brightness_applied.return_value = 0

        target_interface = "/sys/class/backlight/interface1"
        Brightness.brightness_test(mock_brightness, target_interface)

        mock_brightness.get_actual_brightness.assert_called_once_with(
            target_interface
        )
        mock_brightness.get_max_brightness.assert_called_once_with(
            target_interface
        )
        mock_brightness.write_value.assert_called_with(
            100, os.path.join(target_interface, "brightness")
        )
        self.assertEqual(mock_brightness.was_brightness_applied.call_count, 5)

        # Test the case where the brightness was not applied
        mock_brightness.was_brightness_applied.return_value = 1
        with self.assertRaises(SystemExit):
            Brightness.brightness_test(mock_brightness, target_interface)

    def test_brightness_no_interfaces(self):
        mock_brightness = MagicMock()
        mock_brightness.interfaces = []
        target_interface = "/sys/class/backlight/interface1"
        with self.assertRaises(SystemExit) as cm:
            Brightness.brightness_test(mock_brightness, target_interface)
        self.assertIn("ERROR", str(cm.exception))

    def test_brightness_no_target_interface(self):
        mock_brightness = MagicMock()
        mock_brightness.interfaces = [
            "/sys/class/backlight/interface1",
            "/sys/class/backlight/interface2",
        ]
        target_interface = "/sys/class/backlight/interface3"
        with self.assertRaises(SystemExit) as cm:
            Brightness.brightness_test(mock_brightness, target_interface)
        self.assertIn("ERROR", str(cm.exception))

    @patch("os.geteuid")
    @patch("brightness_test.Brightness")
    def test_main(self, mock_brightness, mock_getuid):
        mock_getuid.return_value = 0
        argv = ["script_name", "-p", "G1200-evk", "-d", "dsi"]
        with patch("sys.argv", argv):
            main()
        self.assertEqual(mock_brightness.call_count, 1)

    @patch("os.geteuid")
    @patch("brightness_test.Brightness", MagicMock())
    def test_main_bad_args(self, mock_getuid):
        mock_getuid.return_value = 0
        argv = ["script_name", "-p", "bad_platform", "-d", "dsi"]
        with patch("sys.argv", argv):
            with self.assertRaises(SystemExit):
                main()

        argv = ["script_name", "-p", "G1200-evk", "-d", "bad_display"]
        with patch("sys.argv", argv):
            with self.assertRaises(SystemExit):
                main()

    @patch("os.geteuid")
    @patch("brightness_test.Brightness", MagicMock())
    def test_main_no_root(self, mock_getuid):
        mock_getuid.return_value = 1
        argv = ["script_name", "-p", "G1200-evk", "-d", "dsi"]
        with patch("sys.argv", argv):
            with self.assertRaises(SystemExit):
                main()

    @patch("os.geteuid")
    @patch("brightness_test.Brightness", MagicMock())
    def test_main_wrong_interfaces(self, mock_getuid):
        mock_getuid.return_value = 0
        argv = ["script_name", "-p", "G350", "-d", "lvds"]
        with patch("sys.argv", argv):
            with self.assertRaises(SystemExit):
                main()
