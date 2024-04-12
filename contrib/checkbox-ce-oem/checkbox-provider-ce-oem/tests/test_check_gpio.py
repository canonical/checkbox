#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock, call
import requests
import check_gpio
import os


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
        expected_result = {}
        self.assertEqual(check_gpio.list_gpio_slots(snapd_mock, gadget_name),
                         expected_result)

    @patch('builtins.print')
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

    @patch('builtins.print')
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

    @patch('builtins.print')
    @patch('check_gpio.Snapd')
    def test_connect_interface_success(self, mock_snapd, mock_print):
        mock_snapd.return_value.connect.side_effect = None
        gpio_slot = "gpio-499"
        gadget_name = "gadget_snap"
        snap = "checkbox_snap"
        timeout = 30
        check_gpio.connect_interface(gadget_name,
                                     gpio_slot,
                                     snap,
                                     timeout)

        expected_calls = [call(gadget_name,
                               gpio_slot,
                               snap,
                               'gpio')]
        mock_snapd.return_value.connect.assert_has_calls(expected_calls)
        mock_print.assert_called_with("Success")

    @patch('builtins.print')
    @patch('check_gpio.Snapd')
    def test_connect_interface_fail(self, mock_snapd, mock_print):
        mock_snapd.return_value.connect.side_effect = requests.HTTPError
        gpio_slot = "gpio-499"
        gadget_name = "gadget_snap"
        snap = "checkbox_snap"
        timeout = 30
        with self.assertRaises(SystemExit) as err:
            check_gpio.connect_interface(gadget_name,
                                         gpio_slot,
                                         snap,
                                         timeout)

        expected_calls = [call(gadget_name,
                               gpio_slot,
                               snap,
                               'gpio')]
        mock_snapd.return_value.connect.assert_has_calls(expected_calls)
        mock_print.assert_called_with("Failed to connect gpio-499")
        self.assertEqual(err.exception.code, 1)

    @patch('builtins.print')
    @patch('check_gpio.Snapd')
    def test_disconnect_interface_success(self, mock_snapd, mock_print):
        mock_snapd.return_value.disconnect.side_effect = None
        gpio_slot = "gpio-499"
        gadget_name = "gadget_snap"
        snap = "checkbox_snap"
        timeout = 30
        check_gpio.disconnect_interface(gadget_name,
                                        gpio_slot,
                                        snap,
                                        timeout)

        expected_calls = [call(gadget_name,
                               gpio_slot,
                               snap,
                               'gpio')]
        mock_snapd.return_value.disconnect.assert_has_calls(expected_calls)
        mock_print.assert_called_with("Success")

    @patch('builtins.print')
    @patch('check_gpio.Snapd')
    def test_disconnect_interface_fail(self, mock_snapd, mock_print):
        mock_snapd.return_value.disconnect.side_effect = requests.HTTPError
        gpio_slot = "gpio-499"
        gadget_name = "gadget_snap"
        snap = "checkbox_snap"
        timeout = 30
        with self.assertRaises(SystemExit) as err:
            check_gpio.disconnect_interface(gadget_name,
                                            gpio_slot,
                                            snap,
                                            timeout)

        expected_calls = [call(gadget_name,
                               gpio_slot,
                               snap,
                               'gpio')]
        mock_snapd.return_value.disconnect.assert_has_calls(expected_calls)
        mock_print.assert_called_with("Failed to disconnect gpio-499")
        self.assertEqual(err.exception.code, 1)

    @patch('builtins.print')
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

    @patch.dict(os.environ, {'SNAP_NAME': 'checkbox_snap'})
    @patch.dict(os.environ, {'SNAPD_TASK_TIMEOUT': '30'})
    @patch('check_gpio.connect_interface')
    @patch('check_gpio.disconnect_interface')
    def test_interface_test(self,
                            mock_disconnect,
                            mock_connect):
        gadget_name = "gadget"
        gpio_slot = "gpio-499"
        mock_connect.side_effect = None
        mock_disconnect.side_effect = None
        with check_gpio.interface_test(gpio_slot, gadget_name):
            mock_connect.assert_called_once_with(gadget_name,
                                                 gpio_slot,
                                                 'checkbox_snap',
                                                 30)
        mock_disconnect.assert_called_once_with(gadget_name,
                                                gpio_slot,
                                                'checkbox_snap',
                                                30)


if __name__ == '__main__':
    unittest.main()
