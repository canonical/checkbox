import argparse
import importlib.util
import io
import os
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "bin",
    "dragonwing_camera_test.py",
)

spec = importlib.util.spec_from_file_location(
    "dragonwing_camera_test", SCRIPT_PATH
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TestDragonwingCameraTest(unittest.TestCase):
    def test_get_camera_list_resolves_name_to_camx_camera_id(self):
        args = argparse.Namespace(cameras="OV5640", raise_error=True)
        fake_log = """
        2024-05-20T10:00:00Z frameworkId=0 cameraId=2 sensorId=1 sensorName=OV5640 logicalCamId=0
        """

        with patch.object(
            module,
            "read_json_file",
            return_value={"OV5640": ["1080p", "720p"]},
        ), patch.object(
            module,
            "run_cmd",
            return_value=types.SimpleNamespace(stdout=fake_log, stderr=""),
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                result = module.get_camera_list(args)

        self.assertEqual(result, 0)
        rendered = out.getvalue()
        self.assertIn("name: OV5640", rendered)
        self.assertIn("camera: 2", rendered)
        self.assertIn("resolution: 1080p", rendered)
        self.assertIn("resolution: 720p", rendered)

    def test_get_camera_list_reports_csi_interface(self):
        args = argparse.Namespace(cameras="OV5640", raise_error=True)
        fake_log = """
        2024-05-20T10:00:00Z frameworkId=0 cameraId=2 sensorId=1 sensorName=OV5640 logicalCamId=0
        """

        with patch.object(
            module,
            "read_json_file",
            return_value={"OV5640": ["1080p"]},
        ), patch.object(
            module,
            "run_cmd",
            return_value=types.SimpleNamespace(stdout=fake_log, stderr=""),
        ), patch.object(
            module,
            "find_csi_interface_for_sensor",
            return_value={"csiphy": 1, "slot": 1, "cci": 0},
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                result = module.get_camera_list(args)

        self.assertEqual(result, 0)
        self.assertIn("csi: 1", out.getvalue())

    def test_get_camera_list_accepts_name_and_id_mapping(self):
        args = argparse.Namespace(cameras="OV5640:2", raise_error=True)

        with patch.object(
            module,
            "read_json_file",
            return_value={"OV5640": ["1080p"]},
        ), patch.object(
            module,
            "find_csi_interface_for_sensor",
            return_value={"csiphy": 3, "slot": 2, "cci": 1},
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                result = module.get_camera_list(args)

        self.assertEqual(result, 0)
        self.assertIn("name: OV5640", out.getvalue())
        self.assertIn("camera: 2", out.getvalue())
        self.assertIn("csi: 3", out.getvalue())

    def test_get_camera_list_accepts_cmk_prefixed_sensor_name(self):
        args = argparse.Namespace(cameras="cmk_imx577", raise_error=True)

        with patch.object(
            module,
            "read_json_file",
            return_value={"imx577": ["2160p", "1080p"]},
        ), patch.object(
            module,
            "run_cmd",
            return_value=types.SimpleNamespace(
                stdout="2024-05-20T10:00:00Z frameworkId=0 cameraId=4 sensorId=1 sensorName=cmk_imx577 logicalCamId=0",
                stderr="",
            ),
        ), patch.object(
            module,
            "find_csi_interface_for_sensor",
            return_value={"csiphy": 2, "slot": 1, "cci": 0},
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                result = module.get_camera_list(args)

        self.assertEqual(result, 0)
        self.assertIn("name: imx577", out.getvalue())
        self.assertIn("camera: 4", out.getvalue())
        self.assertIn("csi: 2", out.getvalue())

    def test_get_camera_list_skips_unavailable_cameras(self):
        args = argparse.Namespace(cameras="imx688 imx57", raise_error=True)

        with patch.object(
            module,
            "read_json_file",
            return_value={"imx688": ["2160p", "1080p"]},
        ), patch.object(
            module,
            "find_camx_camera_ids_for_sensor",
            return_value=["2"],
        ), patch.object(
            module,
            "find_csi_interface_for_sensor",
            return_value={"csiphy": 4, "slot": 1, "cci": 0},
        ), patch.object(
            module.logging, "error"
        ) as mock_error:
            out = io.StringIO()
            with redirect_stdout(out):
                result = module.get_camera_list(args)

        self.assertEqual(result, 1)
        rendered = out.getvalue()
        self.assertIn("name: imx688", rendered)
        mock_error.assert_called_once_with(
            "Unavailable cameras: %s",
            "imx57",
        )

    def test_get_camera_list_silently_skips_unavailable_in_quiet_mode(self):
        args = argparse.Namespace(cameras="imx688 imx57", raise_error=False)

        with patch.object(
            module,
            "read_json_file",
            return_value={"imx688": ["2160p", "1080p"]},
        ), patch.object(
            module,
            "find_camx_camera_ids_for_sensor",
            side_effect=lambda name: ["2"] if name == "imx688" else [],
        ), patch.object(
            module,
            "find_csi_interface_for_sensor",
            return_value={"csiphy": 4, "slot": 1, "cci": 0},
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                result = module.get_camera_list(args)

        self.assertEqual(result, 0)
        rendered = out.getvalue()
        self.assertIn("name: imx688", rendered)
        self.assertNotIn("Skipping unavailable camera", rendered)
        self.assertNotIn("Cannot find resolutions for imx57", rendered)
        self.assertNotIn("ERROR", rendered)
