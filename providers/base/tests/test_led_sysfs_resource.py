import sys
import unittest

from unittest.mock import patch, call

import led_sysfs_resource


class TestSupportedColorType(unittest.TestCase):

    def test_color_definition(self):

        self.assertEqual(led_sysfs_resource.SupportedColorType, ["single", "multi"])


class TestLEDParser(unittest.TestCase):
    @patch("builtins.print")
    def test_parse_all_valid_values(self, mock_print):
        pattern = "LED1|path1|single LED2|path2|multi"
        led_sysfs_resource.parse_sysfs_led_resource(pattern)
        calls = [
            call("name: LED1"),
            call("path: path1"),
            call("color_type: single"),
            call(),
            call("name: LED2"),
            call("path: path2"),
            call("color_type: multi"),
            call(),
        ]
        mock_print.assert_has_calls(calls)

    @patch("builtins.print")
    def test_parse_with_invalid_led_pattern(self, mock_print):
        pattern = "LED1"
        led_sysfs_resource.parse_sysfs_led_resource(pattern)
        mock_print.assert_not_called()

    def test_validate_led_pattern_passed(self):
        pattern = "LED1|path1|single LED2|path2|multi"
        led_sysfs_resource.check_environment(pattern)

    def test_validate_led_pattern_invalid_format(self):
        pattern = "LED1|path1 LED2|path2"
        with self.assertRaises(SystemExit):
            led_sysfs_resource.check_environment(pattern)

    def test_validate_led_pattern_invalid_color_type(self):
        pattern = "LED1|path1|dual"
        with self.assertRaises(SystemExit):
            led_sysfs_resource.check_environment(pattern)

    @patch("builtins.print")
    def test_parse_invalid_color_type(self, mock_print):
        pattern = "LED1|path1|error"
        led_sysfs_resource.parse_sysfs_led_resource(pattern)
        mock_print.assert_not_called()

    @patch("builtins.print")
    def test_parse_undefined_color_type(self, mock_print):
        pattern = "LED1|path1"
        led_sysfs_resource.parse_sysfs_led_resource(pattern)
        mock_print.assert_not_called()


class TestArgumentParser(unittest.TestCase):

    def test_parser(self):
        pattern = "LED1|path1|single LED2|path2|multi"
        sys.argv = ["led_sysfs_resource.py", pattern]
        args = led_sysfs_resource.register_arguments()

        self.assertEqual(args.resource, pattern)
        self.assertFalse(False)

    def test_parser_with_validate_arg(self):
        sys.argv = ["led_sysfs_resource.py", "data", "--validate"]
        args = led_sysfs_resource.register_arguments()

        self.assertEqual(args.resource, "data")
        self.assertTrue(True)
