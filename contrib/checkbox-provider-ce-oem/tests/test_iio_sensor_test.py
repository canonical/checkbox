import unittest
import sys
from pathlib import Path
from io import StringIO
from contextlib import redirect_stdout
from unittest.mock import patch

import iio_sensor_test


class TestIndustrialIOSensorTest(unittest.TestCase):

    @patch("pathlib.Path.exists")
    def test_check_root_node_exists(self, mock_path):
        mock_path.return_value = True
        node = iio_sensor_test._check_node("iio_sensor1")

        self.assertIsInstance(node, Path)

    @patch("pathlib.Path.exists")
    def test_check_root_node_not_exists(self, mock_path):
        mock_path.return_value = False

        with self.assertRaises(FileNotFoundError):
            iio_sensor_test._check_node("iio_sensor1")

    def test_check_reading_is_expected(self):
        readings = ["20.1", "-255", "+123.3"]

        self.assertTrue(iio_sensor_test._check_reading(readings))

    def test_check_reading_not_expected(self):
        readings = ["20.1", "-255", "+a"]

        self.assertFalse(iio_sensor_test._check_reading(readings))

    @patch("iio_sensor_test._check_reading")
    @patch("pathlib.Path.read_text")
    @patch("iio_sensor_test._check_node")
    def test_check_pressure_sensor(
            self, mock_check_node, mock_read, mock_check_reading):
        mock_check_node.return_value = Path("fake")

        mock_check_node.return_value = Path("fake")
        mock_read.side_effect = ["20.1", "-255", "+123.3"]

        with redirect_stdout(StringIO()):
            iio_sensor_test.check_pressure_sensor("iio_sensor1")

        self.assertEqual(mock_check_node.call_count, 4)
        self.assertEqual(mock_read.call_count, 3)
        self.assertEqual(mock_check_reading.call_count, 1)

    @patch("pathlib.Path.read_text")
    @patch("iio_sensor_test._check_node")
    def test_check_pressure_sensor_unexpected_value(
                self, mock_check_node, mock_read):

        mock_check_node.return_value = Path("fake")
        mock_read.side_effect = ["20.1", "-255", "+a"]
        with redirect_stdout(StringIO()):
            with self.assertRaises(ValueError):
                iio_sensor_test.check_pressure_sensor("iio_sensor1")

    @patch("iio_sensor_test._check_reading")
    @patch("pathlib.Path.read_text")
    @patch("iio_sensor_test._check_node")
    def test_check_accelerometer_sensor(
            self, mock_check_node, mock_read, mock_check_reading):

        mock_check_node.return_value = Path("fake")
        mock_read.side_effect = [
            "20.1", "-255", "+123.3", "1",
            "509", "-0.1235", "+0.2222", "6666"
        ]

        with redirect_stdout(StringIO()):
            iio_sensor_test.check_accelerometer_sensor("iio_sensor1")

        self.assertEqual(mock_check_node.call_count, 9)
        self.assertEqual(mock_read.call_count, 8)
        self.assertEqual(mock_check_reading.call_count, 1)

    @patch("pathlib.Path.read_text")
    @patch("iio_sensor_test._check_node")
    def test_check_accelerometer_sensor_unexpected_value(
                self, mock_check_node, mock_read):

        mock_check_node.return_value = Path("fake")
        mock_read.side_effect = [
            "d20.1", "-255", "+123.3", "1",
            "5d09", "-0a.1235", "+0.2222", "6666"
        ]
        with redirect_stdout(StringIO()):
            with self.assertRaises(ValueError):
                iio_sensor_test.check_accelerometer_sensor(
                                            "iio_sensor1")

    @patch("iio_sensor_test._check_reading")
    @patch("pathlib.Path.read_text")
    @patch("iio_sensor_test._check_node")
    def test_check_humidity_sensor(
            self, mock_check_node, mock_read, mock_check_reading):

        mock_check_node.return_value = Path("fake")
        mock_read.side_effect = ["20.1", "-255", "+123.3"]

        with redirect_stdout(StringIO()):
            iio_sensor_test.check_humidity_sensor("iio_sensor1")

        self.assertEqual(mock_check_node.call_count, 4)
        self.assertEqual(mock_read.call_count, 3)
        self.assertEqual(mock_check_reading.call_count, 1)

    @patch("pathlib.Path.read_text")
    @patch("iio_sensor_test._check_node")
    def test_check_humidity_sensor_unexpected_value(
                self, mock_check_node, mock_read):

        mock_check_node.return_value = Path("fake")
        mock_read.side_effect = ["20.d1", "-255", "+a"]
        with redirect_stdout(StringIO()):
            with self.assertRaises(ValueError):
                iio_sensor_test.check_humidity_sensor("iio_sensor1")


class TestArgumentParser(unittest.TestCase):

    def test_pressure_parser(self):
        sys.argv = [
            "iio_sensor_test.py", "test", "-t", "pressure",
            "-i", "3"
        ]
        args = iio_sensor_test.register_arguments()

        self.assertEqual(args.test_func,
                         iio_sensor_test.validate_iio_sensor)
        self.assertEqual(args.type, "pressure")
        self.assertEqual(args.index, "3")

    def test_accelerometer_parser(self):
        sys.argv = [
            "iio_sensor_test.py", "test", "-t", "accelerometer",
            "-i", "3"
        ]
        args = iio_sensor_test.register_arguments()

        self.assertEqual(args.test_func,
                         iio_sensor_test.validate_iio_sensor)
        self.assertEqual(args.type, "accelerometer")
        self.assertEqual(args.index, "3")

    def test_humidityrelative_parser(self):
        sys.argv = [
            "iio_sensor_test.py", "test",
            "--type", "humidityrelative",
            "--index", "3"
        ]
        args = iio_sensor_test.register_arguments()

        self.assertEqual(args.test_func,
                         iio_sensor_test.validate_iio_sensor)
        self.assertEqual(args.type, "humidityrelative")
        self.assertEqual(args.index, "3")

    def test_iio_sensore_resource_parser(self):
        sys.argv = [
            "iio_sensor_test.py",
            "sensor-resource",
            "0:pressure 1:accelerometer 2:humidityrelative"
        ]
        args = iio_sensor_test.register_arguments()

        self.assertEqual(args.test_func,
                         iio_sensor_test.dump_sensor_resource)
        self.assertEqual(args.mapping, sys.argv[2])
