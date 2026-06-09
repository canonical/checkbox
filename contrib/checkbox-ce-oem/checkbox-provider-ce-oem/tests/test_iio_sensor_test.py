import unittest
import sys
import argparse
from pathlib import Path
from io import StringIO
from contextlib import redirect_stdout
from unittest.mock import patch

import iio_sensor_test


class TestIndustrialIOSensorTest(unittest.TestCase):
    @patch("iio_sensor_test._get_iio_device_mapping")
    def test_check_device_exists(self, mock_get_mapping):
        """
        Tests that _check_device returns a Path object for an existing device.
        """
        mock_get_mapping.return_value = {
            "test_sensor_name": "/sys/bus/iio/devices/iio:device0"
        }
        node = iio_sensor_test._check_device("test_sensor_name")
        self.assertIsInstance(node, Path)
        self.assertEqual(str(node), "/sys/bus/iio/devices/iio:device0")

    @patch("iio_sensor_test._get_iio_device_mapping")
    def test_check_device_not_exists(self, mock_get_mapping):
        """
        Tests that _check_device raises FileNotFoundError for a
        non-existent device.
        """
        mock_get_mapping.return_value = {
            "test_sensor_name": "/sys/bus/iio/devices/iio:device0"
        }
        with self.assertRaises(FileNotFoundError):
            iio_sensor_test._check_device("non-existent-sensor")

    @patch("pathlib.Path.exists")
    def test_check_node_exists(self, mock_path_exists):
        """
        Tests that _check_node returns a Path object when the path exists.
        """
        mock_path_exists.return_value = True
        node = iio_sensor_test._check_node("some/path")
        self.assertIsInstance(node, Path)

    @patch("pathlib.Path.exists")
    def test_check_node_not_exists(self, mock_path_exists):
        """
        Tests that _check_node raises FileNotFoundError when the path
        does not exist.
        """
        mock_path_exists.return_value = False
        with self.assertRaises(FileNotFoundError):
            iio_sensor_test._check_node("some/path")

    def test_check_reading_is_expected(self):
        """
        Tests that _check_reading correctly validates a list of
        numeric strings.
        """
        readings = ["20.1", "-255", "+123.3", "0"]
        self.assertTrue(iio_sensor_test._check_reading(readings))

    def test_check_reading_not_expected(self):
        """
        Tests that _check_reading correctly invalidates a list with a
        non-numeric string.
        """
        readings = ["20.1", "-255", "+a"]
        self.assertFalse(iio_sensor_test._check_reading(readings))

    def test_update_adc_nodes_mapping(self):
        """
        Tests the dynamic generation of ADC node paths.
        """
        original_mapping = {"adc": []}
        updated_mapping = iio_sensor_test._update_adc_nodes_mapping(
            original_mapping, 3
        )
        expected_nodes = [
            "in_voltage0_raw",
            "in_voltage1_raw",
            "in_voltage2_raw",
            "in_voltage_scale",
        ]
        self.assertEqual(updated_mapping["adc"], expected_nodes)

    @patch("iio_sensor_test._check_reading", return_value=True)
    @patch("pathlib.Path.read_text")
    @patch("iio_sensor_test._check_node")
    @patch("iio_sensor_test._check_device")
    def test_check_sensor(
        self,
        mock_check_device,
        mock_check_node,
        mock_read_text,
        mock_check_reading,
    ):
        """
        Tests the generic check_sensor function for a pressure sensor.
        """
        mock_check_device.return_value = Path("fake/path")
        mock_read_text.return_value = "123"

        # The nodes to be checked for the 'pressure' type
        pressure_nodes = iio_sensor_test.NODE_MAPPING["pressure"]

        with redirect_stdout(StringIO()):
            iio_sensor_test.check_sensor(
                "test_sensor_name", "pressure", iio_sensor_test.NODE_MAPPING
            )

        # One call to find the device
        mock_check_device.assert_called_once_with("test_sensor_name")
        # One call for each sub-node
        self.assertEqual(mock_check_node.call_count, len(pressure_nodes))
        self.assertEqual(mock_read_text.call_count, len(pressure_nodes))
        # One call with all the collected readings
        self.assertEqual(mock_check_reading.call_count, 1)

    @patch("pathlib.Path.read_text")
    @patch("iio_sensor_test._check_node")
    @patch("iio_sensor_test._check_device")
    def test_check_sensor_unexpected_value(
        self, mock_check_device, mock_check_node, mock_read_text
    ):
        """
        Tests that check_sensor raises ValueError on invalid sensor reading.
        """
        mock_check_device.return_value = Path("fake/path")
        mock_read_text.return_value = "not_a_number"  # Invalid reading

        with redirect_stdout(StringIO()):
            with self.assertRaises(ValueError):
                iio_sensor_test.check_sensor(
                    "test_sensor_name",
                    "pressure",
                    iio_sensor_test.NODE_MAPPING,
                )

    @patch("iio_sensor_test.check_sensor")
    def test_validate_iio_sensor(self, mock_check_sensor):
        """
        Tests the main validation function for a standard sensor.
        """
        mock_args = argparse.Namespace(
            type="pressure", name="test_sensor_name", input_num=None
        )

        iio_sensor_test.validate_iio_sensor(mock_args)

        mock_check_sensor.assert_called_once_with(
            "test_sensor_name", "pressure", iio_sensor_test.NODE_MAPPING
        )

    @patch("iio_sensor_test.check_sensor")
    def test_validate_iio_sensor_for_adc(self, mock_check_sensor):
        """
        Tests the main validation function for an ADC sensor.
        """
        mock_args = argparse.Namespace(type="adc", name="ad7490", input_num=4)

        iio_sensor_test.validate_iio_sensor(mock_args)

        # Verify that the node mapping was updated for the ADC before checking
        updated_nodes = iio_sensor_test._update_adc_nodes_mapping(
            iio_sensor_test.NODE_MAPPING, 4
        )
        mock_check_sensor.assert_called_once_with(
            "ad7490", "adc", updated_nodes
        )

    def test_dump_sensor_resource(self):
        """
        Tests the output of sensor resources from a mapping string.
        """
        mapping_str = "test_sensor_name:pressure|ad7490:adc:8"
        mock_args = argparse.Namespace(mapping=mapping_str)

        with redirect_stdout(StringIO()) as stdout:
            iio_sensor_test.dump_sensor_resource(mock_args)

        expected_output = (
            "name: test_sensor_name\n"
            "type: pressure\n"
            "input_num: None\n\n"
            "name: ad7490\n"
            "type: adc\n"
            "input_num: 8\n\n"
        )
        self.assertEqual(stdout.getvalue(), expected_output)


class TestArgumentParser(unittest.TestCase):
    def test_parser_for_pressure_sensor(self):
        """
        Tests arg parsing for a pressure sensor test.
        """
        sys.argv = [
            "iio_sensor_test.py",
            "test",
            "--type",
            "pressure",
            "--name",
            "test_sensor_name",
        ]
        args = iio_sensor_test.register_arguments()

        self.assertEqual(args.test_func, iio_sensor_test.validate_iio_sensor)
        self.assertEqual(args.type, "pressure")
        self.assertEqual(args.name, "test_sensor_name")

    def test_parser_for_adc_sensor(self):
        """
        Tests arg parsing for an ADC sensor test.
        """
        sys.argv = [
            "iio_sensor_test.py",
            "test",
            "-t",
            "adc",
            "-n",
            "ad7490",
            "-i",
            "8",
        ]
        args = iio_sensor_test.register_arguments()

        self.assertEqual(args.test_func, iio_sensor_test.validate_iio_sensor)
        self.assertEqual(args.type, "adc")
        self.assertEqual(args.name, "ad7490")
        self.assertEqual(args.input_num, 8)

    def test_parser_for_sensor_resource(self):
        """
        Tests arg parsing for the sensor-resource command.
        """
        mapping_str = "test_sensor_name:pressure|ad7490:adc:8"
        sys.argv = ["iio_sensor_test.py", "sensor-resource", mapping_str]
        args = iio_sensor_test.register_arguments()

        self.assertEqual(args.test_func, iio_sensor_test.dump_sensor_resource)
        self.assertEqual(args.mapping, mapping_str)
