import unittest
from unittest.mock import patch
from pathlib import PosixPath, Path
from gpio_control_test import GPIOController


class TestGPIOController(unittest.TestCase):

    @patch("pathlib.Path.exists")
    def test_file_not_exists(self, mock_path):
        mock_path.return_value = False
        gpio_controller = GPIOController("32", "1", "in", True)
        with self.assertRaises(FileNotFoundError):
            gpio_controller._node_exists(Path("test-fake"))

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_read_file(self, mock_path, mock_read):
        mock_path.return_value = True
        mock_read.return_value = "test-string"
        with GPIOController("32", "1", "in", True) as gpio_controller:
            self.assertEqual(
                mock_read.return_value,
                gpio_controller._read_node(Path("test-fake")))

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_write_failed(self, mock_path, mock_read, mock_write):
        mock_path.return_value = True
        mock_read.return_value = "33"

        with self.assertRaises(ValueError):
            gpio_controller = GPIOController("32", "1", "out", True)
            gpio_controller._write_node(Path("test-fake"), "22", True)

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_write_passed(self, mock_path, mock_read, mock_write):
        mock_path.return_value = True
        mock_read.return_value = "33"

        with self.assertRaises(ValueError):
            gpio_controller = GPIOController("32", "1", "out", True)
            gpio_controller._write_node(Path("test-fake"), "22", True)

    def test_initial_gpio_controller_property(self):

        with GPIOController("32", "3", "out", False) as led_controller:
            self.assertEqual(led_controller.gpio_pin, "3")
            self.assertIsInstance(led_controller.gpio_chip_node, PosixPath)
            self.assertEqual(led_controller.gpio_chip_node.name, "gpiochip32")
            self.assertDictEqual(
                led_controller.gpiochip_info, {"base": None, "ngpio": None})
            self.assertDictEqual(
                led_controller.initial_state,
                {"value": None, "direction": None})

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_get_gpio_direction(self, mock_path, mock_path_get):
        mock_path.return_value = True
        mock_path_get.return_value = "out"

        with GPIOController("32", "1", "out", True) as gpio_controller:
            gpio_controller.gpio_node = Path("fake-node")
            self.assertEqual(gpio_controller.direction, "out")

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_get_gpio_value(self, mock_path, mock_path_get):
        mock_path.return_value = True
        mock_path_get.return_value = "1"

        with GPIOController("32", "1", "out", True) as gpio_controller:
            gpio_controller.gpio_node = Path("fake-node")
            self.assertEqual(gpio_controller.value, "1")
