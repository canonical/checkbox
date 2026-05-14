#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
import sys
import os
import unittest
from io import StringIO
from unittest.mock import patch, mock_open

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import light_sensor_test as lst

BASE = "/sys/bus/iio/devices/"


def _dev(name):
    return os.path.join(BASE, name)


def _name_file(dev):
    return os.path.join(dev, "name")


def _make_exists(present_paths):
    def _exists(path):
        return path in present_paths

    return _exists


class TestGetAllSensors(unittest.TestCase):
    @patch("light_sensor_test.os.path.exists", return_value=False)
    def test_returns_empty_when_base_path_missing(self, mock_exists):
        result = lst.get_all_sensors()
        self.assertEqual(result, [])
        mock_exists.assert_called_once_with(BASE)

    @patch(
        "light_sensor_test.os.listdir", return_value=["trigger0", "trigger1"]
    )
    @patch("light_sensor_test.os.path.exists", return_value=True)
    def test_skips_trigger_devices(self, _exists, _listdir):
        result = lst.get_all_sensors()
        self.assertEqual(result, [])

    @patch("light_sensor_test.os.listdir", return_value=["iio:device0"])
    @patch("light_sensor_test.os.path.exists")
    def test_detects_sensor_by_name_keyword_light(self, mock_exists, _listdir):
        dev = _dev("iio:device0")
        mock_exists.side_effect = _make_exists([BASE, _name_file(dev)])
        with patch("builtins.open", mock_open(read_data="apds9960_light\n")):
            result = lst.get_all_sensors()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "apds9960_light")
        self.assertEqual(result[0]["path"], dev)

    @patch("light_sensor_test.os.listdir", return_value=["iio:device0"])
    @patch("light_sensor_test.os.path.exists")
    def test_detects_sensor_by_name_keyword_als(self, mock_exists, _listdir):
        dev = _dev("iio:device0")
        mock_exists.side_effect = _make_exists([BASE, _name_file(dev)])
        with patch("builtins.open", mock_open(read_data="stk3310_als")):
            result = lst.get_all_sensors()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "stk3310_als")

    @patch("light_sensor_test.os.listdir", return_value=["iio:device0"])
    @patch("light_sensor_test.os.path.exists")
    def test_detects_sensor_by_name_keyword_tsl(self, mock_exists, _listdir):
        dev = _dev("iio:device0")
        mock_exists.side_effect = _make_exists([BASE, _name_file(dev)])
        with patch("builtins.open", mock_open(read_data="tsl2591")):
            result = lst.get_all_sensors()
        self.assertEqual(len(result), 1)

    @patch("light_sensor_test.os.listdir", return_value=["iio:device0"])
    @patch("light_sensor_test.os.path.exists")
    def test_detects_sensor_by_name_keyword_ltr(self, mock_exists, _listdir):
        dev = _dev("iio:device0")
        mock_exists.side_effect = _make_exists([BASE, _name_file(dev)])
        with patch("builtins.open", mock_open(read_data="ltr559")):
            result = lst.get_all_sensors()
        self.assertEqual(len(result), 1)

    @patch("light_sensor_test.os.listdir")
    @patch("light_sensor_test.os.path.exists")
    def test_detects_sensor_by_illuminance_file_presence(
        self, mock_exists, mock_listdir
    ):
        _ = _dev("iio:device0")
        mock_exists.side_effect = _make_exists([BASE])
        mock_listdir.side_effect = lambda p: (
            ["iio:device0"]
            if p == BASE
            else ["in_illuminance_input", "in_illuminance_raw"]
        )
        result = lst.get_all_sensors()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "iio:device0")

    @patch("light_sensor_test.os.listdir", return_value=["iio:device0"])
    @patch("light_sensor_test.os.path.exists")
    def test_skips_device_on_ioerror_reading_name_file(
        self, mock_exists, _listdir
    ):
        dev = _dev("iio:device0")
        mock_exists.side_effect = _make_exists([BASE, _name_file(dev)])
        with patch("builtins.open", side_effect=IOError("permission denied")):
            result = lst.get_all_sensors()
        self.assertEqual(result, [])

    @patch("light_sensor_test.os.listdir")
    @patch("light_sensor_test.os.path.exists")
    def test_skips_device_on_oserror_listing_dev_path(
        self, mock_exists, mock_listdir
    ):
        mock_exists.side_effect = _make_exists([BASE])
        # name file absent; listing dev_path raises OSError
        mock_listdir.side_effect = lambda p: (
            ["iio:device0"]
            if p == BASE
            else (_ for _ in ()).throw(OSError("no access"))
        )
        result = lst.get_all_sensors()
        self.assertEqual(result, [])

    @patch("light_sensor_test.os.listdir")
    @patch("light_sensor_test.os.path.exists")
    def test_excludes_non_light_device(self, mock_exists, mock_listdir):
        dev = _dev("iio:device0")
        mock_exists.side_effect = _make_exists([BASE, _name_file(dev)])
        mock_listdir.side_effect = lambda p: (
            ["iio:device0"] if p == BASE else ["in_accel_x", "in_accel_y"]
        )
        with patch("builtins.open", mock_open(read_data="mpu6050")):
            result = lst.get_all_sensors()
        self.assertEqual(result, [])

    @patch(
        "light_sensor_test.os.listdir",
        return_value=["iio:device1", "iio:device0"],
    )
    @patch("light_sensor_test.os.path.exists")
    def test_returns_devices_in_sorted_order(self, mock_exists, mock_listdir):
        dev0 = _dev("iio:device0")
        dev1 = _dev("iio:device1")
        mock_exists.side_effect = _make_exists(
            [BASE, _name_file(dev0), _name_file(dev1)]
        )

        def _open(path, *a, **kw):
            data = "tsl2591" if "device0" in path else "ltr559"
            return mock_open(read_data=data)()

        with patch("builtins.open", side_effect=_open):
            result = lst.get_all_sensors()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "tsl2591")
        self.assertEqual(result[1]["name"], "ltr559")


class TestReadIlluminance(unittest.TestCase):

    SENSOR_PATH = "/sys/bus/iio/devices/iio:device0"

    def _file(self, name):
        return os.path.join(self.SENSOR_PATH, name)

    @patch("light_sensor_test.os.path.exists")
    def test_reads_from_input_file_first(self, mock_exists):
        mock_exists.side_effect = _make_exists(
            [self._file("in_illuminance_input")]
        )
        with patch("builtins.open", mock_open(read_data="512.0")):
            result = lst.read_illuminance(self.SENSOR_PATH)
        self.assertAlmostEqual(result, 512.0)

    @patch("light_sensor_test.os.path.exists")
    def test_falls_back_to_raw_file(self, mock_exists):
        mock_exists.side_effect = _make_exists(
            [self._file("in_illuminance_raw")]
        )
        with patch("builtins.open", mock_open(read_data="300")):
            result = lst.read_illuminance(self.SENSOR_PATH)
        self.assertAlmostEqual(result, 300.0)

    @patch("light_sensor_test.os.path.exists")
    def test_falls_back_to_bare_illuminance_file(self, mock_exists):
        mock_exists.side_effect = _make_exists([self._file("in_illuminance")])
        with patch("builtins.open", mock_open(read_data="  128\n")):
            result = lst.read_illuminance(self.SENSOR_PATH)
        self.assertAlmostEqual(result, 128.0)

    @patch("light_sensor_test.os.path.exists", return_value=False)
    def test_returns_none_when_no_file_found(self, _exists):
        result = lst.read_illuminance(self.SENSOR_PATH)
        self.assertIsNone(result)

    @patch("light_sensor_test.os.path.exists")
    def test_returns_none_on_value_error(self, mock_exists):
        mock_exists.side_effect = _make_exists(
            [self._file("in_illuminance_input")]
        )
        with patch("builtins.open", mock_open(read_data="not_a_number")):
            result = lst.read_illuminance(self.SENSOR_PATH)
        self.assertIsNone(result)

    @patch("light_sensor_test.os.path.exists")
    def test_returns_none_on_ioerror(self, mock_exists):
        mock_exists.side_effect = _make_exists(
            [self._file("in_illuminance_input")]
        )
        with patch("builtins.open", side_effect=IOError("read error")):
            result = lst.read_illuminance(self.SENSOR_PATH)
        self.assertIsNone(result)

    @patch("light_sensor_test.os.path.exists")
    def test_skips_bad_file_and_tries_next(self, mock_exists):
        # input file exists but raises IOError; raw file succeeds
        mock_exists.side_effect = _make_exists(
            [
                self._file("in_illuminance_input"),
                self._file("in_illuminance_raw"),
            ]
        )
        call_count = {"n": 0}

        def _open(path, *a, **kw):
            call_count["n"] += 1
            if "input" in path:
                raise IOError("unreadable")
            return mock_open(read_data="99.5")()

        with patch("builtins.open", side_effect=_open):
            result = lst.read_illuminance(self.SENSOR_PATH)
        self.assertAlmostEqual(result, 99.5)


class TestMainResource(unittest.TestCase):
    @patch("light_sensor_test.get_all_sensors")
    def test_prints_sensor_names(self, mock_sensors):
        mock_sensors.return_value = [
            {"name": "tsl2591", "path": "/sys/bus/iio/devices/iio:device0"},
            {"name": "ltr559", "path": "/sys/bus/iio/devices/iio:device1"},
        ]
        with patch("sys.argv", ["lst", "resource"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                lst.main()
        output = mock_out.getvalue()
        self.assertIn("name: tsl2591", output)
        self.assertIn("name: ltr559", output)

    @patch("light_sensor_test.get_all_sensors", return_value=[])
    def test_no_output_when_no_sensors(self, _sensors):
        with patch("sys.argv", ["lst", "resource"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                lst.main()
        self.assertEqual(mock_out.getvalue(), "")


class TestMainDetect(unittest.TestCase):
    @patch("light_sensor_test.get_all_sensors")
    def test_exits_cleanly_when_sensors_present(self, mock_sensors):
        mock_sensors.return_value = [{"name": "tsl2591", "path": "/dev/null"}]
        with patch("sys.argv", ["lst", "detect"]):
            lst.main()  # must not raise

    @patch("light_sensor_test.get_all_sensors", return_value=[])
    def test_raises_systemexit_when_no_sensors(self, _sensors):
        with patch("sys.argv", ["lst", "detect"]):
            with self.assertRaises(SystemExit) as ctx:
                lst.main()
        self.assertIn("no light sensor", str(ctx.exception).lower())


class TestMainNoCommand(unittest.TestCase):
    def test_prints_help_when_no_command_given(self):
        with patch("sys.argv", ["lst"]):
            with patch("argparse.ArgumentParser.print_help") as mock_help:
                lst.main()
        self.assertEqual(mock_help.call_count, 1)


class TestMainTest(unittest.TestCase):

    SENSOR = {"name": "tsl2591", "path": "/sys/bus/iio/devices/iio:device0"}

    def _run_test_cmd(self, read_values, extra_args=None, sensors=None):
        """
        Helper: run `lst test --name tsl2591 --rounds N ...` with mocked
        read_illuminance returning successive values from read_values.
        Returns (stdout_str, exception_or_None).
        """
        if sensors is None:
            sensors = [self.SENSOR]
        args = [
            "lst",
            "test",
            "--name",
            "tsl2591",
            "--rounds",
            str(len(read_values) // 2),
            "--period",
            "0",
            "--delay",
            "0",
        ]
        if extra_args:
            args += extra_args

        read_iter = iter(read_values)
        with patch("sys.argv", args), patch(
            "light_sensor_test.get_all_sensors", return_value=sensors
        ), patch(
            "light_sensor_test.read_illuminance",
            side_effect=lambda _: next(read_iter),
        ), patch(
            "light_sensor_test.time.sleep"
        ), patch(
            "builtins.input"
        ), patch(
            "sys.stdout", new_callable=StringIO
        ) as mock_out:
            try:
                lst.main()
                return mock_out.getvalue(), None
            except SystemExit as e:
                return mock_out.getvalue(), e

    def test_raises_systemexit_when_sensor_not_found(self):
        with patch(
            "sys.argv", ["lst", "test", "--name", "unknown", "--rounds", "1"]
        ), patch(
            "light_sensor_test.get_all_sensors", return_value=[self.SENSOR]
        ):
            with self.assertRaises(SystemExit) as ctx:
                lst.main()
        self.assertIn("not found", str(ctx.exception).lower())

    def test_raises_systemexit_when_duplicate_sensor_names(self):
        duplicate_sensors = [self.SENSOR, self.SENSOR]
        with patch(
            "sys.argv", ["lst", "test", "--name", "tsl2591", "--rounds", "1"]
        ), patch(
            "light_sensor_test.get_all_sensors", return_value=duplicate_sensors
        ):
            with self.assertRaises(SystemExit) as ctx:
                lst.main()
        self.assertIn("more than 1", str(ctx.exception).lower())

    def test_all_rounds_pass(self):
        out, exc = self._run_test_cmd([100.0, 200.0, 100.0, 200.0])
        self.assertIsNone(exc)
        self.assertIn("2/2 Passed", out)

    def test_all_rounds_fail_raises_systemexit(self):
        out, exc = self._run_test_cmd([100.0, 101.0, 100.0, 101.0])
        self.assertIsNotNone(exc)
        self.assertIn("Test failed", str(exc))
        self.assertIn("0/2 Passed", out)

    def test_partial_pass_raises_systemexit(self):
        out, exc = self._run_test_cmd([100.0, 200.0, 100.0, 101.0])
        self.assertIsNotNone(exc)
        self.assertIn("1/2 Passed", out)

    def test_custom_threshold_respected(self):
        out, exc = self._run_test_cmd(
            [100.0, 105.0, 100.0, 105.0],
            extra_args=["--threshold", "4.0"],
        )
        self.assertIsNone(exc)
        self.assertIn("2/2 Passed", out)

    def test_zero_baseline_positive_val2_is_pass(self):
        out, exc = self._run_test_cmd([0.0, 50.0])
        self.assertIsNone(exc)
        self.assertIn("1/1 Passed", out)

    def test_zero_baseline_zero_val2_is_fail(self):
        out, exc = self._run_test_cmd([0.0, 0.0])
        self.assertIsNotNone(exc)
        self.assertIn("FAIL", out)

    def test_skips_round_on_first_read_failure(self):
        read_values = iter([None, 100.0, 200.0])
        with patch(
            "sys.argv",
            [
                "lst",
                "test",
                "--name",
                "tsl2591",
                "--rounds",
                "2",
                "--period",
                "0",
                "--delay",
                "0",
            ],
        ), patch(
            "light_sensor_test.get_all_sensors", return_value=[self.SENSOR]
        ), patch(
            "light_sensor_test.read_illuminance",
            side_effect=lambda _: next(read_values),
        ), patch(
            "light_sensor_test.time.sleep"
        ), patch(
            "builtins.input"
        ), patch(
            "sys.stdout", new_callable=StringIO
        ) as mock_out:
            with self.assertRaises(SystemExit):
                lst.main()
        out = mock_out.getvalue()
        self.assertIn("Could not read sensor", out)
        self.assertIn("1/2 Passed", out)

    def test_skips_round_on_second_read_failure(self):
        read_values = iter([100.0, None, 100.0, 200.0])
        with patch(
            "sys.argv",
            [
                "lst",
                "test",
                "--name",
                "tsl2591",
                "--rounds",
                "2",
                "--period",
                "0",
                "--delay",
                "0",
            ],
        ), patch(
            "light_sensor_test.get_all_sensors", return_value=[self.SENSOR]
        ), patch(
            "light_sensor_test.read_illuminance",
            side_effect=lambda _: next(read_values),
        ), patch(
            "light_sensor_test.time.sleep"
        ), patch(
            "builtins.input"
        ), patch(
            "sys.stdout", new_callable=StringIO
        ) as mock_out:
            with self.assertRaises(SystemExit):
                lst.main()
        out = mock_out.getvalue()
        self.assertIn("Failed second reading", out)
        self.assertIn("1/2 Passed", out)

    def test_sleep_called_with_period_and_delay(self):
        with patch(
            "sys.argv",
            [
                "lst",
                "test",
                "--name",
                "tsl2591",
                "--rounds",
                "2",
                "--period",
                "7",
                "--delay",
                "3",
            ],
        ), patch(
            "light_sensor_test.get_all_sensors", return_value=[self.SENSOR]
        ), patch(
            "light_sensor_test.read_illuminance", return_value=100.0
        ), patch(
            "light_sensor_test.time.sleep"
        ) as mock_sleep, patch(
            "builtins.input"
        ), patch(
            "sys.stdout", new_callable=StringIO
        ):
            with self.assertRaises(SystemExit):
                lst.main()
        sleep_args = [c[0][0] for c in mock_sleep.call_args_list]
        self.assertIn(7, sleep_args)
        self.assertIn(3, sleep_args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
