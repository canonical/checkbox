import unittest
from unittest.mock import patch
from pathlib import PosixPath, Path
from gpio_control_test import GPIOController


class TestGPIOController(unittest.TestCase):

    @patch("gpio_control_test.GPIOController._unexport")
    @patch("gpio_control_test.GPIOController._export")
    @patch("gpio_control_test.GPIOController._write_node")
    @patch("gpio_control_test.GPIOController._read_node")
    @patch("gpio_control_test.GPIOController._node_exists")
    def test_initial_gpio_controller_success(
            self, mock_path, mock_read, mock_write,
            mock_export, mock_unexport):
        mock_path.return_value = True
        mock_read.side_effect = ["32", "16", "0", "in"]

        with GPIOController("32", "1", "in", True) as gpio_controller:
            mock_path.assert_called()
            mock_read.assert_called()
            mock_write.assert_called()
            self.assertIsInstance(gpio_controller.gpio_chip_node, PosixPath)
            self.assertEqual(gpio_controller.gpio_chip_node.name, "gpiochip32")
            self.assertDictEqual(
                gpio_controller.gpiochip_info,
                {"base": "32", "ngpio": "16", "offset": "1"})
            self.assertDictEqual(
                gpio_controller.initial_state,
                {"value": "0", "direction": "in", "number": "32"})

    def test_initial_gpio_controller_with_invalid_gpiochip(self):
        with self.assertRaises(ValueError):
            with GPIOController("6a", "1", "in", True) as gpio_controller:
                gpio_controller.gpio_chip_node

    def test_initial_gpio_controller_with_invalid_gpiopin(self):
        with self.assertRaises(ValueError):
            with GPIOController("12", "1a", "in", True) as _:
                pass

    @patch("gpio_control_test.GPIOController._unexport")
    @patch("gpio_control_test.GPIOController._export")
    @patch("gpio_control_test.GPIOController._write_node")
    @patch("gpio_control_test.GPIOController._read_node")
    @patch("gpio_control_test.GPIOController._node_exists")
    def test_initial_gpiopin_exceeds_maximum(
            self, mock_path, mock_read, mock_write,
            mock_export, mock_unexport):
        mock_path.return_value = True
        mock_read.side_effect = ["32", "16", "0", "in"]

        with self.assertRaises(IndexError):
            with GPIOController("32", "18", "in", True) as _:
                mock_path.assert_called()
                mock_read.assert_called()

    @patch("pathlib.Path.exists")
    def test_file_not_exists(self, mock_path):
        mock_path.return_value = False
        gpio_controller = GPIOController("32", "1", "in", True)
        with self.assertRaises(FileNotFoundError):
            gpio_controller._node_exists(Path("test-fake"))

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_read_file(self, mock_path, mock_read):
        expected_result = "test-string"
        mock_path.return_value = True
        mock_read.return_value = expected_result
        gpio_controller = GPIOController("32", "1", "in", True)
        self.assertEqual(
            expected_result,
            gpio_controller._read_node(gpio_controller.gpio_chip_node))

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_write_failed(self, mock_path, mock_read, mock_write):
        read_value = "33"
        write_value = "22"

        mock_path.return_value = True
        mock_read.return_value = read_value

        with self.assertRaises(ValueError):
            gpio_controller = GPIOController("32", "1", "out", True)
            gpio_controller._write_node(Path("test-fake"), write_value, True)

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_write_passed(self, mock_path, mock_read, mock_write):
        read_value = "33"
        write_value = "33"

        mock_path.return_value = True
        mock_read.return_value = read_value

        gpio_controller = GPIOController("32", "1", "out", True)
        gpio_controller._write_node(Path("test-fake"), write_value, True)

        mock_path.assert_called()
        mock_read.assert_called_once()
        mock_write.assert_called_once()

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_get_gpio_direction(self, mock_path, mock_path_get):
        mock_path.return_value = True
        mock_path_get.return_value = "out"

        gpio_controller = GPIOController("32", "1", "out", True)
        gpio_controller.gpio_node = Path("fake-node")
        self.assertEqual(gpio_controller.direction, "out")

    def test_set_gpio_direction_failed(self):
        with self.assertRaises(ValueError):
            gpio_controller = GPIOController("32", "1", "out", True)
            gpio_controller.direction = "wrong_direction"

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_get_gpio_value(self, mock_path, mock_path_get):
        mock_path.return_value = True
        mock_path_get.return_value = "1"

        gpio_controller = GPIOController("32", "1", "out", True)
        gpio_controller.gpio_node = Path("fake-node")
        self.assertEqual(gpio_controller.value, "1")

    def test_set_gpio_value_failed(self):
        with self.assertRaises(ValueError):
            gpio_controller = GPIOController("32", "1", "out", True)
            gpio_controller.value = "wrong_value"
