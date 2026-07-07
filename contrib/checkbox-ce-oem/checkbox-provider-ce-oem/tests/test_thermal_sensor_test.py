import unittest
import argparse
import tempfile
import io
from unittest import mock
from unittest.mock import PropertyMock
from pathlib import Path
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
                thermal_node.name,
                thermal_node.type,
                thermal_node.mode,
                thermal_node.temperature,
            ],
            expected_result,
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
        self, mock_popen, mock_file, mock_text, mock_check_temp
    ):
        """
        Checking Thermal temperature has been altered
        """
        mock_args = mock.Mock(
            return_value=argparse.Namespace(
                name="fake-thermal", duration=30, extra_commands="stress-ng"
            )
        )
        mock_text.side_effect = ["30000", "30000", "31000"]
        mock_check_temp.return_value = True

        with self.assertLogs() as lc:
            thermal_sensor_test.thermal_monitor_test(mock_args())
            self.assertIn(
                "# The temperature of fake-thermal thermal has been altered",
                lc.output[-1],
            )

    @mock.patch("thermal_sensor_test.check_temperature")
    @mock.patch("pathlib.Path.read_text")
    @mock.patch("pathlib.Path.exists")
    @mock.patch("subprocess.Popen")
    def test_thermal_monitor_with_fixed_temperature(
        self, mock_popen, mock_file, mock_text, mock_check_temp
    ):
        mock_args = mock.Mock(
            return_value=argparse.Namespace(
                name="fake-thermal", duration=2, extra_commands="stress-ng"
            )
        )
        mock_text.return_value = "30000"
        mock_check_temp.return_value = False

        with self.assertRaises(SystemExit):
            thermal_sensor_test.thermal_monitor_test(mock_args())

    @mock.patch("thermal_sensor_test.ThermalMonitor")
    @mock.patch("pathlib.Path.glob")
    def test_resolve_thermal_zone_name_by_stable_id(
        self, mock_glob, mock_thermal_monitor
    ):
        mock_glob.return_value = [Path("thermal_zone9"), Path("thermal_zone1")]

        def monitor_factory(name):
            monitor = mock.Mock()
            monitor.name = name
            if name == "thermal_zone1":
                monitor.stable_id = "match-id"
                monitor.type = "x86_pkg_temp"
            else:
                monitor.stable_id = "other-id"
                monitor.type = "acpitz"
            return monitor

        mock_thermal_monitor.side_effect = monitor_factory

        self.assertEqual(
            thermal_sensor_test.resolve_thermal_zone_name(
                "match-id", zone_type="x86_pkg_temp"
            ),
            "thermal_zone1",
        )

    @mock.patch("thermal_sensor_test.resolve_thermal_zone_name")
    def test_monitor_fails_when_stable_id_cannot_be_resolved(
        self, mock_resolve
    ):
        mock_resolve.return_value = None
        mock_args = mock.Mock(
            return_value=argparse.Namespace(
                name=None,
                stable_id="missing-id",
                zone_type="acpitz",
                duration=10,
                extra_commands="stress-ng",
            )
        )

        with self.assertRaises(SystemExit):
            thermal_sensor_test.thermal_monitor_test(mock_args())

    @mock.patch.object(
        thermal_sensor_test.ThermalMonitor,
        "type",
        new_callable=PropertyMock,
    )
    @mock.patch.object(
        thermal_sensor_test.ThermalMonitor,
        "device_path",
        new_callable=PropertyMock,
    )
    @mock.patch.object(
        thermal_sensor_test.ThermalMonitor,
        "firmware_node_path",
        new_callable=PropertyMock,
    )
    @mock.patch.object(
        thermal_sensor_test.ThermalMonitor,
        "of_node_path",
        new_callable=PropertyMock,
    )
    def test_stable_source_prefers_of_node(
        self,
        mock_of_node_path,
        mock_firmware_node_path,
        mock_device_path,
        mock_type,
    ):
        mock_of_node_path.return_value = "/soc/thermal/node"
        mock_firmware_node_path.return_value = ""
        mock_device_path.return_value = "/sys/devices/virtual/thermal/fallback"
        mock_type.return_value = "acpitz"

        thermal_node = thermal_sensor_test.ThermalMonitor("fake-thermal")
        self.assertEqual(thermal_node.stable_source, "/soc/thermal/node")

    def test_compare_thermal_snapshots_human_readable_output(self):
        before_data = "\n".join(
            [
                "sid-a\tthermal_zone1\tcpu\t/source/cpu",
                "sid-b\tthermal_zone2\tgpu\t/source/gpu",
            ]
        ) + "\n"
        after_data = "\n".join(
            [
                "sid-a\tthermal_zone5\tcpu\t/source/cpu",
                "sid-c\tthermal_zone3\tddr\t/source/ddr",
            ]
        ) + "\n"

        with tempfile.TemporaryDirectory() as tmpdir:
            before = Path(tmpdir).joinpath("before.tsv")
            after = Path(tmpdir).joinpath("after.tsv")
            before.write_text(before_data)
            after.write_text(after_data)

            args = argparse.Namespace(
                before=str(before),
                after=str(after),
                allow_legacy_id_upgrade=False,
                fail_on_diff=False,
            )
            with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                thermal_sensor_test.compare_thermal_snapshots(args)
                output = stdout.getvalue()

        self.assertIn(
            "summary: before=2 after=2 missing=1 new=1 identity_changed=0 renumbered=1",
            output,
        )
        self.assertIn(
            "renumbered: type=cpu stable_id=sid-a thermal_zone1 -> thermal_zone5",
            output,
        )
        self.assertIn(
            "missing_after: type=gpu stable_id=sid-b name=thermal_zone2",
            output,
        )
        self.assertIn(
            "new_after: type=ddr stable_id=sid-c name=thermal_zone3",
            output,
        )
