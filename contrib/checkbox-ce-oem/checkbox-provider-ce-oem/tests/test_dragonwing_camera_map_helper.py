import contextlib
import importlib.util
import io
import os
import tempfile
import unittest


SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "bin",
    "dragonwing-camera-map-helper.py",
)
SPEC = importlib.util.spec_from_file_location(
    "dragonwing_camera_map_helper", SCRIPT_PATH
)
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


class TestCamxEnumeration(unittest.TestCase):
    def test_parses_and_sorts_camera_records(self):
        lines = [
            "frameworkId: 1 cameraId: 2 sensorId: 4 sensorName: imx219 "
            "logicalCamId: 0",
            "frameworkId: 0 cameraId: 0 sensorId: 3 sensorName: ov5640 "
            "logicalCamId: 0",
            "unrelated cameraId: 3 sensorName: ignored",
        ]

        cameras = HELPER.parse_camx_enumeration(lines)

        self.assertEqual([item["camera"] for item in cameras], ["0", "2"])
        self.assertEqual(cameras[0]["sensor"], "ov5640")
        self.assertEqual(cameras[1]["sensor_id"], "4")


class TestKernelProbes(unittest.TestCase):
    def test_parses_sensor_probe_metadata(self):
        probes = HELPER.parse_kernel_probes(
            [
                "Probe success for imx219 slot:2 sensor_id:0x1a",
                "Probe success for ov5640 slot:0 sensor_id:0x42",
            ]
        )

        self.assertEqual(probes[0]["sensor"], "imx219")
        self.assertEqual(probes[0]["slot"], "2")
        self.assertEqual(probes[0]["chip"], "1a")


class TestDeviceTree(unittest.TestCase):
    def test_reads_big_endian_properties_and_string(self):
        with tempfile.TemporaryDirectory() as root:
            node = os.path.join(root, "qcom,cam-sensor@0")
            os.makedirs(node)
            with open(os.path.join(node, "cell-index"), "wb") as handle:
                handle.write((2).to_bytes(4, byteorder="big"))
            with open(os.path.join(node, "csiphy-sd-index"), "wb") as handle:
                handle.write((1).to_bytes(4, byteorder="big"))
            with open(os.path.join(node, "sensor-name"), "wb") as handle:
                handle.write(b"imx219\x00")

            entries = HELPER.read_device_tree(root)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["slot"], "2")
        self.assertEqual(entries[0]["phy"], "1")
        self.assertEqual(entries[0]["name"], "imx219")


class TestRuntimeOptions(unittest.TestCase):
    def test_all_discovered_ids(self):
        cameras = [{"camera": "0"}, {"camera": "2"}]

        self.assertEqual(
            HELPER.camera_ids_to_test("__ALL__", cameras), ["0", "2"]
        )

    def test_rejects_malformed_camera_ids(self):
        with self.assertRaises(ValueError):
            HELPER.camera_ids_to_test("0,,2", [])

    def test_classifies_capture_errors_and_timeouts(self):
        self.assertEqual(
            HELPER.classify_capture(1, "Failed to start stream"),
            "FAIL-STREAM-CONFIG",
        )
        self.assertEqual(HELPER.classify_capture(124, ""), "TIMEOUT")


class TestReportFormatting(unittest.TestCase):
    def test_long_sensor_names_keep_report_within_terminal_width(self):
        cameras = [
            {
                "camera": "1",
                "sensor": "max96724_ox03f10_rb8_yuv_30",
                "sensor_id": "",
            }
        ]
        device_tree = [
            {
                "slot": "21",
                "phy": "1",
                "cci": "0",
                "name": "-",
                "node": (
                    "/sys/firmware/devicetree/base/soc@0/qcom,cam-sensor21"
                ),
            }
        ]
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            HELPER.print_report("cam-server.service", cameras, [], device_tree)

        lines = output.getvalue().splitlines()
        self.assertLessEqual(max(map(len, lines)), 79)
        self.assertIn("qcom,cam-sensor21", output.getvalue())


if __name__ == "__main__":
    unittest.main()
