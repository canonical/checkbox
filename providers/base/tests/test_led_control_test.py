import unittest
from unittest.mock import patch
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
    @patch("led_control_test.SysFsLEDController._read_node")
    @patch("pathlib.Path.exists")
    def test_write_passed(self, mock_path, mock_read, mock_write):
        mock_path.return_value = True
        mock_read.return_value = "22"

        self.led_controller._write_node(Path("test-fake"), "22", True)
        mock_read.assert_called_once()
        mock_write.assert_called_once()

    @patch("led_control_test.SysFsLEDController._write_node")
    @patch("led_control_test.SysFsLEDController.off")
    @patch("led_control_test.SysFsLEDController._get_initial_state")
    @patch("led_control_test.SysFsLEDController._read_node")
    def test_initial_sysfs_controller_property(
            self, mock_read, mock_get_initial, mock_off, mock_write):
        mock_read.return_value = 255

        led_name = "status"
        with SysFsLEDController(led_name, "3", "0") as led_controller:
            mock_read.assert_called_once()
            mock_get_initial.assert_called_once()
            mock_off.assert_called_once()
            mock_write.assert_called_once()
            self.assertEqual(led_controller.led_name, led_name)
            self.assertIsInstance(led_controller.led_node, PosixPath)
            self.assertIsInstance(led_controller.brightness_node, PosixPath)
            self.assertIsInstance(led_controller.trigger_node, PosixPath)
            self.assertEqual(led_controller.led_node.name, led_name)
            self.assertEqual(led_controller.brightness_node.name, "brightness")
            self.assertEqual(led_controller.trigger_node.name, "trigger")
            self.assertDictEqual(
                led_controller.initial_state,
                {"trigger": None, "brightness": None})

    @patch("led_control_test.SysFsLEDController._read_node")
    def test_get_brightness(self, mock_read):
        mock_read.return_value = "33"
        self.assertEqual(self.led_controller.brightness, "33")
        mock_read.assert_called_once()

    @patch("led_control_test.SysFsLEDController._write_node")
    def test_set_brightness(self, mock_write):
        self.led_controller.brightness = "33"
        mock_write.assert_called_once()

    @patch("led_control_test.SysFsLEDController._read_node")
    def test_get_trigger(self, mock_read):
        expected_data = "[none] usb-gadget rfkill-any kbd-scrolllock"
        mock_read.return_value = expected_data

        self.assertEqual(self.led_controller.trigger, expected_data)

    @patch("led_control_test.SysFsLEDController._read_node")
    def test_get_initial_state(self, mock_read):
        mock_read.side_effect = [
            "none usb-gadget [usb-host] rfkill-any rfkill-none kbd-scrolllock",
            "255"
        ]
        expected_data = {"trigger": "usb-host", "brightness": "255"}
        self.led_controller._get_initial_state()
        self.assertEqual(expected_data, self.led_controller.initial_state)
