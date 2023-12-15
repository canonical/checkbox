import unittest
from unittest.mock import patch, Mock
from pathlib import PosixPath, Path
from led_control_test import SysFsLEDController


class TestSysFsLEDController(unittest.TestCase):

    def setUp(self):

        self.led_controller = SysFsLEDController("test-fake")

    @patch("pathlib.Path.exists")
    def test_file_not_exists(self, mock_path):
        mock_path.return_value = False
        with self.assertRaises(FileNotFoundError):
            self.led_controller._node_exists(Path("test-fake"))

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_read_file(self, mock_path, mock_read):
        mock_path.return_value = True
        mock_read.return_value = "test-string"
        self.assertEqual(
            mock_read.return_value,
            self.led_controller._read_node(Path("test-fake")))

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_write_failed(self, mock_path, mock_read, mock_write):
        mock_path.return_value = True
        mock_read.return_value = "33"

        with self.assertRaises(ValueError):
            self.led_controller._write_node(Path("test-fake"), "22", True)

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_write_passed(self, mock_path, mock_read, mock_write):
        mock_path.return_value = True
        mock_read.return_value = "33"

        with self.assertRaises(ValueError):
            self.led_controller._write_node(Path("test-fake"), "22", True)

    def test_initial_sysfs_controller_property(self):

        led_name = "status"
        led_controller = SysFsLEDController(led_name, "3", "0")
        self.assertEqual(led_controller.led_name, led_name)
        self.assertIsInstance(led_controller.led_node, PosixPath)
        self.assertIsInstance(led_controller.brightness_node, PosixPath)
        self.assertIsInstance(led_controller.trigger_node, PosixPath)
        self.assertEqual(led_controller.led_node.name, led_name)
        self.assertEqual(led_controller.brightness_node.name, "brightness")
        self.assertEqual(led_controller.trigger_node.name, "trigger")
        self.assertDictEqual(led_controller.initial_state,
                             {"trigger": None, "brightness": None})

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_get_brightness(
            self, mock_path, mock_path_get):
        mock_path.return_value = True
        mock_path_get.return_value = "33"

        self.assertEqual(self.led_controller.brightness, "33")

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_get_trigger(self, mock_path, mock_path_get):
        expected_data = "[none] usb-gadget rfkill-any kbd-scrolllock"
        mock_path.return_value = True
        mock_path_get.return_value = expected_data

        self.assertEqual(self.led_controller.trigger, expected_data)

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_get_initial_state(self, mock_path, mock_path_get):

        mock_path.return_value = True
        mock_path_get.side_effect = [
            "none usb-gadget [usb-host] rfkill-any rfkill-none kbd-scrolllock",
            "255"
        ]
        expected_data = {"trigger": "usb-host", "brightness": "255"}
        self.led_controller._get_initial_state()
        self.assertEqual(expected_data, self.led_controller.initial_state)
