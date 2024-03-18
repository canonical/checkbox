import textwrap
import unittest
from unittest.mock import patch, mock_open, MagicMock
from gpio_loopback_test import GPIOSysFsController, main


class TestGpioLoopback(unittest.TestCase):

    def setUp(self):
        self.gpio_controller = GPIOSysFsController()

    def test_get_gpio_base_number(self):
        data = textwrap.dedent(
            """
            gpiochip0: GPIOs 0-31, ID1, ID2:
                gpio-0 (                    |sysfs               ) in  hi
                gpio-1 (                    |sysfs               ) out hi
            gpiochip1: GPIOs 32-63, ID3, ID4:
                gpio-32 (                   |sysfs               ) in  hi
                gpio-33 (                   |sysfs               ) out hi
        """
        )
        with patch("builtins.open", mock_open(read_data=data)):
            self.assertEqual(
                self.gpio_controller.get_gpio_base_number(),
                {
                    "gpiochip0": "0",
                    "gpiochip1": "32",
                },
            )

    @patch("gpio_loopback_test.GPIOSysFsController.get_gpio_base_number")
    @patch("gpio_loopback_test.GPIOSysFsController.loopback_test")
    @patch("builtins.print")
    def test_run_test(self, mock_print, mock_loopback, mock_get_base_number):
        mock_get_base_number.return_value = {
            "gpiochip0": "0",
            "gpiochip1": "32",
        }
        mock_loopback.return_value = True

        output_gpio_chip_number = "0"
        input_gpio_chip_number = "1"
        physical_output_port = "J1"
        physical_input_port = "J2"
        gpio_output_pin = "1"
        gpio_input_pin = "2"

        self.gpio_controller.run_test(
            output_gpio_chip_number,
            input_gpio_chip_number,
            physical_output_port,
            physical_input_port,
            gpio_output_pin,
            gpio_input_pin,
        )

        print_calls = [
            "\nOutput Base Number: 0",
            "Input Base Number: 32",
            "Physical output port: J1, GPIO number: 1",
            "Physical input port: J2, GPIO number 2",
            "Output Pin Number: 1 + Base Number = 1",
            "Input Pin Number: 2 + Base Number = 34",
            "\n# Start GPIO loopback test",
        ]

        actual_calls = [call.args[0] for call in mock_print.call_args_list]

        self.assertEqual(actual_calls, print_calls)

        # SystemExit is raised if the loopback test fails
        mock_loopback.return_value = False
        with self.assertRaises(SystemExit):
            self.gpio_controller.run_test(
                output_gpio_chip_number,
                input_gpio_chip_number,
                physical_output_port,
                physical_input_port,
                gpio_output_pin,
                gpio_input_pin,
            )

    @patch("os.path.exists")
    def test_check_gpio_node(self, mock_exists):
        mock_exists.return_value = True
        self.assertTrue(self.gpio_controller.check_gpio_node("test"))

    def test_set_gpio(self):
        with patch("builtins.open", mock_open()) as mock_file:
            self.gpio_controller.set_gpio("test", "1")
            mock_file.assert_called_once_with(
                "/sys/class/gpio/gpio{}/value".format("test"), "wt"
            )
            mock_file().write.assert_called_once_with("1\n")

    def test_read_gpio(self):
        with patch("builtins.open", mock_open(read_data="1")) as mock_file:
            self.assertEqual(self.gpio_controller.read_gpio("test"), "1")
            mock_file.assert_called_once_with(
                "/sys/class/gpio/gpio{}/value".format("test"), "r"
            )

    def test_set_direction(self):
        with patch("builtins.open", mock_open()) as mock_file:
            self.gpio_controller.set_direction("test", "out")
            mock_file.assert_called_once_with(
                "/sys/class/gpio/gpio{}/direction".format("test"), "w"
            )
            mock_file().write.assert_called_once_with("out\n")

    @patch("gpio_loopback_test.GPIOSysFsController.check_gpio_node")
    @patch("gpio_loopback_test.GPIOSysFsController.set_direction")
    @patch("builtins.open")
    def test_configure_gpio(
        self, mock_open, mock_set_direction, mock_check_gpio_node
    ):
        mock_check_gpio_node.return_value = True
        self.gpio_controller.configure_gpio("port", "dir")
        mock_open.assert_not_called()
        mock_set_direction.assert_called_once_with("port", "dir")

        # If the GPIO node does not exist, it should be created
        mock_check_gpio_node.side_effect = [False, True]
        self.gpio_controller.configure_gpio("port", "dir")
        mock_open.assert_called_once_with("/sys/class/gpio/export", "w")
        with mock_open() as mock_file:
            mock_file.write.assert_called_once_with("port\n")
        mock_set_direction.assert_called_with("port", "dir")

    @patch("gpio_loopback_test.GPIOSysFsController.check_gpio_node")
    @patch("gpio_loopback_test.GPIOSysFsController.set_direction")
    @patch("builtins.open")
    def test_configure_fail(
        self, mock_open, mock_set_direction, mock_check_gpio_node
    ):
        # The test should fail if the GPIO can't be exported
        mock_check_gpio_node.side_effect = [False, False]
        with self.assertRaises(SystemExit):
            self.gpio_controller.configure_gpio("port", "dir")
        mock_set_direction.assert_not_called()

        # The test should fail if the direction can't be set
        mock_check_gpio_node.side_effect = [True, True]
        mock_set_direction.side_effect = IOError
        with self.assertRaises(IOError):
            self.gpio_controller.configure_gpio("port", "dir")

    @patch("gpio_loopback_test.GPIOSysFsController.configure_gpio")
    @patch("gpio_loopback_test.GPIOSysFsController.read_gpio")
    @patch("gpio_loopback_test.GPIOSysFsController.set_gpio")
    @patch("time.sleep", MagicMock())
    def test_loopback_test(
        self, mock_set_gpio, mock_read_gpio, mock_configure_gpio
    ):
        mock_read_gpio.side_effect = ["1", "0", "0", "1"]
        self.assertTrue(self.gpio_controller.loopback_test("1", "34"))
        # configure_gpio should be called twice, once for each port
        self.assertEqual(mock_configure_gpio.call_count, 2)
        # set_gpio should be called twice, once for each state
        self.assertEqual(mock_set_gpio.call_count, 2)

    @patch("gpio_loopback_test.GPIOSysFsController.configure_gpio")
    @patch("gpio_loopback_test.GPIOSysFsController.read_gpio")
    @patch("gpio_loopback_test.GPIOSysFsController.set_gpio")
    @patch("time.sleep", MagicMock())
    def test_loopback_test_fail(
        self, mock_set_gpio, mock_read_gpio, mock_configure_gpio
    ):
        mock_read_gpio.side_effect = ["1", "0", "0", "0"]
        self.assertFalse(self.gpio_controller.loopback_test("1", "34"))
        # configure_gpio should be called twice, once for each port
        self.assertEqual(mock_configure_gpio.call_count, 2)
        # set_gpio should be called twice, once for each state
        self.assertEqual(mock_set_gpio.call_count, 2)

    @patch("gpio_loopback_test.GPIOSysFsController.run_test")
    def test_main(self, mock_run_test):
        mock_run_test.return_value = None
        args = (
            ["script_name"]
            + ["-oc", "0"]
            + ["-ic", "1"]
            + ["-po", "J1"]
            + ["-pi", "J2"]
            + ["-go", "1"]
            + ["-gi", "2"]
        )
        with patch("sys.argv", args):
            self.assertEqual(main(), None)
            mock_run_test.assert_called_once_with(
                "0", "1", "J1", "J2", "1", "2"
            )

        # Test fails if run_test raises a SystemExit
        mock_run_test.side_effect = SystemExit
        with patch("sys.argv", args):
            with self.assertRaises(SystemExit):
                main()
