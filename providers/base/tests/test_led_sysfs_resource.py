import sys
import unittest

from unittest.mock import patch, call, Mock

import led_sysfs_resource


class TestSupportedColorEnum(unittest.TestCase):

    def test_single_color(self):

        self.assertEqual(
            led_sysfs_resource.SupportedColorTypeEnum.SINGLE,
            led_sysfs_resource.SupportedColorTypeEnum("single"),
        )


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
    def test_parse_invalid_color_type(self, mock_print):
        pattern = "LED1|path1|error"
        led_sysfs_resource.parse_sysfs_led_resource(pattern)
        calls = [
            call("name: LED1"),
            call("path: path1"),
            call("color_type: error"),
            call(),
        ]
        mock_print.assert_has_calls(calls)

    @patch("builtins.print")
    def test_parse_undefined_color_type(self, mock_print):
        pattern = "LED1|path1"
        led_sysfs_resource.parse_sysfs_led_resource(pattern)
        calls = [
            call("name: LED1"),
            call("path: path1"),
            call("color_type: {}".format(led_sysfs_resource.UNDEFINED)),
            call(),
        ]
        mock_print.assert_has_calls(calls)

    @patch("builtins.print")
    def test_parse_led_name_only(self, mock_print):
        pattern = "LED1"
        led_sysfs_resource.parse_sysfs_led_resource(pattern)
        calls = [
            call("name: LED1"),
            call("path: {}".format(led_sysfs_resource.UNDEFINED)),
            call("color_type: {}".format(led_sysfs_resource.UNDEFINED)),
            call(),
        ]
        mock_print.assert_has_calls(calls)


class TestArgumentParser(unittest.TestCase):

    def test_parser(self):
        pattern = "LED1|path1|single LED2|path2|multi"
        sys.argv = ["led_sysfs_resource.py", pattern]
        args = led_sysfs_resource.register_arguments()

        self.assertEqual(args.resource, pattern)
