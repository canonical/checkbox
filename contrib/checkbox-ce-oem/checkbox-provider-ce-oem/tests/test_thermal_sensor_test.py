import errno
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
        mock_text.side_effect = [
            "acpitz",
            "acpitz",
            "enabled",
            "30000",
            "31000",
            "acpitz",
        ]
        mock_check_temp.return_value = True

        with self.assertLogs() as lc:
            thermal_sensor_test.thermal_monitor_test(mock_args())
            self.assertIn(
                (
                    "# The temperature of fake-thermal "
                    "(acpitz) thermal has been altered"
                ),
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
        mock_text.side_effect = [
            "acpitz",
            "acpitz",
            "enabled",
            "30000",
            "30000",
            "30000",
            "acpitz",
        ]
        mock_check_temp.return_value = False

        with self.assertRaises(SystemExit):
            thermal_sensor_test.thermal_monitor_test(mock_args())

    @mock.patch("pathlib.Path.read_text")
    @mock.patch("pathlib.Path.exists")
    def test_thermal_monitor_ignore_temp_check_reads_once(
        self, mock_exists, mock_text
    ):
        mock_args = mock.Mock(
            return_value=argparse.Namespace(
                name="fake-thermal",
                duration=30,
                extra_commands="stress-ng",
                stable_id=None,
                zone_type=None,
            )
        )
        mock_exists.return_value = True
        mock_text.side_effect = [
            "acpitz",
            "acpitz",
            "enabled",
            "30000",
            "acpitz",
            "acpitz",
        ]

        with mock.patch.dict(
            "os.environ", {"TZ_IGNORE_TEMP_CHECK": "acpitz"}, clear=False
        ):
            thermal_sensor_test.thermal_monitor_test(mock_args())

        self.assertEqual(mock_text.call_count, 6)

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
        before_data = (
            "\n".join(
                [
                    "sid-a\tthermal_zone1\tcpu\t/source/cpu",
                    "sid-b\tthermal_zone2\tgpu\t/source/gpu",
                ]
            )
            + "\n"
        )
        after_data = (
            "\n".join(
                [
                    "sid-a\tthermal_zone5\tcpu\t/source/cpu",
                    "sid-c\tthermal_zone3\tddr\t/source/ddr",
                ]
            )
            + "\n"
        )

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
            (
                "summary: before=2 after=2 missing=1 new=1 "
                "stable_id_upgraded=0 identity_changed=0 renumbered=1"
            ),
            output,
        )
        self.assertIn(
            (
                "renumbered: type=cpu stable_id=sid-a "
                "thermal_zone1 -> thermal_zone5"
            ),
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


class StableIdentityTest(unittest.TestCase):
    """stable_id must not follow cdev bindings when the type is unique."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        patcher = mock.patch.object(
            thermal_sensor_test, "SYS_THERMAL_PATH", self.tmp.name
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def _zone(self, name, zone_type, cdevs=(), temp="42000"):
        zone = self.root / name
        zone.mkdir()
        (zone / "type").write_text(zone_type + "\n")
        (zone / "temp").write_text(temp + "\n")
        (zone / "mode").write_text("enabled\n")
        for index, cdev_type in enumerate(cdevs):
            cdev = zone / "cdev{}".format(index)
            cdev.mkdir()
            (cdev / "type").write_text(cdev_type + "\n")
        return zone

    def test_stable_id_ignores_cdev_change(self):
        zone = self._zone(
            "thermal_zone0",
            "cpu-thermal",
            ("cpufreq-cpu0", "devfreq-17000000.gpu"),
        )
        self._zone("thermal_zone1", "tj-thermal", ("pwm-fan",))
        node = thermal_sensor_test.ThermalMonitor("thermal_zone0")
        before = node.stable_id

        # the GPU devfreq cooling device goes away with its driver
        (zone / "cdev1" / "type").unlink()
        (zone / "cdev1").rmdir()

        self.assertEqual(node.stable_source, "cpu-thermal")
        self.assertEqual(node.stable_id, before)

    def test_dump_reports_temp_available(self):
        self._zone("thermal_zone0", "cpu-thermal")
        node = thermal_sensor_test.ThermalMonitor("thermal_zone0")
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            thermal_sensor_test.dump_thermal_zones(None)
        self.assertIn("temp_available: True", out.getvalue())
        self.assertIn(
            "testable_stable_id: {}".format(node.stable_id), out.getvalue()
        )

    def _dump_enodata_zone(self, env):
        self._zone("thermal_zone0", "cv0-thermal")
        node = thermal_sensor_test.ThermalMonitor("thermal_zone0")
        with mock.patch.dict("os.environ", env, clear=True):
            with mock.patch.object(
                thermal_sensor_test.ThermalMonitor,
                "temperature_available",
                new_callable=PropertyMock,
                return_value=False,
            ):
                with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                    thermal_sensor_test.dump_thermal_zones(None)
        return node, out.getvalue()

    def test_dump_keeps_enodata_zone_testable_by_default(self):
        node, output = self._dump_enodata_zone({})
        self.assertIn("temp_available: False", output)
        self.assertIn("testable_stable_id: {}".format(node.stable_id), output)

    def test_dump_skips_enodata_zone_when_allowed(self):
        _, output = self._dump_enodata_zone(
            {"TZ_ALLOW_NO_DATA": "cv0-thermal|cv1-thermal"}
        )
        self.assertIn("temp_available: False", output)
        self.assertIn("testable_stable_id: none", output)

    def test_dump_keeps_keep_powered_zone_testable(self):
        node, output = self._dump_enodata_zone(
            {"TZ_ALLOW_NO_DATA": "all", "TZ_KEEP_POWERED": "cv0-thermal:/x"}
        )
        self.assertIn("testable_stable_id: {}".format(node.stable_id), output)

    def test_monitor_fails_clearly_on_enodata(self):
        self._zone("thermal_zone0", "gpu-thermal")
        args = argparse.Namespace(
            name="thermal_zone0",
            stable_id=None,
            zone_type=None,
            duration=1,
            extra_commands="true",
        )
        real_read_text = Path.read_text

        def read_text(path, *a, **kw):
            if path.name == "temp":
                raise OSError(errno.ENODATA, "No data available")
            return real_read_text(path, *a, **kw)

        with mock.patch.object(
            Path, "read_text", autospec=True, side_effect=read_text
        ):
            with self.assertRaises(SystemExit) as ctx:
                thermal_sensor_test.thermal_monitor_test(args)
        self.assertIn("ENODATA", str(ctx.exception))
        self.assertIn("gpu-thermal", str(ctx.exception))
        self.assertIn("TZ_KEEP_POWERED", str(ctx.exception))

    def test_temperature_available_false_on_enodata(self):
        self._zone("thermal_zone0", "gpu-thermal")
        node = thermal_sensor_test.ThermalMonitor("thermal_zone0")
        with mock.patch(
            "pathlib.Path.read_text",
            side_effect=OSError(errno.ENODATA, "No data available"),
        ):
            self.assertFalse(node.temperature_available)

    def test_temperature_available_reraises_other_errors(self):
        self._zone("thermal_zone0", "gpu-thermal")
        node = thermal_sensor_test.ThermalMonitor("thermal_zone0")
        with mock.patch(
            "pathlib.Path.read_text",
            side_effect=OSError(errno.EIO, "I/O error"),
        ):
            with self.assertRaises(OSError):
                node.temperature_available


class KeepPoweredTest(unittest.TestCase):
    """TZ_KEEP_POWERED: power the zone's devices on for the test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _device(self, name, control):
        dev = Path(self.tmp.name, name)
        (dev / "power").mkdir(parents=True)
        (dev / "power" / "control").write_text(control + "\n")
        return dev

    def _control(self, dev):
        return (dev / "power" / "control").read_text().strip()

    def test_devices_parsed_with_pci_paths(self):
        env = {
            "TZ_KEEP_POWERED": "gpu-thermal:/sys/bus/pci/devices/0000:01:00.0"
            "|cv0-thermal:/a/pva0,/a/nvdla0"
        }
        with mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(
                thermal_sensor_test._keep_powered_devices("gpu-thermal"),
                ["/sys/bus/pci/devices/0000:01:00.0"],
            )
            self.assertEqual(
                thermal_sensor_test._keep_powered_devices("cv0-thermal"),
                ["/a/pva0", "/a/nvdla0"],
            )
            self.assertEqual(
                thermal_sensor_test._keep_powered_devices("cpu-thermal"), []
            )

    def test_powers_on_and_restores(self):
        dev = self._device("gpu", "auto")
        env = {"TZ_KEEP_POWERED": "gpu-thermal:{}".format(dev)}
        with mock.patch.dict("os.environ", env, clear=True):
            with thermal_sensor_test.keep_powered("gpu-thermal"):
                self.assertEqual(self._control(dev), "on")
        self.assertEqual(self._control(dev), "auto")

    def test_already_on_is_left_untouched(self):
        dev = self._device("gpu", "on")
        env = {"TZ_KEEP_POWERED": "gpu-thermal:{}".format(dev)}
        with mock.patch.dict("os.environ", env, clear=True):
            with mock.patch.object(
                thermal_sensor_test, "_write_power_control"
            ) as write:
                with thermal_sensor_test.keep_powered("gpu-thermal"):
                    pass
        write.assert_not_called()
        self.assertEqual(self._control(dev), "on")

    def test_restores_when_test_fails(self):
        dev = self._device("pva0", "auto")
        env = {"TZ_KEEP_POWERED": "cv0-thermal:{}".format(dev)}
        with mock.patch.dict("os.environ", env, clear=True):
            with self.assertRaises(SystemExit):
                with thermal_sensor_test.keep_powered("cv0-thermal"):
                    raise SystemExit(1)
        self.assertEqual(self._control(dev), "auto")

    def test_missing_power_control_fails(self):
        env = {"TZ_KEEP_POWERED": "gpu-thermal:/nonexistent/device"}
        with mock.patch.dict("os.environ", env, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                with thermal_sensor_test.keep_powered("gpu-thermal"):
                    pass
        self.assertIn("no power/control", str(ctx.exception))

    def test_hung_resume_fails_after_timeout(self):
        dev = self._device("gpu", "auto")
        proc = mock.Mock()
        proc.wait.side_effect = thermal_sensor_test.subprocess.TimeoutExpired(
            "sh", 1
        )
        env = {"TZ_KEEP_POWERED": "gpu-thermal:{}".format(dev)}
        with mock.patch.dict("os.environ", env, clear=True):
            with mock.patch.object(
                thermal_sensor_test.subprocess, "Popen", return_value=proc
            ) as popen:
                with self.assertRaises(SystemExit) as ctx:
                    with thermal_sensor_test.keep_powered("gpu-thermal"):
                        pass
        # the power-on error is reported, not the failed restore after it
        self.assertIn("did not respond", str(ctx.exception))
        self.assertIn("after writing on", str(ctx.exception))
        # a hung child must not hold the job's stdout open
        self.assertIs(
            popen.call_args.kwargs["stdout"],
            thermal_sensor_test.subprocess.DEVNULL,
        )

    def _keep_powered_with_writes(self, fake_write, body_error=None):
        dev = self._device("gpu", "auto")
        env = {"TZ_KEEP_POWERED": "gpu-thermal:{}".format(dev)}
        with mock.patch.dict("os.environ", env, clear=True):
            with mock.patch.object(
                thermal_sensor_test,
                "_write_power_control",
                side_effect=fake_write,
            ):
                with self.assertRaises(SystemExit) as ctx:
                    with thermal_sensor_test.keep_powered("gpu-thermal"):
                        if body_error:
                            raise SystemExit(body_error)
        return str(ctx.exception)

    def test_restores_when_power_on_fails(self):
        writes = []

        def fake_write(control, value):
            writes.append(value)
            if value == "on":
                raise SystemExit("Error: failed to set gpu to on")

        error = self._keep_powered_with_writes(fake_write)
        self.assertIn("failed to set gpu to on", error)
        self.assertEqual(writes, ["on", "auto"])

    def _failing_restore(self, control, value):
        if value != "on":
            raise SystemExit("Error: failed to set gpu to auto")

    def test_restore_error_fails_passing_test(self):
        error = self._keep_powered_with_writes(self._failing_restore)
        self.assertIn("failed to set gpu to auto", error)

    def test_restore_error_keeps_test_error(self):
        error = self._keep_powered_with_writes(
            self._failing_restore, body_error="Error: test failed"
        )
        self.assertEqual(error, "Error: test failed")
