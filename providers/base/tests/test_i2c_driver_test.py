#!/usr/bin/env python3

import unittest
import io
import types
from contextlib import redirect_stdout
from unittest.mock import patch, call

import i2c_driver_test

MOCK_BUS_LIST_OUTPUT = """\
i2c-0	i2c       	2360000.i2c                     	I2C adapter
i2c-1	i2c       	5ab0000.i2c                     	I2C adapter
i2c-2	i2c       	23a0000.i2c                     	I2C adapter
i2c-4	i2c       	Some other adapter              	I2C adapter
i2c-5	i2c       	4350000.i2c                     	I2C adapter
i2c-7	i2c       	c120000.i2c                     	I2C adapter
"""

MOCK_DETECT_BUS_0_SUCCESS = """\
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- UU -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- UU -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --\
"""

MOCK_DETECT_BUS_1_SUCCESS = """\
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- 3b -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --\
"""

MOCK_DETECT_BUS_FAILURE = """\
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --\
"""


# A helper function for our subprocess mock
def mock_subprocess_check_output(cmd_args, **kwargs):
    """
    This function will be used as a 'side_effect' for our
    subprocess.check_output mock. It returns different mock data
    based on the command it's given.
    """
    if cmd_args == ["i2cdetect", "-l"]:
        return MOCK_BUS_LIST_OUTPUT
    if cmd_args == ["i2cdetect", "-y", "-r", "0"]:
        return MOCK_DETECT_BUS_0_SUCCESS
    if cmd_args == ["i2cdetect", "-y", "-r", "1"]:
        return MOCK_DETECT_BUS_1_SUCCESS
    if cmd_args == ["i2cdetect", "-y", "-r", "2"]:
        return MOCK_DETECT_BUS_FAILURE
    if cmd_args == ["i2cdetect", "-y", "-r", "4"]:
        return MOCK_DETECT_BUS_FAILURE
    if cmd_args == ["i2cdetect", "-y", "-r", "5"]:
        return MOCK_DETECT_BUS_FAILURE
    if cmd_args == ["i2cdetect", "-y", "-r", "7"]:
        return MOCK_DETECT_BUS_FAILURE

    raise ValueError(f"Unexpected subprocess call: {cmd_args}")


class TestI2CDevice(unittest.TestCase):
    def setUp(self):
        self.mock_args = types.SimpleNamespace()  # no args
        self.device = i2c_driver_test.Device()

    @patch("i2c_driver_test.os.geteuid", return_value=1000)
    def test_device_fails_if_not_root(self, mock_geteuid):
        """Test fails (raises SystemExit) if not run as root."""
        with self.assertRaises(SystemExit) as cm:
            self.device.invoked(self.mock_args)

        self.assertIn(
            "Error: please run this command as root", str(cm.exception)
        )

    @patch("i2c_driver_test.subprocess.check_output")
    @patch("i2c_driver_test.os.geteuid", return_value=0)
    def test_device_success_bus_0(self, mock_geteuid, mock_check_output):
        """Test succeeds with only bus 0 present"""

        def bus_0_side_effect(cmd_args, **kwargs):
            if cmd_args == ["i2cdetect", "-l"]:
                return MOCK_BUS_LIST_OUTPUT.splitlines()[0]
            if cmd_args == ["i2cdetect", "-y", "-r", "0"]:
                return MOCK_DETECT_BUS_0_SUCCESS
            raise ValueError(f"Unexpected subprocess call: {cmd_args}")

        mock_check_output.side_effect = bus_0_side_effect
        with io.StringIO() as buf, redirect_stdout(buf):
            self.device.invoked(self.mock_args)

        calls = mock_check_output.call_args_list

        self.assertIn(
            call(["i2cdetect", "-l"], universal_newlines=True), calls
        )
        self.assertIn(
            call(["i2cdetect", "-y", "-r", "0"], universal_newlines=True),
            calls,
        )

    @patch("i2c_driver_test.subprocess.check_output")
    @patch("i2c_driver_test.os.geteuid", return_value=0)
    def test_device_success_bus_1(self, mock_geteuid, mock_check_output):
        """Test succeeds with only bus 1 present"""

        def bus_1_side_effect(cmd_args, **kwargs):
            if cmd_args == ["i2cdetect", "-l"]:
                return MOCK_BUS_LIST_OUTPUT.splitlines()[1]
            if cmd_args == ["i2cdetect", "-y", "-r", "1"]:
                return MOCK_DETECT_BUS_1_SUCCESS
            raise ValueError(f"Unexpected subprocess call: {cmd_args}")

        mock_check_output.side_effect = bus_1_side_effect
        with io.StringIO() as buf, redirect_stdout(buf):
            self.device.invoked(self.mock_args)

        calls = mock_check_output.call_args_list

        self.assertIn(
            call(["i2cdetect", "-l"], universal_newlines=True), calls
        )
        self.assertIn(
            call(["i2cdetect", "-y", "-r", "1"], universal_newlines=True),
            calls,
        )

    @patch("i2c_driver_test.subprocess.check_output")
    @patch("i2c_driver_test.os.geteuid", return_value=0)
    def test_device_fails_if_no_devices_found(
        self, mock_geteuid, mock_check_output
    ):
        """
        Test fails (raises SystemExit) if no devices are found on any bus.
        """

        def no_devices_side_effect(cmd_args, **kwargs):
            if cmd_args == ["i2cdetect", "-l"]:
                return MOCK_BUS_LIST_OUTPUT.splitlines()[4]
            if cmd_args == ["i2cdetect", "-y", "-r", "5"]:
                return MOCK_DETECT_BUS_FAILURE
            raise ValueError(f"Unexpected subprocess call: {cmd_args}")

        mock_check_output.side_effect = no_devices_side_effect

        with self.assertRaises(SystemExit) as cm:
            with io.StringIO() as buf, redirect_stdout(buf):
                self.device.invoked(self.mock_args)

        self.assertIn("No I2C device detected", str(cm.exception))

    @patch.dict(
        "i2c_driver_test.os.environ",
        {"IGNORED_I2C_BUSES": "2360000.i2c,23a0000.i2c,Some other adapter"},
    )
    @patch("i2c_driver_test.subprocess.check_output")
    @patch("i2c_driver_test.os.geteuid", return_value=0)
    def test_device_ignores_buses_from_env(
        self, mock_geteuid, mock_check_output
    ):
        """Test that buses from IGNORED_I2C_BUSES are not scanned."""
        mock_check_output.side_effect = mock_subprocess_check_output

        with io.StringIO() as buf, redirect_stdout(buf):
            self.device.invoked(self.mock_args)

        calls = mock_check_output.call_args_list

        self.assertIn(
            call(["i2cdetect", "-l"], universal_newlines=True), calls
        )
        self.assertNotIn(
            call(["i2cdetect", "-y", "-r", "0"], universal_newlines=True),
            calls,
        )
        self.assertIn(
            call(["i2cdetect", "-y", "-r", "1"], universal_newlines=True),
            calls,
        )
        self.assertNotIn(
            call(["i2cdetect", "-y", "-r", "2"], universal_newlines=True),
            calls,
        )
        self.assertNotIn(
            call(["i2cdetect", "-y", "-r", "4"], universal_newlines=True),
            calls,
        )
        self.assertIn(
            call(["i2cdetect", "-y", "-r", "5"], universal_newlines=True),
            calls,
        )
        self.assertIn(
            call(["i2cdetect", "-y", "-r", "7"], universal_newlines=True),
            calls,
        )

    @patch.dict(
        "i2c_driver_test.os.environ",
        {
            "IGNORED_I2C_BUSES": "2360000.i2c,5ab0000.i2c,23a0000.i2c,"
            "Some other adapter,4350000.i2c,c120000.i2c"
        },
    )
    @patch("i2c_driver_test.subprocess.check_output")
    @patch("i2c_driver_test.os.geteuid", return_value=0)
    def test_device_fails_if_all_buses_are_ignored(
        self, mock_geteuid, mock_check_output
    ):
        """Test fails (raises SystemExit) if all detected buses are ignored."""
        mock_check_output.side_effect = mock_subprocess_check_output

        with self.assertRaises(SystemExit) as cm:
            with io.StringIO() as buf, redirect_stdout(buf):
                self.device.invoked(self.mock_args)

        self.assertIn("No I2C device detected", str(cm.exception))
