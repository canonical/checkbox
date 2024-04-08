import unittest
import argparse
from unittest import mock
import thermal_sensor_test


class ThermalMonitorTest(unittest.TestCase):
    """
    Unit tests for thermal_monitor_test scripts
    """
    @mock.patch("pathlib.Path.read_text")
    @mock.patch("pathlib.Path.exists")
    def test_thermal_node_available(self, mock_file, mock_text):
        """
        Checking Thermal zone file exists
        """
        mock_results = ["apcitz", "enabled", "32000"]
        expected_result = ["fake-thermal"]
        expected_result.extend(mock_results)
        mock_file.return_value = True
        mock_text.side_effect = mock_results

        thermal_node = thermal_sensor_test.ThermalMonitor("fake-thermal")
        self.assertListEqual(
            [
                thermal_node.name, thermal_node.type,
                thermal_node.mode, thermal_node.temperature
            ],
            expected_result
        )

    @mock.patch("pathlib.Path.exists")
    def test_thermal_node_not_available(self, mock_file):
        """
        Checking Thermal zone file not exists
        """
        mock_file.return_value = False
        with self.assertRaises(FileNotFoundError):
            thermal_node = thermal_sensor_test.ThermalMonitor("fake-thermal")
            thermal_node.type

    @mock.patch("thermal_sensor_test.check_temperature")
    @mock.patch("pathlib.Path.read_text")
    @mock.patch("pathlib.Path.exists")
    @mock.patch("subprocess.Popen")
    def test_thermal_monitor_test_passed(
            self, mock_popen, mock_file, mock_text, mock_check_temp):
        """
        Checking Thermal temperature has been altered
        """
        mock_args = mock.Mock(
            return_value=argparse.Namespace(
                name="fake-thermal", duration=30, extra_commands="stress-ng"))
        mock_text.side_effect = ["30000", "30000", "31000"]
        mock_check_temp.return_value = True

        with self.assertLogs() as lc:
            thermal_sensor_test.thermal_monitor_test(mock_args())
            self.assertIn(
                "# The temperature of fake-thermal thermal has been altered",
                lc.output[-1]
            )

    @mock.patch("thermal_sensor_test.check_temperature")
    @mock.patch("pathlib.Path.read_text")
    @mock.patch("pathlib.Path.exists")
    @mock.patch("subprocess.Popen")
    def test_thermal_monitor_with_fixed_temperature(
                    self, mock_popen, mock_file, mock_text, mock_check_temp):
        mock_args = mock.Mock(
            return_value=argparse.Namespace(
                name="fake-thermal", duration=2, extra_commands="stress-ng"))
        mock_text.return_value = "30000"
        mock_check_temp.return_value = False

        with self.assertRaises(SystemExit):
            thermal_sensor_test.thermal_monitor_test(mock_args())
