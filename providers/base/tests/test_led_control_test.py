import sys
import unittest
from datetime import datetime
from unittest.mock import patch, Mock, PropertyMock
from pathlib import PosixPath, Path
from led_control_test import SysFsLEDController
from led_control_test import register_arguments


class TestSysFsLEDController(unittest.TestCase):

    def setUp(self):

        self.led_controller = SysFsLEDController("test-fake")

    @patch("led_control_test.SysFsLEDController._read_node")
    @patch("led_control_test.SysFsLEDController._node_exists")
    def test_setup_failed(self, mock_path, mock_read):
        mock_path.return_value = False
        mock_read.return_value = "30"
        self.led_controller._on_value = "50"

        with self.assertRaises(ValueError):
            self.led_controller.setup()

    @patch("led_control_test.SysFsLEDController._write_node")
    @patch("led_control_test.SysFsLEDController._read_node")
    @patch("led_control_test.SysFsLEDController._node_exists")
    def test_setup_passed(self, mock_path, mock_read, mock_write):
        mock_path.return_value = True
        mock_read.return_value = "30"

        self.led_controller.setup()
        self.assertEqual(self.led_controller._on_value, mock_read.return_value)

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
            self.led_controller._read_node(Path("test-fake")),
        )

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

        self.led_controller._write_node(
            self.led_controller.led_node, "22", True
        )
        mock_read.assert_called_once_with(self.led_controller.led_node)
        mock_write.assert_called_once_with("22")

    @patch("led_control_test.SysFsLEDController._write_node")
    @patch("led_control_test.SysFsLEDController.off")
    @patch("led_control_test.SysFsLEDController._get_initial_state")
    @patch("led_control_test.SysFsLEDController._read_node")
    def test_initial_sysfs_controller_property(
        self, mock_read, mock_get_initial, mock_off, mock_write
    ):
        mock_read.return_value = 255

        led_name = "status"
        with SysFsLEDController(led_name, "3", "0") as led_controller:
            mock_read.assert_called_once_with(
                led_controller.max_brightness_node
            )
            mock_get_initial.assert_called_once_with()
            mock_off.assert_called_once_with()
            mock_write.assert_called_once_with(
                led_controller.trigger_node, "none", False
            )
            self.assertEqual(led_controller.led_name, led_name)
            self.assertIsInstance(led_controller.led_node, PosixPath)
            self.assertIsInstance(led_controller.brightness_node, PosixPath)
            self.assertIsInstance(led_controller.trigger_node, PosixPath)
            self.assertEqual(led_controller.led_node.name, led_name)
            self.assertEqual(led_controller.brightness_node.name, "brightness")
            self.assertEqual(led_controller.trigger_node.name, "trigger")
            self.assertDictEqual(
                led_controller.initial_state,
                {"trigger": None, "brightness": None},
            )

    @patch("led_control_test.SysFsLEDController._read_node")
    def test_get_brightness(self, mock_read):
        mock_read.return_value = "33"
        self.assertEqual(self.led_controller.brightness, "33")
        mock_read.assert_called_once_with(self.led_controller.brightness_node)

    @patch("led_control_test.SysFsLEDController._write_node")
    def test_set_brightness(self, mock_write):
        self.led_controller.brightness = "33"
        mock_write.assert_called_once_with(
            self.led_controller.brightness_node, "33"
        )

    @patch("led_control_test.SysFsLEDController._read_node")
    def test_get_trigger(self, mock_read):
        expected_data = "[none] usb-gadget rfkill-any kbd-scrolllock"
        mock_read.return_value = expected_data

        self.assertEqual(self.led_controller.trigger, expected_data)

    @patch("led_control_test.SysFsLEDController._read_node")
    def test_get_initial_state(self, mock_read):
        mock_read.side_effect = [
            "none usb-gadget [usb-host] rfkill-any rfkill-none kbd-scrolllock",
            "255",
        ]
        expected_data = {"trigger": "usb-host", "brightness": "255"}
        self.led_controller._get_initial_state()
        self.assertEqual(expected_data, self.led_controller.initial_state)

    @patch("time.sleep", return_value=0)
    @patch("led_control_test.datetime")
    @patch("led_control_test.SysFsLEDController.off")
    @patch("led_control_test.SysFsLEDController.on")
    def test_blinking_test(self, mock_on, mock_off, mock_datetime, mock_sleep):
        mock_datetime.now = Mock()
        mock_datetime.now.side_effect = [
            datetime(2020, 1, 1, 0, 0, 0),
            datetime(2020, 1, 1, 0, 0, 1),
            datetime(2020, 1, 1, 0, 0, 2),
        ]

        self.led_controller.blinking(1, 0.5)
        mock_on.assert_called_with()
        mock_off.assert_called_with()


class TestMultiColorSysFsLEDController(unittest.TestCase):

    def setUp(self):

        self.led_controller = SysFsLEDController("name", "0", "0", True)

    @patch(
        "led_control_test.SysFsLEDController.multi_index",
        new_callable=PropertyMock,
    )
    @patch("led_control_test.SysFsLEDController.off")
    @patch(
        "led_control_test.SysFsLEDController.trigger",
        new_callable=PropertyMock,
    )
    @patch("led_control_test.SysFsLEDController._get_initial_state")
    @patch(
        "led_control_test.SysFsLEDController.max_brightness",
        new_callable=PropertyMock,
    )
    def test_setup_passed(
        self, mock_max, mock_get_ini, mock_trigger, mock_off, mock_index
    ):
        mock_max.return_value = "200"
        mock_index.return_value = "red green blue"

        self.led_controller.setup()
        self.assertEqual(self.led_controller._on_value, "200")
        mock_get_ini.assert_called_with()
        mock_trigger.assert_called_with("none")
        mock_off.assert_called_with()
        self.assertEqual(
            self.led_controller.color_mapping, ["red", "green", "blue"]
        )

    @patch(
        "led_control_test.SysFsLEDController.multi_intensity",
        new_callable=PropertyMock,
    )
    @patch(
        "led_control_test.SysFsLEDController.trigger",
        new_callable=PropertyMock,
    )
    @patch(
        "led_control_test.SysFsLEDController.brightness",
        new_callable=PropertyMock,
    )
    def test_teardown_passed(self, mock_br, mock_trigger, mock_intensity):
        self.led_controller.initial_state = {
            "brightness": "br",
            "trigger": "default",
            "multi_intensity": "30 2 1",
        }
        self.led_controller.teardown()
        mock_br.assert_called_with("br")
        mock_trigger.assert_called_with("default")
        mock_intensity.assert_called_with("30 2 1")

    def test_initial_attributes(self):
        self.assertTrue(self.led_controller.is_multi_color_led)
        self.assertEqual(
            self.led_controller.blinking_test_func,
            self.led_controller.multi_color_blinking,
        )
        self.assertEqual(
            self.led_controller.multi_index_node,
            PosixPath("/sys/class/leds/name/multi_index"),
        )
        self.assertEqual(
            self.led_controller.multi_intensity_node,
            PosixPath("/sys/class/leds/name/multi_intensity"),
        )
        self.assertEqual(
            self.led_controller.initial_state["multi_intensity"],
            None,
        )

    @patch("led_control_test.SysFsLEDController._read_node")
    def test_get_multi_intensity(self, mock_read):
        mock_read.return_value = "33"
        self.assertEqual(self.led_controller.multi_intensity, "33")

    @patch("led_control_test.SysFsLEDController._write_node")
    def test_set_multi_intensity(self, mock_write):
        self.led_controller.multi_intensity = "33"
        mock_write.assert_called_once_with(
            self.led_controller.multi_intensity_node, "33"
        )

    @patch("led_control_test.SysFsLEDController._read_node")
    def test_get_multi_index(self, mock_read):
        mock_read.return_value = "33"
        self.assertEqual(self.led_controller.multi_index, "33")

    @patch(
        "led_control_test.SysFsLEDController.max_brightness",
        new_callable=PropertyMock,
    )
    def test_form_multi_intensity_value(self, mock_max):
        mock_max.side_effect = ["20", "0"]

        self.led_controller.color_mapping = ["red", "green"]
        ret = self.led_controller.form_multi_intensity_value("red")
        self.assertEqual(ret, "20 0")

    @patch(
        "led_control_test.SysFsLEDController.multi_intensity",
        new_callable=PropertyMock,
    )
    @patch("led_control_test.SysFsLEDController.blinking")
    @patch("led_control_test.SysFsLEDController.form_multi_intensity_value")
    def test_multi_color_blinking(
        self, mock_form_func, mock_blink, mock_intensity
    ):
        mock_form_func.return_value = "color value"

        self.led_controller.color_mapping = ["red"]
        self.led_controller.multi_color_blinking(10, 1)

        mock_form_func.assert_called_with("red")
        mock_intensity.assert_called_with("color value")
        mock_blink.assert_called_with(10, 1)

    @patch("led_control_test.SysFsLEDController.multi_color_blinking")
    def test_blinkgin_test_func_been_called(self, mock_func):
        self.led_controller.blinking_test_func = mock_func
        self.led_controller.blinking_test(10, 1)
        mock_func.assert_called_with(10, 1)


class TestArgumentParser(unittest.TestCase):

    def test_parser(self):
        sys.argv = [
            "led_control_test.py",
            "--debug",
            "-n",
            "fake-led",
            "--on-value",
            "33",
            "--off-value",
            "1",
            "-d",
            "30",
            "-i",
            "2",
            "--color-type",
            "single",
        ]
        args = register_arguments()

        self.assertEqual(args.debug, True)
        self.assertEqual(args.name, "fake-led")
        self.assertEqual(args.duration, 30)
        self.assertEqual(args.interval, 2)
        self.assertEqual(args.on_value, 33)
        self.assertEqual(args.off_value, 1)
        self.assertEqual(args.color_type, "single")
