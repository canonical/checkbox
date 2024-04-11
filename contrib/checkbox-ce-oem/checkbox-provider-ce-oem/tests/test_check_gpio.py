#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock, call
import requests
import check_gpio


class TestCheckGpio(unittest.TestCase):

    def test_parse_single_ports(self):
        # Test parsing single ports
        self.assertEqual(check_gpio.parse_config("1,2,3"), [1, 2, 3])

    def test_parse_port_ranges(self):
        # Test parsing port ranges
        self.assertEqual(check_gpio.parse_config("5:8,10:12"),
                         [5, 6, 7, 8, 10, 11, 12])

    def test_parse_mixed(self):
        # Test parsing mixed single ports and port ranges
        self.assertEqual(check_gpio.parse_config("1,3:5,7,9:10"),
                         [1, 3, 4, 5, 7, 9, 10])

    def test_parse_empty_string(self):
        # Test parsing an empty string
        expected_result = "Error: Config is empty!"
        with self.assertRaises(ValueError) as err:
            check_gpio.parse_config("")
        self.assertEqual(err.exception.args[0], expected_result)

    def test_parse_invalid_input(self):
        # Test parsing invalid input (non-integer ports)
        expected_result = "Invalid port range: 3:a"
        with self.assertRaises(ValueError) as err:
            check_gpio.parse_config("1,2,3:a")
        self.assertEqual(err.exception.args[0], expected_result)

    def test_list_gpio_slots_exist(self):
        snapd_mock = MagicMock()
        gadget_name = 'test_gadget'
        snapd_mock.interfaces.return_value = {
            "slots": [
                {"snap": gadget_name,
                 "slot": "gpio-0",
                 "interface": "gpio",
                 "attrs": {"number": "10"}},
                {"snap": "other-snap",
                 "slot": "other-slot",
                 "interface": "other-interface",
                 "attrs": {}},
            ]
        }
        expected_result = {"gpio-0": {"number": "10"}}
        self.assertEqual(check_gpio.list_gpio_slots(snapd_mock, gadget_name),
                         expected_result)

    def test_list_gpio_slots_not_exist(self):
        snapd_mock = MagicMock()
        gadget_name = 'test_gadget'
        snapd_mock.interfaces.return_value = {
            "slots": [
                {"snap": "other-snap",
                 "slot": "other-slot",
                 "interface": "other-interface",
                 "attrs": {}},
            ]
        }
        expected_result = "Error: Can not find any GPIO slot"
        with self.assertRaises(SystemExit) as err:
            check_gpio.list_gpio_slots(snapd_mock, gadget_name)
        self.assertEqual(err.exception.args[0], expected_result)

    @patch('builtins.print')  # Mock print function to prevent actual printing
    def test_check_gpio_list_all_defined(self, mock_print):
        gpio_list = {
            1: {"number": 499},
            2: {"number": 500},
            3: {"number": 501},
            4: {"number": 502}
        }
        config = "499,500:502"
        check_gpio.check_gpio_list(gpio_list, config)
        # Assert that "All expected GPIO slots have been defined
        # in gadget snap." is printed
        mock_print.assert_called_with(
            "All expected GPIO slots have been defined in gadget snap.")

    @patch('builtins.print')  # Mock print function to prevent actual printing
    def test_check_gpio_list_missing(self, mock_print):
        gpio_list = {
            1: {"number": 499},
            2: {"number": 500},
            3: {"number": 501},
            # GPIO 502 is missing
        }
        config = "499,500:502"
        with self.assertRaises(SystemExit) as context:
            check_gpio.check_gpio_list(gpio_list, config)

        # Assert that the proper error message is printed for the
        # missing GPIO slot
        mock_print.assert_called_with(
            "Error: Slot of GPIO 502 is not defined in gadget snap")

        # Assert that SystemExit is raised with exit code 1
        self.assertEqual(context.exception.code, 1)

    @patch('check_gpio.os.environ')
    @patch('check_gpio.Snapd')
    def test_connect_gpio_success(self, mock_snapd, mock_environ):
        mock_environ.__getitem__.side_effect = lambda x: {
            'SNAP_NAME': 'checkbox_snap',
            'SNAPD_TASK_TIMEOUT': '30'
        }[x]
        mock_snapd.return_value.connect.side_effect = None

        gpio_slots = {
            "gpio-499": {"number": 499},
            "gpio-500": {"number": 500}
        }
        gadget_name = "gadget_snap"

        check_gpio.connect_gpio(gpio_slots, gadget_name)

        # Assert that connect is called for each GPIO slot
        expected_calls = [call(gadget_name,
                               'gpio-499',
                               'checkbox_snap',
                               'gpio'),
                          call(gadget_name,
                               'gpio-500',
                               'checkbox_snap',
                               'gpio')
                          ]
        mock_snapd.return_value.connect.assert_has_calls(expected_calls)

    @patch('check_gpio.os.environ')
    @patch('check_gpio.Snapd')
    def test_connect_gpio_fail(self, mock_snapd, mock_environ):
        mock_environ.__getitem__.side_effect = lambda x: {
            'SNAP_NAME': 'checkbox_snap',
            'SNAPD_TASK_TIMEOUT': '30'
        }[x]
        mock_snapd.return_value.connect.side_effect = requests.HTTPError

        gpio_slots = {
            "gpio-499": {"number": 499},
            "gpio-500": {"number": 500}
        }
        gadget_name = "gadget_snap"
        with self.assertRaises(SystemExit) as err:
            check_gpio.connect_gpio(gpio_slots, gadget_name)

        # Assert that connect is called for each GPIO slot
        expected_calls = [call(gadget_name,
                               'gpio-499',
                               'checkbox_snap',
                               'gpio'),
                          call(gadget_name,
                               'gpio-500',
                               'checkbox_snap',
                               'gpio')]
        mock_snapd.return_value.connect.assert_has_calls(expected_calls)
        self.assertEqual(err.exception.code, 1)

    @patch('builtins.print')  # Mock print function to prevent actual printing
    def test_check_node_exists(self, mock_print):
        # Mocking os.path.exists to return True
        with patch('os.path.exists', return_value=True):
            check_gpio.check_node(499)
        # Assert that "GPIO node of 499 exist!" is printed
        mock_print.assert_called_with("GPIO node of 499 exist!")

    def test_check_node_not_exist(self):
        # Mocking os.path.exists to return False
        with patch('os.path.exists', return_value=False):
            with self.assertRaises(SystemExit) as context:
                check_gpio.check_node(499)
        # Assert that SystemExit is raised with the correct message
        self.assertEqual(context.exception.args[0],
                         "GPIO node of 499 not exist!")


if __name__ == '__main__':
    unittest.main()
