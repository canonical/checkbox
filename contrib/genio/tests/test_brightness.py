import unittest
import os
from unittest.mock import patch, mock_open, MagicMock
from brightness_test import Brightness, main


class TestBrightness(unittest.TestCase):

    @patch("brightness_test.Brightness._get_interfaces_from_path")
    def setUp(self, mock_get_interfaces):
        mock_get_interfaces.return_value = [
            "/sys/class/backlight/interface1",
            "/sys/class/backlight/interface2",
        ]
        self.bt = Brightness()

    @patch("brightness_test.Brightness._get_interfaces_from_path")
    def test_init(self, mock_get_interfaces):
        mock_get_interfaces.return_value = [
            "/sys/class/backlight/interface1",
            "/sys/class/backlight/interface2",
        ]
        self.bt = Brightness("test_path")
        self.assertEqual(self.bt.sysfs_path, "test_path")
        self.assertEqual(
            self.bt.interfaces,
            [
                "/sys/class/backlight/interface1",
                "/sys/class/backlight/interface2",
            ],
        )

    def test_read_value(self):
        data = "100\n"
        with patch("builtins.open", mock_open(read_data=data)):
            self.assertEqual(self.bt.read_value("test_path"), 100)

        # The test raises a value error if the data is None
        file = None
        with self.assertRaises(ValueError):
            self.bt.read_value(file)

        # The test can handle a file object
        mock_file = MagicMock()
        mock_file.write = ""
        mock_file.readlines.return_value = ["100\n"]
        self.assertEqual(self.bt.read_value(mock_file), 100)

    @patch("builtins.open")
    def test_write_value(self, mock_open):
        mock_file = MagicMock()
        mock_open.return_value = mock_file

        self.bt.write_value(100, "test_path")
        mock_open.assert_called_once_with("test_path", "w")
        mock_file.write.assert_called_once_with("100")

        # The file is opened in append mode if the test argument is True
        self.bt.write_value(100, "test_path", True)
        mock_open.assert_called_with("test_path", "a")

        # The test can handle a file object
        self.bt.write_value(100, mock_file)
        mock_file.write.assert_called_with("100")

    @patch("brightness_test.Brightness.read_value")
    def test_get_max_brightness(self, mock_read_value):
        mock_read_value.return_value = 100
        self.assertEqual(self.bt.get_max_brightness("test_path"), 100)

    @patch("brightness_test.Brightness.read_value")
    def test_get_actual_brightness(self, mock_read_value):
        mock_read_value.return_value = 100
        self.assertEqual(self.bt.get_actual_brightness("test_path"), 100)

    @patch("brightness_test.Brightness.read_value")
    def test_get_last_set_brightness(self, mock_read_value):
        mock_read_value.return_value = 100
        self.assertEqual(self.bt.get_last_set_brightness("test_path"), 100)

    @patch("os.path.isdir")
    @patch("brightness_test.glob")
    def test_get_interfaces_from_path(self, mock_glob, mock_isdir):
        mock_isdir.return_value = True
        mock_glob.return_value = ["/sys/class/backlight/interface1"]
        self.assertEqual(
            self.bt._get_interfaces_from_path(),
            ["/sys/class/backlight/interface1"],
        )

        # Returns an empty list if the path is not a directory
        mock_isdir.return_value = False
        self.assertEqual(self.bt._get_interfaces_from_path(), [])

        # Returns an empty list if there are no directories in the path
        mock_isdir.side_effect = [True, False]
        self.assertEqual(self.bt._get_interfaces_from_path(), [])

    @patch("brightness_test.Brightness.get_actual_brightness")
    @patch("brightness_test.Brightness.get_last_set_brightness")
    def test_was_brightness_applied(self, mock_get_last_set, mock_get_actual):
        mock_get_actual.return_value = 100
        mock_get_last_set.return_value = 100
        self.assertEqual(self.bt.was_brightness_applied("test_path"), 0)

        mock_get_actual.return_value = 100
        mock_get_last_set.return_value = 105
        self.assertEqual(self.bt.was_brightness_applied("test_path"), 1)

    @patch("brightness_test.Brightness.get_actual_brightness")
    @patch("brightness_test.Brightness.get_max_brightness")
    @patch("brightness_test.Brightness.write_value")
    @patch("brightness_test.Brightness.was_brightness_applied")
    @patch("time.sleep", MagicMock())
    def test_brightness(
        self,
        mock_was_brightness_applied,
        mock_write_value,
        mock_get_max_brightness,
        mock_get_actual_brightness,
    ):

        target_interface = "/sys/class/backlight/interface1"

        mock_get_actual_brightness.return_value = 100
        mock_get_max_brightness.return_value = 200
        mock_was_brightness_applied.return_value = 0
        self.bt.brightness_test(target_interface)

        mock_get_actual_brightness.assert_called_once_with(target_interface)
        mock_get_max_brightness.assert_called_once_with(target_interface)
        mock_write_value.assert_called_with(
            100, os.path.join(target_interface, "brightness")
        )
        self.assertEqual(mock_was_brightness_applied.call_count, 5)

        # Test the case where the brightness was not applied
        mock_was_brightness_applied.return_value = 1
        with self.assertRaises(SystemExit):
            self.bt.brightness_test(target_interface)

    def test_brightness_no_interfaces(self):
        self.bt.interfaces = []
        target_interface = "/sys/class/backlight/interface1"
        with self.assertRaises(SystemExit) as cm:
            self.bt.brightness_test(target_interface)
        self.assertIn("ERROR", str(cm.exception))

    def test_brightness_no_target_interface(self):
        self.bt.interfaces = [
            "/sys/class/backlight/interface1",
            "/sys/class/backlight/interface2",
        ]
        target_interface = "/sys/class/backlight/interface3"
        with self.assertRaises(SystemExit) as cm:
            self.bt.brightness_test(target_interface)
        self.assertIn("ERROR", str(cm.exception))

    @patch("os.geteuid")
    @patch("brightness_test.Brightness.brightness_test")
    def test_main(self, mock_brightness, mock_getuid):
        mock_getuid.return_value = 0
        argv = ["script_name", "-p", "G1200-evk", "-d", "dsi"]
        with patch("sys.argv", argv):
            main()
        self.assertEqual(mock_brightness.call_count, 1)

    @patch("os.geteuid")
    @patch("brightness_test.Brightness.brightness_test", MagicMock())
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
    @patch("brightness_test.Brightness.brightness_test", MagicMock())
    def test_main_no_root(self, mock_getuid):
        mock_getuid.return_value = 1
        argv = ["script_name", "-p", "G1200-evk", "-d", "dsi"]
        with patch("sys.argv", argv):
            with self.assertRaises(SystemExit):
                main()

    @patch("os.geteuid")
    @patch("brightness_test.Brightness.brightness_test", MagicMock())
    def test_main_wrong_interfaces(self, mock_getuid):
        mock_getuid.return_value = 0
        argv = ["script_name", "-p", "G350", "-d", "lvds"]
        with patch("sys.argv", argv):
            with self.assertRaises(SystemExit):
                main()