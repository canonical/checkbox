import unittest
import sys
import argparse
from unittest.mock import patch, Mock
from pathlib import PosixPath, Path
from io import StringIO
from contextlib import redirect_stdout
from gpio_control_test import GPIOController
from gpio_control_test import blinking_test
from gpio_control_test import dump_gpiochip
from gpio_control_test import leds_resource
from gpio_control_test import register_arguments


class TestGPIOController(unittest.TestCase):

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("gpio_control_test.GPIOController._unexport")
    @patch("gpio_control_test.GPIOController._export")
    @patch("gpio_control_test.GPIOController._write_node")
    @patch("gpio_control_test.GPIOController._read_node")
    @patch("gpio_control_test.GPIOController._node_exists")
    @patch("gpio_control_test.time.sleep", new=Mock)
    def test_initial_gpio_controller_success(
        self,
        mock_path,
        mock_read,
        mock_write,
        mock_export,
        mock_unexport,
        mock_mapping,
    ):
        mock_path.return_value = True
        mock_read.side_effect = ["32", "16", "0", "in"]
        mock_mapping.return_value = {"1": "32"}

        with GPIOController("1", "1", "in", True) as gpio_controller:
            mock_path.assert_called_with(gpio_controller.gpio_node)
            mock_read.assert_called_with(
                gpio_controller.gpio_node.joinpath("direction")
            )
            mock_write.assert_called_with(
                gpio_controller.gpio_node.joinpath("direction"), "in"
            )
            self.assertIsInstance(gpio_controller.gpio_chip_node, PosixPath)
            self.assertEqual(gpio_controller.gpio_chip_node.name, "gpiochip32")
            self.assertDictEqual(
                gpio_controller.gpiochip_info,
                {"base": "32", "ngpio": "16", "offset": "1"},
            )
            self.assertDictEqual(
                gpio_controller.initial_state,
                {"value": "0", "direction": "in", "number": "32"},
            )

    def test_initial_gpio_controller_with_invalid_gpiochip(self):
        with self.assertRaises(ValueError):
            with GPIOController("6a", "1", "in", True) as gpio_controller:
                gpio_controller.gpio_chip_node

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    def test_initial_gpio_controller_with_notexist_gpiochip(
        self, mock_mapping
    ):
        mock_mapping.return_value = {"0": "32"}
        with self.assertRaises(KeyError):
            GPIOController("1", "1", "in", True)

    def test_initial_gpio_controller_with_invalid_gpiopin(self):
        with self.assertRaises(ValueError):
            with GPIOController("12", "1a", "in", True) as _:
                pass

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("gpio_control_test.GPIOController._read_node")
    @patch("gpio_control_test.GPIOController._node_exists")
    def test_initial_gpio_controller_with_notexist_gpiopin(
        self, mock_path, mock_read, mock_mapping
    ):
        mock_read.side_effect = ["32", "16", "0", "in"]
        mock_mapping.return_value = {"0": "32"}
        with self.assertRaises(ValueError):
            gpio_conn = GPIOController("0", "0", "in", True)
            gpio_conn.setup()

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("gpio_control_test.GPIOController._unexport")
    @patch("gpio_control_test.GPIOController._export")
    @patch("gpio_control_test.GPIOController._write_node")
    @patch("gpio_control_test.GPIOController._read_node")
    @patch("gpio_control_test.GPIOController._node_exists")
    def test_initial_gpiopin_exceeds_maximum(
        self,
        mock_path,
        mock_read,
        mock_write,
        mock_export,
        mock_unexport,
        mock_mapping,
    ):
        mock_path.return_value = True
        mock_read.side_effect = ["32", "16", "0", "in"]
        mock_mapping.return_value = {"1": "32"}

        with self.assertRaises(IndexError):
            with GPIOController("1", "18", "in", True) as gpio_controller:
                mock_path.assert_called_with(gpio_controller.gpio_node)
                mock_read.assert_called_with(
                    gpio_controller.gpio_node.joinpath("direction")
                )

    @patch("pathlib.Path.glob")
    def test_get_gpiochip_mapping(self, mock_glob):
        expected_data = {"0": "32", "1": "96"}
        mock_glob.return_value = [
            "/sys/class/gpio/gpiochip32/device/gpiochip0",
            "/sys/class/gpio/gpiochip96/device/gpiochip1",
        ]

        gpio_conn = GPIOController("0", "1", "out", True)
        self.assertDictEqual(gpio_conn.get_gpiochip_mapping(), expected_data)

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("gpio_control_test.GPIOController._read_node")
    @patch("gpio_control_test.GPIOController._node_exists")
    def test_setup_failed_by_ngpio_not_available(
        self, mock_path, mock_read, mock_mapping
    ):
        mock_mapping.return_value = {"0": "32"}
        mock_path.side_effect = [True, False]
        mock_read.return_value = "32"

        gpio_conn = GPIOController("0", "1", "out", False)
        with self.assertRaises(FileNotFoundError):
            gpio_conn.setup()

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("gpio_control_test.GPIOController._read_node")
    @patch("gpio_control_test.GPIOController._node_exists")
    def test_setup_failed_gpionode_not_available(
        self, mock_path, mock_read, mock_mapping
    ):
        mock_mapping.return_value = {"0": "32"}
        mock_path.side_effect = [True, True, False]
        mock_read.side_effect = ["32", "16"]

        gpio_conn = GPIOController("0", "1", "out", False)
        with self.assertRaises(FileNotFoundError):
            gpio_conn.setup()

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("pathlib.Path.exists")
    def test_file_not_exists(self, mock_path, mock_mapping):
        mock_path.return_value = False
        mock_mapping.return_value = {"1": "32"}
        gpio_controller = GPIOController("1", "1", "in", True)
        with self.assertRaises(FileNotFoundError):
            gpio_controller._node_exists(Path("test-fake"))

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_read_file(self, mock_path, mock_read, mock_mapping):
        expected_result = "test-string"
        mock_path.return_value = True
        mock_read.return_value = expected_result
        mock_mapping.return_value = {"1": "32"}
        gpio_controller = GPIOController("1", "1", "in", True)
        self.assertEqual(
            expected_result,
            gpio_controller._read_node(gpio_controller.gpio_chip_node),
        )

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_write_failed(
        self, mock_path, mock_read, mock_write, mock_mapping
    ):
        read_value = "33"
        write_value = "22"

        mock_path.return_value = True
        mock_read.return_value = read_value
        mock_mapping.return_value = {"1": "32"}

        with self.assertRaises(ValueError):
            gpio_controller = GPIOController("1", "1", "out", True)
            gpio_controller._write_node(Path("test-fake"), write_value, True)

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_write_passed(
        self, mock_path, mock_read, mock_write, mock_mapping
    ):
        read_value = "33"
        write_value = "33"
        mock_path.return_value = True
        mock_read.return_value = read_value
        mock_mapping.return_value = {"1": "32"}

        gpio_controller = GPIOController("1", "1", "out", True)
        gpio_controller._write_node(Path("test-fake"), write_value, True)

        mock_path.assert_called_with()
        mock_read.assert_called_once_with()
        mock_write.assert_called_once_with("33")

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("gpio_control_test.GPIOController._write_node")
    def test_export_gpio_node(self, mock_write, mock_mapping):
        mock_mapping.return_value = {"1": "32"}

        gpio_no = "30"
        gpio_controller = GPIOController("1", "1", "out", True)
        gpio_controller._export(gpio_no)
        mock_write.assert_called_once_with(
            PosixPath("/sys/class/gpio/export"), gpio_no, False
        )

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("gpio_control_test.GPIOController._write_node")
    def test_unexport_gpio_node(self, mock_write, mock_mapping):
        mock_mapping.return_value = {"1": "32"}

        gpio_no = "30"
        gpio_controller = GPIOController("1", "1", "out", True)
        gpio_controller._unexport(gpio_no)
        mock_write.assert_called_once_with(
            PosixPath("/sys/class/gpio/unexport"), gpio_no, False
        )

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("gpio_control_test.GPIOController._read_node")
    @patch("gpio_control_test.GPIOController._node_exists")
    def test_get_gpio_direction(self, mock_path, mock_path_get, mock_mapping):
        mock_path.return_value = True
        mock_path_get.return_value = "out"
        mock_mapping.return_value = {"1": "32"}

        gpio_controller = GPIOController("1", "1", "out", True)
        gpio_controller.gpio_node = Path("fake-node")
        self.assertEqual(gpio_controller.direction, "out")

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    def test_set_gpio_direction_failed(self, mock_mapping):
        mock_mapping.return_value = {"1": "32"}

        with self.assertRaises(ValueError):
            gpio_controller = GPIOController("1", "1", "out", True)
            gpio_controller.direction = "wrong_direction"

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("gpio_control_test.GPIOController._read_node")
    @patch("gpio_control_test.GPIOController._node_exists")
    def test_get_gpio_value(self, mock_path, mock_path_get, mock_mapping):
        mock_path.return_value = True
        mock_path_get.return_value = "1"
        mock_mapping.return_value = {"1": "32"}

        gpio_controller = GPIOController("1", "1", "out", True)
        gpio_controller.gpio_node = Path("fake-node")
        self.assertEqual(gpio_controller.value, "1")

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    def test_set_gpio_value_failed(self, mock_mapping):
        mock_mapping.return_value = {"1": "32"}

        with self.assertRaises(ValueError):
            gpio_controller = GPIOController("1", "1", "out", True)
            gpio_controller.value = "wrong_value"

    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("gpio_control_test.GPIOController.off")
    @patch("gpio_control_test.GPIOController.on")
    def test_blinking_function(self, mock_on, mock_off, mock_mapping):
        mock_mapping.return_value = {"1": "32"}

        gpio_controller = GPIOController("1", "1", "out", True)
        gpio_controller.blinking(0.0001, 0.0001)
        mock_on.assert_called_with()
        mock_off.assert_called_with()


class TestMainFunction(unittest.TestCase):

    @patch("gpio_control_test.GPIOController._write_node")
    @patch("gpio_control_test.GPIOController._read_node")
    @patch("gpio_control_test.GPIOController._node_exists")
    @patch("gpio_control_test.GPIOController.get_gpiochip_mapping")
    @patch("gpio_control_test.GPIOController.blinking")
    def test_blinking_test(
        self, mock_blinking, mock_mapping, mock_path, mock_read, mock_write
    ):
        mock_args = Mock(
            return_value=argparse.Namespace(
                name="fake-node",
                duration=5,
                interval=0.5,
                gpio_chip="1",
                gpio_pin="1",
                need_export=False,
            )
        )
        mock_mapping.return_value = {"1": "32"}
        mock_path.return_value = True
        mock_read.side_effect = ["32", "16", "1", "out"]

        blinking_test(mock_args())
        mock_blinking.assert_called_once_with(
            mock_args().duration, mock_args().interval
        )

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_dump_gpiochip_test(self, mock_path, mock_read):
        mock_path.return_value = True
        mock_read.return_value = "mock-string"

        with redirect_stdout(StringIO()) as stdout:
            dump_gpiochip(None)
        mock_path.assert_called_once_with()
        mock_read.assert_called_once_with()

    @patch("pathlib.Path.exists")
    def test_dump_gpiochip_test_failed(self, mock_path):
        mock_path.return_value = False

        with self.assertRaises(FileNotFoundError) as context:
            dump_gpiochip(None)

        self.assertEqual(
            str(context.exception), "/sys/kernel/debug/gpio file not exists"
        )

    def test_led_resource(self):
        mock_args = Mock(
            return_value=argparse.Namespace(mapping="DL14:5:1 DL14:5:2")
        )
        with redirect_stdout(StringIO()) as stdout:
            leds_resource(mock_args())

    def test_led_resource_with_unexpected_format(self):
        mock_args = Mock(return_value=argparse.Namespace(mapping="DL14-5:1"))

        with self.assertRaises(ValueError) as context:
            leds_resource(mock_args())

        self.assertEqual(
            str(context.exception),
            "not enough values to unpack (expected 3, got 2)",
        )


class TestArgumentParser(unittest.TestCase):

    def test_led_parser(self):
        sys.argv = [
            "gpio_control_test.py",
            "--debug",
            "led",
            "-n",
            "fake-led",
            "--gpio-chip",
            "3",
            "--gpio-pin",
            "5",
            "--need-export",
            "-d",
            "30",
            "-i",
            "2",
        ]
        args = register_arguments()

        self.assertEqual(args.test_func, blinking_test)
        self.assertEqual(args.debug, True)
        self.assertEqual(args.name, "fake-led")
        self.assertEqual(args.duration, 30)
        self.assertEqual(args.interval, 2)
        self.assertEqual(args.gpio_chip, "3")
        self.assertEqual(args.gpio_pin, "5")

    def test_dump_parser(self):
        sys.argv = ["gpio_control_test.py", "dump"]
        args = register_arguments()

        self.assertEqual(args.test_func, dump_gpiochip)
        self.assertEqual(args.debug, False)

    def test_led_resource_parser(self):
        sys.argv = ["gpio_control_test.py", "led-resource", "DL14:5:1"]
        args = register_arguments()

        self.assertEqual(args.test_func, leds_resource)
        self.assertEqual(args.debug, False)
