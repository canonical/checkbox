import unittest
from unittest.mock import patch, mock_open, MagicMock, PropertyMock

from argparse import Namespace
from pathlib import Path


HWMON_BASE_PATH = Path("/sys/class/hwmon")


from pwm_fan_test import find_hwmon_node_path, HwmonController, main


class TestHwmonUtils(unittest.TestCase):
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists", side_effect=[True, True, False, True, True])
    @patch("pathlib.Path.is_dir", side_effect=[True, True, True, True, True])
    @patch("pathlib.Path.iterdir")
    def test_find_hwmon_node_path_success(
        self, mock_iterdir, mock_is_dir, mock_exists, mock_read_text
    ):
        """Test successful finding of a known chip name by mocking pathlib globals."""

        mock_hwmon0 = Path(HWMON_BASE_PATH, "hwmon0")
        mock_hwmon1 = Path(HWMON_BASE_PATH, "hwmon1")
        mock_iterdir.return_value = [mock_hwmon0, mock_hwmon1]
        mock_read_text.side_effect = ["other_chip", "test_chip"]

        result = find_hwmon_node_path("test_chip")
        self.assertEqual(result, mock_hwmon1)

    @patch("pathlib.Path.read_text", return_value="some_chip")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.is_dir", return_value=True)
    @patch(
        "pathlib.Path.iterdir", return_value=[Path(HWMON_BASE_PATH, "hwmon0")]
    )
    def test_find_hwmon_node_path_not_found(self, *args):
        """Test failure when the chip name is not found."""

        result = find_hwmon_node_path("non_existent_chip")
        self.assertIsNone(result)


class TestHwmonController(unittest.TestCase):
    """Tests for the HwmonController class methods and properties."""

    def setUp(self):
        self.mock_path = MagicMock(spec=Path)
        self.mock_path.is_dir.return_value = True
        self.mock_path.joinpath.return_value.exists.return_value = True

    def test_init_file_not_found(self):
        self.mock_path.is_dir.return_value = True
        self.mock_path.joinpath.return_value.exists.side_effect = [False]

        with self.assertRaisesRegex(
            FileNotFoundError,
            "PWM control file 'pwm1' does not exist",
        ):
            HwmonController(self.mock_path)

    def test_read_sys_file_success(self):
        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = True
        mock_file.read_text.return_value = " 123 \n"

        controller = HwmonController(self.mock_path)
        result = controller._read_sys_file(mock_file)

        self.assertEqual(result, "123")

    def test_read_sys_file_not_exists(self):
        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = False

        controller = HwmonController(self.mock_path)
        result = controller._read_sys_file(mock_file)

        self.assertIsNone(result)

    def test_read_sys_file_io_error(self):
        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = True
        mock_file.read_text.side_effect = IOError("Read error")

        controller = HwmonController(self.mock_path)
        with self.assertRaises(IOError):
            controller._read_sys_file(mock_file)

    def test_write_sys_file_success(self):
        mock_file = MagicMock(spec=Path)

        controller = HwmonController(self.mock_path)
        controller._write_sys_file(mock_file, "456")

        mock_file.write_text.assert_called_once_with("456", encoding="utf-8")

    def test_write_sys_file_io_error(self):
        mock_file = MagicMock(spec=Path)
        mock_file.write_text.side_effect = IOError("Write error")

        controller = HwmonController(self.mock_path)
        with self.assertRaises(IOError):
            controller._write_sys_file(mock_file, "789")

    @patch(
        "pwm_fan_test.HwmonController._read_sys_file",
        return_value="test_chip",
    )
    def test_name_property(self, mock_read):

        controller = HwmonController(self.mock_path)
        result = controller.name

        self.assertEqual(result, "test_chip")
        mock_read.assert_called_once_with(self.mock_path.joinpath("name"))

    @patch("pwm_fan_test.HwmonController._read_sys_file", return_value="150")
    def test_pwm1_property(self, mock_read):

        controller = HwmonController(self.mock_path)
        result = controller.pwm1

        self.assertEqual(result, 150)
        mock_read.assert_called_once_with(self.mock_path.joinpath("pwm1"))

    @patch("pwm_fan_test.HwmonController._write_sys_file")
    def test_pwm1_setter(self, mock_write):

        controller = HwmonController(self.mock_path)
        controller.pwm1 = 200

        mock_write.assert_called_once_with(
            self.mock_path.joinpath("pwm1"), "200"
        )

    def test_pwm1_setter_invalid_value(self):
        controller = HwmonController(self.mock_path)

        with self.assertRaises(ValueError):
            controller.pwm1 = 300

    def test_pwm1_setter_negative_value(self):
        controller = HwmonController(self.mock_path)

        with self.assertRaises(ValueError):
            controller.pwm1 = -10

    def test_pwm1_setter_non_integer(self):
        controller = HwmonController(self.mock_path)

        with self.assertRaises(ValueError):
            controller.pwm1 = "invalid"

    def test_pwm_enable_property(self):
        with patch.object(
            HwmonController,
            "_read_sys_file",
            return_value="1",
        ) as mock_read:
            controller = HwmonController(self.mock_path)
            result = controller.pwm1_enable

            self.assertEqual(result, 1)
            mock_read.assert_called_once_with(
                self.mock_path.joinpath("pwm1_enable")
            )

    def test_pwm_enable_setter(self):
        with patch.object(HwmonController, "_write_sys_file") as mock_write:
            controller = HwmonController(self.mock_path)

            controller.pwm1_enable = 2

            mock_write.assert_called_once_with(
                self.mock_path.joinpath("pwm1_enable"), "2"
            )

    def test_pwm_enable_setter_invalid_value(self):
        controller = HwmonController(self.mock_path)

        with self.assertRaises(ValueError):
            controller.pwm1_enable = 5

    def test_pwm_enable_setter_negative_value(self):
        controller = HwmonController(self.mock_path)

        with self.assertRaises(ValueError):
            controller.pwm1_enable = -1

    def test_pwm_enable_setter_non_integer(self):
        controller = HwmonController(self.mock_path)

        with self.assertRaises(ValueError):
            controller.pwm1_enable = "invalid"

    @patch(
        "pwm_fan_test.HwmonController._read_sys_file",
        side_effect=["2", "150"],
    )
    @patch("pwm_fan_test.HwmonController._write_sys_file")
    def test_set_pwm_with_validation_already_manual(
        self, mock_write, mock_read
    ):
        controller = HwmonController(self.mock_path)
        controller.pwm1 = 200

        self.assertEqual(mock_write.call_count, 1)
        pwm_call_args = mock_write.call_args_list[0]
        self.assertEqual(pwm_call_args[0][1], "200")

    @patch("pwm_fan_test.HwmonController._read_sys_file", return_value="0")
    @patch("pwm_fan_test.HwmonController._write_sys_file")
    def test_set_pwm_with_validation_to_manual_as_well(
        self, mock_write, mock_read
    ):
        controller = HwmonController(self.mock_path)
        controller.set_pwm_with_validation(180)

        self.assertEqual(mock_write.call_count, 2)
        enable_call_args = mock_write.call_args_list[0]
        self.assertEqual(enable_call_args[0][1], "1")
        pwm_call_args = mock_write.call_args_list[1]
        self.assertEqual(pwm_call_args[0][1], "180")

    def test_set_pwm_with_validation_invalid_value(self):
        controller = HwmonController(self.mock_path)

        with self.assertRaises(ValueError):
            controller.set_pwm_with_validation(300)

    def test_verify_fan_speed_yes(self):
        controller = HwmonController(self.mock_path)

        with patch("builtins.input", return_value="y"):
            result = controller._verify_fan_speed("Is the fan speed correct?")
            self.assertTrue(result)

    def test_verify_fan_speed_no(self):
        controller = HwmonController(self.mock_path)

        with patch("builtins.input", return_value="n"):
            result = controller._verify_fan_speed("Is the fan speed correct?")
            self.assertFalse(result)


class TestMainSequence(unittest.TestCase):

    @patch("builtins.input", side_effect=["y", "y"])
    @patch.object(HwmonController, "turn_fan_off", return_value=True)
    @patch.object(HwmonController, "turn_fan_on", return_value=True)
    @patch.object(
        HwmonController,
        "pwm1_enable",
        new_callable=PropertyMock,
        side_effect=[2, 2],
    )
    @patch.object(
        HwmonController,
        "pwm1",
        new_callable=PropertyMock,
        side_effect=[128, 128],
    )
    @patch("pwm_fan_test.find_hwmon_node_path")
    @patch(
        "pwm_fan_test.register_arguments",
        return_value=Namespace(device="test_chip"),
    )
    @patch("os.geteuid", return_value=0)
    def test_main_restore_auto_mode(
        self,
        mock_root,
        mock_argv,
        mock_find,
        mock_pwm,
        mock_enable,
        mock_turn_on,
        mock_turn_off,
        mock_input,
    ):
        mock_enable.side_effect = [2, 2]
        mock_pwm.side_effect = [128, 128]
        mock_path = MagicMock(spec=Path)
        mock_path.is_dir.return_value = True
        mock_path.joinpath.return_value.exists.return_value = True
        mock_find.return_value = mock_path

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 0)
        self.assertTrue(mock_pwm.called)
        self.assertTrue(mock_enable.called)
